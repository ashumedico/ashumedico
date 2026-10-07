"""Keep the YouTube side current without reinstalling T-Amp.

YouTube changes its player every few weeks; a yt-dlp a few months old stops finding
audio. This fetches newer wheels of yt-dlp, its JavaScript solver and ytmusicapi from
PyPI, checks each against the SHA-256 PyPI publishes, and unpacks them into
<state>/pylib. `activate()` puts that folder first on sys.path at the next start, so
the .exe and the source install both pick them up. Pure-Python wheels only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.request
import zipfile

from .settings import state_dir

PACKAGES = ("yt-dlp", "yt-dlp-ejs", "ytmusicapi")
CHECK_EVERY_S = 3 * 24 * 3600


def pylib_dir() -> str:
    return os.path.join(state_dir(), "pylib")


def _ver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v or "0")[:4]) or (0,)


def _manifest() -> dict:
    try:
        with open(os.path.join(pylib_dir(), "versions.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _bundled(pkg: str) -> str:
    try:
        from importlib.metadata import version
        return version(pkg)
    except Exception:  # metadata not shipped (frozen build): fall back to the module itself
        try:
            if pkg == "yt-dlp":
                from yt_dlp.version import __version__
                return __version__
        except Exception:  # yt-dlp missing entirely
            pass
        return "0"


def activate() -> None:
    """Call before importing yt_dlp / ytmusicapi."""
    path = pylib_dir()
    man = _manifest()
    if not man or not os.path.isdir(path):
        return
    if _ver(man.get("yt-dlp", "0")) <= _ver(_bundled("yt-dlp")):
        return  # what's installed is already as new: don't shadow it with an older copy
    if path not in sys.path:
        sys.path.insert(0, path)


def due(settings) -> bool:
    return time.time() - float(settings.get("engine_checked") or 0) > CHECK_EVERY_S


def update(log=lambda msg: None) -> list[str]:
    """Bring every package to PyPI's latest. Returns 'pkg old -> new' lines for what changed."""
    path = pylib_dir()
    os.makedirs(path, exist_ok=True)
    man = _manifest()
    changed = []
    for pkg in PACKAGES:
        have = max(_ver(man.get(pkg, "0")), _ver(_bundled(pkg)))
        with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=20) as r:
            info = json.load(r)
        latest = info["info"]["version"]
        if _ver(latest) <= have:
            continue
        wheel = next((f for f in info.get("urls", []) if f.get("packagetype") == "bdist_wheel"
                      and f["filename"].endswith("-py3-none-any.whl")), None)
        if wheel is None:
            log(f"{pkg} {latest}: no pure-Python wheel, skipped")
            continue
        log(f"downloading {wheel['filename']}")
        with urllib.request.urlopen(wheel["url"], timeout=120) as r:
            data = r.read()
        if hashlib.sha256(data).hexdigest() != wheel["digests"]["sha256"]:
            raise RuntimeError(f"{wheel['filename']}: checksum mismatch, not installed")
        _install_wheel(data, path)
        old = man.get(pkg) or _bundled(pkg)
        man[pkg] = latest
        changed.append(f"{pkg} {old} -> {latest}")
    with open(os.path.join(path, "versions.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    return changed


def _dist_name(dist_info: str) -> str:
    """'yt_dlp-2026.8.19.dist-info' -> 'yt_dlp'."""
    return dist_info[: -len(".dist-info")].rsplit("-", 1)[0]


def _install_wheel(data: bytes, dest: str) -> None:
    os.makedirs(dest, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        whl = os.path.join(tmp, "pkg.whl")
        with open(whl, "wb") as fh:
            fh.write(data)
        with zipfile.ZipFile(whl) as zf:
            names = zf.namelist()
            root = os.path.realpath(dest)
            for n in names:  # refuse anything that would land outside pylib
                if not os.path.realpath(os.path.join(dest, n)).startswith(root + os.sep):
                    raise RuntimeError(f"unsafe path in wheel: {n}")
            tops = {n.split("/", 1)[0] for n in names}
            for top in tops:
                target = os.path.join(dest, top)
                if top.endswith(".dist-info"):
                    dist = _dist_name(top)
                    for old in os.listdir(dest):
                        if old.endswith(".dist-info") and _dist_name(old) == dist:
                            shutil.rmtree(os.path.join(dest, old), ignore_errors=True)
                elif os.path.isdir(target):
                    shutil.rmtree(target, ignore_errors=True)
            zf.extractall(dest)

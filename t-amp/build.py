"""Build dist/T-Amp/T-Amp.exe with PyInstaller. Run on Windows: python build.py

One folder, not one file: a one-file exe unpacks ~300 MB to %TEMP% on every launch.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    os.chdir(HERE)
    import deno
    deno_bin = deno.find_deno_bin()
    os.makedirs("build", exist_ok=True)
    icon = os.path.join("build", "t-amp.ico")
    subprocess.run([sys.executable, "-m", "tamp", "--make-icon", icon], check=True)
    shutil.rmtree(os.path.join("dist", "T-Amp"), ignore_errors=True)
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", "T-Amp", "--icon", icon,
        "--collect-all", "yt_dlp_ejs",
        "--collect-submodules", "yt_dlp",
        "--collect-data", "ytmusicapi",
        "--collect-all", "imageio_ffmpeg",
        "--copy-metadata", "yt-dlp", "--copy-metadata", "yt-dlp-ejs", "--copy-metadata", "ytmusicapi",
        "--add-binary", f"{deno_bin}{os.pathsep}deno",
        "--exclude-module", "tkinter",
        "T-Amp.pyw",
    ]
    subprocess.run(cmd, check=True)
    exe = os.path.join(HERE, "dist", "T-Amp", "T-Amp.exe" if sys.platform == "win32" else "T-Amp")
    print(f"\nBuilt: {exe}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

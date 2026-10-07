"""Audio engine: ffmpeg decodes, a buffer absorbs the network, PortAudio plays.

    source URL --ffmpeg--> float32 PCM --PcmBuffer--> callback: EQ -> vis tap -> volume/balance -> device

The engine knows nothing about YouTube; it plays any URL or file ffmpeg can open.
It never blocks the UI: decoding runs in a thread, playback in PortAudio's callback,
and the UI learns what happened by calling `poll()` from its timer.
"""
from __future__ import annotations

import collections
import subprocess
import sys
import threading
import time

import numpy as np

from .dsp import Equalizer

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
CHANNELS = 2
PREBUFFER_S = 0.35     # audio needed before a fresh start begins to play
REBUFFER_S = 1.5       # ...and after the network ran dry mid-song
MAX_AHEAD_S = 20.0     # how far ffmpeg may decode ahead of the speakers
IDLE_CLOSE_S = 120.0   # paused this long -> release the device so Windows can sleep


def ffmpeg_command(ffmpeg: str, source: str, samplerate: int, start: float = 0.0,
                   headers: dict | None = None) -> list[str]:
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error"]
    if source.startswith(("http://", "https://")):
        cmd += ["-reconnect", "1", "-reconnect_streamed", "1",
                "-reconnect_on_network_error", "1", "-reconnect_delay_max", "5",
                "-rw_timeout", "15000000"]
        headers = dict(headers or {})
        ua = headers.pop("User-Agent", None) or headers.pop("user-agent", None)
        if ua:
            cmd += ["-user_agent", ua]
        extra = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        if extra:
            cmd += ["-headers", extra]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", source, "-vn", "-sn", "-dn", "-map", "0:a:0",
            "-f", "f32le", "-acodec", "pcm_f32le", "-ac", str(CHANNELS), "-ar", str(samplerate),
            "pipe:1"]
    return cmd


class PcmBuffer:
    """FIFO of float32 (frames, 2) blocks. The decoder waits when it is full."""

    def __init__(self, max_frames: int):
        self.max_frames = max_frames
        self._chunks: collections.deque[np.ndarray] = collections.deque()
        self._frames = 0
        self._cond = threading.Condition()

    @property
    def frames(self) -> int:
        return self._frames

    def put(self, block: np.ndarray, stop: threading.Event) -> bool:
        with self._cond:
            while self._frames >= self.max_frames and not stop.is_set():
                self._cond.wait(0.1)
            if stop.is_set():
                return False
            self._chunks.append(block)
            self._frames += len(block)
            return True

    def take(self, out: np.ndarray) -> int:
        """Fill `out` from the front of the queue; return how many frames were filled."""
        need, got = len(out), 0
        with self._cond:
            while got < need and self._chunks:
                head = self._chunks[0]
                n = min(need - got, len(head))
                out[got:got + n] = head[:n]
                got += n
                if n == len(head):
                    self._chunks.popleft()
                else:
                    self._chunks[0] = head[n:]
            self._frames -= got
            self._cond.notify_all()
        return got


class Decoder(threading.Thread):
    """Runs one ffmpeg process and pours its PCM into a PcmBuffer."""

    def __init__(self, cmd: list[str], buf: PcmBuffer):
        super().__init__(daemon=True, name="t-amp-decoder")
        self.cmd = cmd
        self.buf = buf
        self.stop_event = threading.Event()
        self.done = False
        self.returncode: int | None = None
        self.frames_decoded = 0
        self.stderr: collections.deque[str] = collections.deque(maxlen=12)
        self._proc: subprocess.Popen | None = None

    def run(self) -> None:
        try:
            self._proc = subprocess.Popen(
                self.cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=0, creationflags=CREATE_NO_WINDOW)
        except OSError as exc:
            self.stderr.append(f"cannot start ffmpeg: {exc}")
            self.returncode = -1
            self.done = True
            return
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        frame_bytes = 4 * CHANNELS
        pending = b""
        try:
            while not self.stop_event.is_set():
                data = self._proc.stdout.read(65536)
                if not data:
                    break
                pending += data
                usable = len(pending) // frame_bytes * frame_bytes
                if not usable:
                    continue
                block = np.frombuffer(pending[:usable], dtype="<f4").reshape(-1, CHANNELS)
                pending = pending[usable:]
                self.frames_decoded += len(block)
                if not self.buf.put(block, self.stop_event):
                    break
        except (OSError, ValueError):
            pass
        finally:
            if self.stop_event.is_set():
                self._kill()
            try:
                self.returncode = self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._kill()
                self.returncode = self._proc.wait()
            self.done = True

    def _drain_stderr(self) -> None:
        try:
            for line in iter(self._proc.stderr.readline, b""):
                text = line.decode("utf-8", "replace").strip()
                if text:
                    self.stderr.append(text)
        except (OSError, ValueError):
            pass

    def _kill(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except OSError:
                pass

    def stop(self) -> None:
        self.stop_event.set()
        self._kill()


class _Session:
    """One continuous run of audio: a load, or a seek. Replaced whole, never edited from outside."""

    def __init__(self, gen: int, decoder: Decoder, base: float):
        self.gen = gen
        self.decoder = decoder
        self.buf = decoder.buf
        self.base = base            # seconds into the track where this run started
        self.played = 0             # frames handed to the device since `base`
        self.started = False        # has the prebuffer been reached once?
        self.starved = False        # ran dry mid-song, waiting for REBUFFER_S
        self.drained = False        # decoder finished and every frame was played
        self.reported = False


class AudioEngine:
    """Play / pause / seek / stop over ffmpeg + PortAudio, with EQ, balance and a vis tap."""

    def __init__(self, ffmpeg: str, samplerate: int | None = None, output=None):
        """`output` builds the device stream; tests pass a fake, the app leaves it None."""
        self.ffmpeg = ffmpeg
        self._sd = None
        if samplerate is None:
            import sounddevice as sd
            self._sd = sd
            try:
                samplerate = int(sd.query_devices(kind="output")["default_samplerate"])
            except Exception:  # no output device right now: pick the common rate, report on play
                samplerate = 48000
        self.samplerate = int(samplerate)
        self._make_output = output
        self.eq = Equalizer(self.samplerate, CHANNELS)
        self.volume = 0.8           # 0..1, applied as a square-law curve
        self.balance = 0.0          # -1 (left) .. +1 (right)
        self.duration: float | None = None
        self.source: str | None = None
        self._headers: dict | None = None
        self._session: _Session | None = None
        self._gen = 0
        self._paused = False
        self._paused_at = 0.0
        self._fade = 0.0
        self._stream = None
        self._latency = 0.0
        self._events: collections.deque = collections.deque()
        self._scratch = np.zeros((8192, CHANNELS), dtype=np.float32)
        self._vis = np.zeros(16384, dtype=np.float32)
        self._vis_written = 0

    # ---- transport -------------------------------------------------------------------------
    def open(self, source: str, headers: dict | None = None, start: float = 0.0,
             duration: float | None = None) -> None:
        """Start playing `source` from `start` seconds."""
        self.source, self._headers, self.duration = source, headers, duration
        self._paused = False
        self._start_session(max(0.0, start))
        self._ensure_stream()

    def seek(self, seconds: float) -> None:
        if self.source is None:
            return
        if self.duration:
            seconds = min(seconds, max(0.0, self.duration - 0.5))
        self._start_session(max(0.0, seconds))
        self.eq.reset()

    def pause(self) -> None:
        if self._session is not None and not self._paused:
            self._paused = True
            self._paused_at = time.monotonic()

    def resume(self) -> None:
        if self._session is not None and self._paused:
            self._paused = False
            self._ensure_stream()

    def stop(self) -> None:
        old, self._session = self._session, None
        self._paused = False
        if old is not None:
            old.decoder.stop()
        self._close_stream()
        self._vis[:] = 0.0

    def close(self) -> None:
        self.stop()

    # ---- state the UI reads ----------------------------------------------------------------
    @property
    def state(self) -> str:
        s = self._session
        if s is None:
            return "stopped"
        if self._paused:
            return "paused"
        if s.drained:
            return "ended"
        if not s.started or s.starved:
            return "buffering"
        return "playing"

    @property
    def position(self) -> float:
        s = self._session
        if s is None:
            return 0.0
        lag = 0.0 if (self._paused or s.drained) else self._latency  # paused: the device ran dry
        audible = s.played - lag * self.samplerate
        return s.base + max(0.0, audible) / self.samplerate

    @property
    def buffered_seconds(self) -> float:
        s = self._session
        return s.buf.frames / self.samplerate if s else 0.0

    def audible_samples(self, n: int = 2048) -> np.ndarray | None:
        """The last `n` mono samples that have reached the speakers (pre-volume, post-EQ)."""
        if self._session is None:
            return None
        end = self._vis_written - int(self._latency * self.samplerate)
        if end <= 0:
            return np.zeros(n, dtype=np.float32)
        size = len(self._vis)
        idx = (np.arange(end - n, end) % size)
        return self._vis[idx]

    def poll(self) -> list[tuple]:
        """Called by the UI ~30x/s. Returns ('finished',) or ('error', message, position) once each."""
        s = self._session
        out = list(self._events)
        self._events.clear()
        if s is None:
            return out
        dec = s.decoder
        if not s.reported and dec.done and dec.returncode not in (0, None) and s.buf.frames == 0:
            near_end = self.duration and self.position >= self.duration - 3
            s.reported = True
            if near_end:
                s.drained = True
                out.append(("finished",))
            else:
                msg = dec.stderr[-1] if dec.stderr else f"ffmpeg exited with code {dec.returncode}"
                out.append(("error", msg, self.position))
        elif not s.reported and s.drained:
            s.reported = True
            out.append(("finished",))
        if self._paused and self._stream is not None and time.monotonic() - self._paused_at > IDLE_CLOSE_S:
            self._close_stream()
        if self._stream is not None and not self._paused and self._stream_died():
            self._close_stream()
            self._ensure_stream()
        return out

    # ---- internals -------------------------------------------------------------------------
    def _start_session(self, start: float) -> None:
        self._gen += 1
        buf = PcmBuffer(int(MAX_AHEAD_S * self.samplerate))
        dec = Decoder(ffmpeg_command(self.ffmpeg, self.source, self.samplerate, start, self._headers), buf)
        old, self._session = self._session, _Session(self._gen, dec, start)
        self._fade = 0.0
        dec.start()
        if old is not None:
            old.decoder.stop()

    def _ensure_stream(self) -> None:
        if self._stream is not None:
            return
        if self._make_output is not None:
            self._stream = self._make_output(self)
        else:
            sd = self._sd
            try:
                # Re-scan devices so headphones plugged in since launch become the default.
                sd._terminate()
                sd._initialize()
            except Exception:  # private API moved: keep the device list we have
                pass
            try:
                self._stream = sd.OutputStream(
                    samplerate=self.samplerate, channels=CHANNELS, dtype="float32",
                    latency="high", callback=self._callback)
                self._stream.start()
            except Exception as exc:  # no device, device busy, unsupported rate
                self._stream = None
                self._events.append(("device", str(exc)))
                return
        self._latency = float(getattr(self._stream, "latency", 0.0) or 0.0)

    def _close_stream(self) -> None:
        st, self._stream = self._stream, None
        if st is not None:
            try:
                st.close()
            except Exception:  # a device that vanished can't be closed cleanly; drop it
                pass

    def _stream_died(self) -> bool:
        st = self._stream
        return bool(st is not None and hasattr(st, "active") and not st.active and not getattr(st, "closed", False))

    def _callback(self, outdata, frames, time_info, status) -> None:
        s = self._session
        if s is None or frames > len(self._scratch):
            outdata.fill(0)
            self._tap(None, frames)
            return
        if self._paused and self._fade <= 0.0:
            outdata.fill(0)
            self._tap(None, frames)
            return
        if not s.started or s.starved:
            need = (REBUFFER_S if s.starved else PREBUFFER_S) * self.samplerate
            if s.buf.frames >= need or s.decoder.done:
                s.started, s.starved = True, False
            else:
                outdata.fill(0)
                self._tap(None, frames)
                return
        block = self._scratch[:frames]
        got = s.buf.take(block)
        if got < frames:
            block[got:] = 0.0
            if s.decoder.done:
                if s.buf.frames == 0 and got == 0:
                    s.drained = True
            else:
                s.starved = True
        s.played += got
        block = self.eq.process(block)
        target = 0.0 if self._paused else 1.0
        if self._fade != target:  # 1-block ramp: no click on pause, resume or a fresh start
            block = block * np.linspace(self._fade, target, frames, dtype=np.float32)[:, None]
            self._fade = target
        self._tap(block, frames)
        g = self.volume * self.volume
        left = g * min(1.0, 1.0 - self.balance)
        right = g * min(1.0, 1.0 + self.balance)
        np.clip(block * np.array([left, right], dtype=np.float32), -1.0, 1.0, out=outdata)

    def _tap(self, block, frames: int) -> None:
        size = len(self._vis)
        start = self._vis_written % size
        mono = np.zeros(frames, dtype=np.float32) if block is None else block.mean(axis=1)
        end = start + frames
        if end <= size:
            self._vis[start:end] = mono
        else:
            k = size - start
            self._vis[start:] = mono[:k]
            self._vis[:end - size] = mono[k:]
        self._vis_written += frames

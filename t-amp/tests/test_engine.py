"""The audio core, end to end, without a sound card or a network.

A real ffmpeg decodes a real file; a fake device pulls blocks the way PortAudio would.
Run:  python -m pytest t-amp/tests -q
"""
import os
import subprocess
import sys
import tempfile
import threading
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tamp.dsp import EQ_FREQS, Equalizer, Visualizer  # noqa: E402
from tamp.engine import AudioEngine, ffmpeg_command  # noqa: E402
from tamp.youtube import find_ffmpeg  # noqa: E402

SR = 48000
FFMPEG = find_ffmpeg()


class FakeDevice:
    """Calls the engine's callback from a thread, `speed` times faster than real time."""

    latency = 0.0
    closed = False

    def __init__(self, engine, block=1024, speed=20.0):
        self.engine, self.block, self.speed = engine, block, speed
        self.out = []
        self.active = True
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        while not self._stop.is_set():
            buf = np.zeros((self.block, 2), dtype=np.float32)
            self.engine._callback(buf, self.block, None, None)
            self.out.append(buf.copy())
            time.sleep(self.block / SR / self.speed)

    def close(self):
        self._stop.set()
        self.active = False
        self._t.join(1)

    def audio(self):
        return np.concatenate(self.out) if self.out else np.zeros((0, 2), np.float32)


def make_tone(path, freq=440, seconds=3.0):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:sample_rate=44100:duration={seconds}",
                    "-ac", "2", path], check=True)


@pytest.fixture(scope="module")
def tone():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "tone.wav")
    make_tone(p)
    return p


def wait_for(cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def make_engine():
    devices = []

    def factory(engine):
        d = FakeDevice(engine)
        devices.append(d)
        return d
    return AudioEngine(FFMPEG, samplerate=SR, output=factory), devices


def test_plays_to_the_end_and_reports_finished_once(tone):
    eng, devs = make_engine()
    eng.open(tone, duration=3.0)
    events = []
    assert wait_for(lambda: events.extend(eng.poll()) or ("finished",) in events, 15)
    assert events.count(("finished",)) == 1
    audio = devs[0].audio()
    played = np.abs(audio).max(axis=1) > 1e-4
    # 3 s of tone at 48 kHz: within one block of 144000 frames
    assert abs(int(played.sum()) - 3 * SR) < 2048
    assert eng.state == "ended"
    eng.close()


def test_volume_balance_and_rms(tone):
    eng, devs = make_engine()
    eng.volume, eng.balance = 1.0, -1.0       # hard left
    eng.open(tone, duration=3.0)
    assert wait_for(lambda: eng.position > 1.0)
    a = devs[0].audio()[-4096:]
    assert np.sqrt(np.mean(a[:, 0] ** 2)) > 0.05
    assert np.abs(a[:, 1]).max() == 0.0          # right silent
    eng.close()


def test_seek_restarts_decoder_at_position(tone):
    eng, devs = make_engine()
    eng.open(tone, duration=3.0)
    assert wait_for(lambda: eng.state == "playing")
    eng.seek(2.0)
    assert 1.99 <= eng.position <= 2.2
    events = []
    assert wait_for(lambda: events.extend(eng.poll()) or ("finished",) in events, 10)
    eng.close()


def test_pause_stops_consuming_and_resume_continues(tone):
    eng, devs = make_engine()
    eng.open(tone, duration=3.0)
    assert wait_for(lambda: eng.position > 0.5)
    eng.pause()
    time.sleep(0.05)
    p1 = eng.position
    time.sleep(0.3)
    assert eng.position == pytest.approx(p1, abs=0.03)
    assert eng.state == "paused"
    eng.resume()
    assert wait_for(lambda: eng.position > p1 + 0.3)
    eng.close()


def test_bad_source_reports_error_not_finished():
    eng, devs = make_engine()
    eng.open("/definitely/not/here.m4a", duration=200)
    events = []
    assert wait_for(lambda: events.extend(eng.poll()) or any(e[0] == "error" for e in events), 10)
    err = next(e for e in events if e[0] == "error")
    assert "not" in err[1].lower() or "no such" in err[1].lower()
    assert ("finished",) not in events
    eng.close()


def test_http_command_carries_headers_and_reconnect():
    cmd = ffmpeg_command("ffmpeg", "https://x.googlevideo.com/a", 48000, 12.5,
                         {"User-Agent": "UA/1", "Accept": "*/*"})
    assert cmd[cmd.index("-user_agent") + 1] == "UA/1"
    assert "Accept: */*\r\n" in cmd[cmd.index("-headers") + 1]
    assert cmd[cmd.index("-ss") + 1] == "12.500"
    assert "-reconnect" in cmd
    local = ffmpeg_command("ffmpeg", "C:/x.wav", 48000)
    assert "-reconnect" not in local and "-ss" not in local


def _tone(freq, n=SR):
    t = np.arange(n) / SR
    x = 0.25 * np.sin(2 * np.pi * freq * t).astype(np.float32)
    return np.stack([x, x], axis=1)


@pytest.mark.parametrize("band", [0, 4, 9])
def test_eq_band_boost_is_heard_at_its_frequency(band):
    eq = Equalizer(SR)
    gains = [0.0] * 10
    gains[band] = 12.0
    eq.set(True, 0.0, gains)
    x = _tone(EQ_FREQS[band])
    y = np.concatenate([eq.process(x[i:i + 1024]) for i in range(0, len(x), 1024)])
    tail = slice(SR // 2, None)  # after the filters settle
    gain_db = 20 * np.log10(np.sqrt(np.mean(y[tail, 0] ** 2)) / np.sqrt(np.mean(x[tail, 0] ** 2)))
    assert 10.5 < gain_db < 13.5, gain_db
    assert eq.response_db(np.array([EQ_FREQS[band]]))[0] == pytest.approx(12.0, abs=1.0)


def test_eq_off_is_bit_exact():
    eq = Equalizer(SR)
    eq.set(False, 6.0, [12.0] * 10)
    x = _tone(1000, 4096)
    assert np.array_equal(eq.process(x), x)


def test_preamp_only():
    eq = Equalizer(SR)
    eq.set(True, -6.0, [0.0] * 10)
    x = _tone(1000, 4096)
    assert np.allclose(eq.process(x), x * 10 ** (-6 / 20), atol=1e-6)


def test_visualizer_puts_a_tone_in_the_right_bar():
    vis = Visualizer(SR)
    for freq in (100, 1000, 8000):
        lv = vis.levels(_tone(freq, 4096)[:, 0], 19)
        edges = np.geomspace(40, 16000, 20)
        expect = int(np.searchsorted(edges, freq) - 1)
        assert int(np.argmax(lv)) == expect, (freq, lv)
        assert lv.max() > 0.6
    assert vis.levels(np.zeros(4096, np.float32), 19).max() == 0.0


def test_visualizer_bars_fall_and_peaks_hang():
    vis = Visualizer(SR)
    loud = _tone(1000, 4096)[:, 0]
    vis.step(loud, 19)
    top_bar, top_peak = vis.bars.max(), vis.peaks.max()
    vis.step(None, 19)
    assert vis.bars.max() < top_bar
    assert vis.peaks.max() == pytest.approx(top_peak, abs=0.01)


def test_stream_cut_short_is_an_error_not_the_end(tone):
    eng, devs = make_engine()
    eng.open(tone, duration=60.0)          # the file stops at 3 s of a "60 s" song
    events = []
    assert wait_for(lambda: events.extend(eng.poll()) or any(e[0] == "error" for e in events), 15)
    assert ("finished",) not in events
    assert next(e for e in events if e[0] == "error")[1] == "stream ended early"
    eng.close()


def test_halt_keeps_the_device_stop_releases_it(tone):
    eng, devs = make_engine()
    eng.open(tone, duration=3.0)
    assert wait_for(lambda: eng.state == "playing")
    eng.halt()
    assert eng._stream is not None and eng.state == "stopped"
    eng.open(tone, duration=3.0)
    assert len(devs) == 1, "the next song reuses the open device"
    eng.stop()
    assert eng._stream is None


def _has_output_device() -> bool:
    try:
        import sounddevice as sd
        sd.query_devices(kind="output")
        return True
    except Exception:  # no PortAudio, or no device on this machine (CI runners)
        return False


@pytest.mark.skipif(not _has_output_device(), reason="no audio output device here")
def test_real_device_playback(tone):
    """The production path: sounddevice.OutputStream, not the fake. Play, pause, seek, next song, stop."""
    eng = AudioEngine(FFMPEG)                 # real device, its own sample rate
    try:
        eng.open(tone, duration=3.0)
        assert wait_for(lambda: eng.position > 0.8, 10), eng.state
        assert eng._stream is not None and eng._stream.active
        eng.pause()
        time.sleep(0.3)
        p = eng.position
        time.sleep(0.4)
        assert abs(eng.position - p) < 0.05
        eng.resume()
        eng.seek(2.0)
        events = []
        assert wait_for(lambda: events.extend(eng.poll()) or ("finished",) in events, 10), events
        stream = eng._stream
        eng.halt()
        eng.open(tone, duration=3.0)          # next song on the same open device
        assert eng._stream is stream
        assert wait_for(lambda: eng.position > 0.3, 10)
        samples = eng.audible_samples(2048)
        assert samples is not None and float(np.abs(samples).max()) > 0.02, "the vis tap sees the tone"
    finally:
        eng.stop()
    assert eng._stream is None

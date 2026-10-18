"""Signal processing: the 10-band equaliser and the analyser behind the visualiser.

Both run on real samples. The equaliser sits in the audio callback, so every slider
change is heard on the next block; the analyser reads the samples that are reaching
the speakers *now*, so the bars move with the music rather than ahead of it.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.signal import sosfilt

# The classic Winamp band centres, and its +/-12 dB travel.
EQ_FREQS = (60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000)
EQ_LABELS = ("60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K")
EQ_RANGE_DB = 12.0
EQ_Q = 1.2  # about one octave wide: neighbouring bands overlap the way Winamp's do


def _peaking(f0: float, gain_db: float, fs: float, q: float = EQ_Q) -> list[float]:
    """One RBJ peaking biquad as a second-order section [b0 b1 b2 1 a1 a2]."""
    f0 = min(f0, 0.45 * fs)  # keep the top band legal at low sample rates
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2.0 * q)
    cos_w0 = math.cos(w0)
    a0 = 1.0 + alpha / a
    return [
        (1.0 + alpha * a) / a0,
        (-2.0 * cos_w0) / a0,
        (1.0 - alpha * a) / a0,
        1.0,
        (-2.0 * cos_w0) / a0,
        (1.0 - alpha / a) / a0,
    ]


class Equalizer:
    """Preamp + 10 peaking filters, applied block by block with carried filter state.

    `set()` is called from the UI thread and `process()` from the audio thread. The
    whole filter state is swapped in one assignment, so the audio thread only ever
    sees a complete old state or a complete new one.
    """

    def __init__(self, samplerate: float, channels: int = 2):
        self.samplerate = float(samplerate)
        self.channels = channels
        self.enabled = False
        self.preamp_db = 0.0
        self.gains_db = [0.0] * len(EQ_FREQS)
        self._state: tuple[np.ndarray | None, np.ndarray | None, float] | None = None

    def set(self, enabled: bool, preamp_db: float, gains_db) -> None:
        self.enabled = bool(enabled)
        self.preamp_db = float(preamp_db)
        self.gains_db = [float(g) for g in gains_db]
        if not self.enabled:
            self._state = None
            return
        sections = [
            _peaking(f, g, self.samplerate)
            for f, g in zip(EQ_FREQS, self.gains_db)
            if abs(g) >= 0.05
        ]
        gain = 10.0 ** (self.preamp_db / 20.0)
        if not sections and abs(self.preamp_db) < 0.05:
            self._state = None
            return
        if not sections:
            self._state = (None, None, gain)
            return
        sos = np.asarray(sections, dtype=np.float64)
        old = self._state
        if old is not None and old[1] is not None and old[1].shape[0] == len(sections):
            zi = old[1]  # same filter count: keep the memory so a slider drag doesn't click
        else:
            zi = np.zeros((len(sections), 2, self.channels), dtype=np.float64)
        self._state = (sos, zi, gain)

    def reset(self) -> None:
        """Forget filter memory (after a seek, so the old song doesn't ring into the new spot)."""
        st = self._state
        if st is not None and st[1] is not None:
            st[1][...] = 0.0

    def process(self, block: np.ndarray) -> np.ndarray:
        st = self._state
        if st is None:
            return block
        sos, zi, gain = st
        if sos is None:
            return block * np.float32(gain)
        y, zf = sosfilt(sos, block * gain, axis=0, zi=zi)
        zi[...] = zf
        return y.astype(np.float32, copy=False)

    def response_db(self, freqs: np.ndarray) -> np.ndarray:
        """Magnitude response in dB at `freqs` (for the EQ graph and the tests)."""
        out = np.full(len(freqs), self.preamp_db if self.enabled else 0.0)
        if not self.enabled:
            return out
        w = 2.0 * np.pi * np.asarray(freqs, dtype=float) / self.samplerate
        z = np.exp(1j * w)
        for f, g in zip(EQ_FREQS, self.gains_db):
            if abs(g) < 0.05:
                continue
            b0, b1, b2, _, a1, a2 = _peaking(f, g, self.samplerate)
            h = (b0 + b1 / z + b2 / z**2) / (1 + a1 / z + a2 / z**2)
            out += 20.0 * np.log10(np.abs(h))
        return out


# Built-in presets (dB per band, preamp in dB). Shapes in the spirit of Winamp's list.
PRESETS: dict[str, tuple[float, list[float]]] = {
    "Flat": (0, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    "Classical": (0, [0, 0, 0, 0, 0, 0, -4, -4, -4, -6]),
    "Club": (0, [0, 0, 4, 3, 3, 3, 2, 0, 0, 0]),
    "Dance": (-2, [6, 4, 1, 0, 0, -3, -4, -4, 0, 0]),
    "Full Bass": (-4, [6, 6, 6, 4, 1, -2, -5, -6, -6, -6]),
    "Full Bass & Treble": (-4, [4, 3, 0, -4, -3, 1, 5, 7, 7, 7]),
    "Full Treble": (-5, [-6, -6, -6, -2, 1, 7, 10, 10, 10, 10]),
    "Headphones": (-2, [3, 7, 3, -2, -1, 1, 3, 6, 8, 9]),
    "Large Hall": (-1, [6, 6, 3, 3, 0, -3, -3, -3, 0, 0]),
    "Live": (0, [-3, 0, 2, 3, 3, 3, 2, 1, 1, 1]),
    "Party": (-1, [4, 4, 0, 0, 0, 0, 0, 0, 4, 4]),
    "Pop": (-1, [-1, 3, 4, 5, 3, 0, -1, -1, -1, -1]),
    "Reggae": (0, [0, 0, 0, -3, 0, 4, 4, 0, 0, 0]),
    "Rock": (-2, [5, 3, -3, -5, -2, 3, 6, 7, 7, 7]),
    "Soft": (0, [3, 1, 0, -1, 0, 3, 6, 7, 8, 9]),
    "Soft Rock": (0, [3, 3, 1, 0, -2, -3, -2, 0, 2, 6]),
    "Techno": (-2, [5, 4, 0, -3, -3, 0, 5, 6, 6, 5]),
    "Vocal": (-1, [-2, -3, -3, 1, 4, 4, 3, 1, 0, -2]),
}


class Visualizer:
    """Turns audible samples into Winamp-style analyser bars (with falling peaks) or a scope."""

    FFT_SIZE = 2048
    HEIGHT = 16  # pixel rows in the main-window vis box

    def __init__(self, samplerate: float):
        self.samplerate = float(samplerate)
        self._window = np.hanning(self.FFT_SIZE).astype(np.float32)
        self._norm = float(self._window.sum()) / 2.0
        self._freqs = np.fft.rfftfreq(self.FFT_SIZE, 1.0 / self.samplerate)
        self._bands_for: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        self.bars = np.zeros(0)
        self.peaks = np.zeros(0)
        self._peak_vel = np.zeros(0)

    def _bands(self, n: int):
        if n not in self._bands_for:
            top = min(16000.0, 0.48 * self.samplerate)
            edges = np.geomspace(40.0, top, n + 1)
            centres = np.sqrt(edges[:-1] * edges[1:])
            # Real music falls faster than pink noise at the top; lift it gently so the
            # treble bars move with hi-hats the way Winamp's did.
            tilt = 1.5 * np.log2(centres / 1000.0)
            self._bands_for[n] = (edges, centres, tilt)
        return self._bands_for[n]

    def levels(self, mono: np.ndarray, n_bars: int) -> np.ndarray:
        """Bar heights in [0, 1] for one frame of audio (no smoothing).

        Each bar is the energy in its slice of the spectrum (an octave-band analyser), in
        dB relative to a full-scale sine, so loud masters fill the box and silence is empty.
        """
        x = np.zeros(self.FFT_SIZE, dtype=np.float32)
        tail = mono[-self.FFT_SIZE:]
        x[-len(tail):] = tail
        power = (np.abs(np.fft.rfft(x * self._window)) / self._norm) ** 2
        edges, centres, tilt = self._bands(n_bars)
        bin_hz = self._freqs[1]
        out = np.empty(n_bars)
        for i in range(n_bars):
            lo, hi = edges[i], edges[i + 1]
            sel = (self._freqs >= lo) & (self._freqs < hi)
            if sel.sum() >= 2:
                e = float(power[sel].sum())
            else:  # band narrower than ~2 FFT bins: read the density at the centre, scale by width
                e = float(np.interp(centres[i], self._freqs, power)) * (hi - lo) / bin_hz
            out[i] = 10.0 * math.log10(e / 1.5 + 1e-12) + tilt[i]  # /1.5: Hann spreads a sine over 1.5 bins
        # -70 dB .. -6 dB fills the box: a mastered track sits ~60% up, kicks and snares hit the top.
        return np.clip((out + 70.0) / 64.0, 0.0, 1.0)

    def step(self, mono: np.ndarray | None, n_bars: int, falloff: float = 0.07) -> None:
        """Advance one display frame: bars jump up, fall at `falloff`/frame; peaks hang then drop."""
        if len(self.bars) != n_bars:
            self.bars = np.zeros(n_bars)
            self.peaks = np.zeros(n_bars)
            self._peak_vel = np.zeros(n_bars)
        target = self.levels(mono, n_bars) if mono is not None and len(mono) else np.zeros(n_bars)
        self.bars = np.maximum(target, self.bars - falloff)
        rising = self.bars >= self.peaks
        self.peaks = np.where(rising, self.bars, self.peaks)
        self._peak_vel = np.where(rising, 0.0, self._peak_vel + 0.004)
        self.peaks = np.where(rising, self.peaks, np.maximum(0.0, self.peaks - self._peak_vel))

    @staticmethod
    def scope(mono: np.ndarray | None, width: int = 76) -> np.ndarray:
        """`width` scope points in [-1, 1] from the most recent samples."""
        if mono is None or not len(mono):
            return np.zeros(width)
        seg = mono[-576:]
        idx = np.linspace(0, len(seg) - 1, width).astype(int)
        return np.clip(seg[idx] * 1.6, -1.0, 1.0)

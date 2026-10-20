"""Compose the demo's soundtrack in code: music plus sound effects timed to the video.

Everything is synthesised here, so there is nothing to license. record_demo.py logs what happens
on screen and when (clicks, typing, slides) to raw/events.json; this file turns that into a WAV.

    python demo/soundtrack.py      # uses demo/raw/events.json, writes demo/raw/soundtrack.wav
"""
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter, sosfilt

SR = 44100
RNG = np.random.default_rng(7)
HERE = Path(__file__).parent


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def secs(n):
    return np.arange(int(n * SR)) / SR


def lowpass(x, hz, order=2):
    return sosfilt(butter(order, hz, "low", fs=SR, output="sos"), x)


def highpass(x, hz, order=2):
    return sosfilt(butter(order, hz, "high", fs=SR, output="sos"), x)


def bandpass(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def noise(seconds):
    return RNG.standard_normal(int(seconds * SR))


def adsr(n, a=0.01, d=0.1, s=0.7, r=0.1):
    """An envelope n samples long: attack, decay to the sustain level, release at the end."""
    env = np.full(n, s)
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    a = min(a, n)
    env[:a] = np.linspace(0, 1, a, endpoint=False)
    d = min(d, n - a)
    env[a:a + d] = np.linspace(1, s, d, endpoint=False)
    r = min(r, n)
    env[n - r:] *= np.linspace(1, 0, r)
    return env


class Mix:
    """A stereo buffer that sounds are added into at a time in seconds."""

    def __init__(self, seconds):
        self.buf = np.zeros((int(seconds * SR) + SR, 2))

    def add(self, sound, at, gain=1.0, pan=0.0):
        start = int(at * SR)
        if start < 0 or start >= len(self.buf):
            return
        sound = sound[: len(self.buf) - start]
        left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        self.buf[start:start + len(sound), 0] += sound * gain * left * 1.414
        self.buf[start:start + len(sound), 1] += sound * gain * right * 1.414

    def add_stereo(self, left, right, at, gain=1.0):
        start = int(at * SR)
        n = min(len(left), len(self.buf) - start)
        self.buf[start:start + n, 0] += left[:n] * gain
        self.buf[start:start + n, 1] += right[:n] * gain


# ---------------------------------------------------------------- instruments

def epiano(note, length, vel=1.0):
    t = secs(length + 0.8)
    f = midi(note)
    tone = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
            + 0.08 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t * 9))
    env = np.exp(-t * 2.2) * np.minimum(1, t / 0.004)
    env[int(length * SR):] *= np.linspace(1, 0, len(t) - int(length * SR))
    return tone * env * (1 + 0.04 * np.sin(2 * np.pi * 5 * t)) * vel


def pluck(note, vel=1.0):
    t = secs(0.45)
    f = midi(note)
    tone = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 20)
    return tone * np.exp(-t * 11) * np.minimum(1, t / 0.002) * vel


def pad(notes, length):
    t = secs(length)
    out = np.zeros(len(t))
    for note in notes:
        for detune in (-0.12, 0.0, 0.12):
            f = midi(note + detune)
            for k in range(1, 7):
                out += np.sin(2 * np.pi * f * k * t + RNG.uniform(0, 6.28)) / (k * k)
    out = lowpass(out, 1400)
    return out * adsr(len(t), a=0.18, d=0.3, s=0.85, r=0.55) / (len(notes) * 4)


def bass(note, length):
    t = secs(length)
    f = midi(note)
    tone = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)
    return lowpass(tone * adsr(len(t), 0.008, 0.15, 0.6, 0.06), 700)


def kick():
    t = secs(0.35)
    freq = 45 + 75 * np.exp(-t * 30)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 9)
    return body + 0.3 * highpass(noise(0.35), 3000) * np.exp(-t * 300)


def clap():
    t = secs(0.25)
    return bandpass(noise(0.25), 1200, 4500) * np.exp(-t * 22) * 0.6


def hat(open_=False):
    t = secs(0.2)
    return highpass(noise(0.2), 7000) * np.exp(-t * (18 if open_ else 70)) * 0.5


def tick(high=True):
    """A woodblock click, for the clock in the 'before' section."""
    t = secs(0.08)
    f = 2100 if high else 1500
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2.7 * f * t)) * np.exp(-t * 90)


# ---------------------------------------------------------------- sound effects

def sfx_click():
    t = secs(0.05)
    return 0.6 * highpass(noise(0.05), 2000) * np.exp(-t * 400) + 0.5 * np.sin(2 * np.pi * 1700 * t) * np.exp(-t * 160)


def sfx_key():
    t = secs(0.04)
    lo = RNG.uniform(1500, 2500)
    return bandpass(noise(0.04), lo, lo * 2.5) * np.exp(-t * RNG.uniform(180, 260)) * RNG.uniform(0.6, 1.0)


def sfx_pop():
    t = secs(0.12)
    freq = 300 + 700 * np.exp(-t * 45)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 32)


def sweep_noise(seconds, lo, hi, rising=True):
    """Noise through a band-pass filter whose centre moves from lo to hi (or back)."""
    x = noise(seconds)
    out = np.zeros_like(x)
    block = 512
    n_blocks = len(x) // block + 1
    zi = None
    for i in range(n_blocks):
        frac = i / max(1, n_blocks - 1)
        frac = frac if rising else 1 - frac
        centre = lo * (hi / lo) ** frac
        b, a = butter(2, [centre * 0.6, min(centre * 1.6, SR / 2 - 100)], "band", fs=SR)
        if zi is None:
            zi = np.zeros(max(len(a), len(b)) - 1)
        seg = x[i * block:(i + 1) * block]
        if len(seg) == 0:
            break
        y, zi = lfilter(b, a, seg, zi=zi)
        out[i * block:i * block + len(seg)] = y
    return out


def sfx_whoosh(seconds=0.7):
    t = secs(seconds)
    env = np.sin(np.pi * np.clip(t / seconds, 0, 1)) ** 2
    return sweep_noise(seconds, 300, 4000) * env * 1.6


def sfx_stamp():
    t = secs(0.45)
    freq = 50 + 60 * np.exp(-t * 25)
    thud = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 14)
    slap = bandpass(noise(0.45), 900, 3500) * np.exp(-t * 60)
    return thud * 1.1 + slap * 0.9


def bell(f, length=1.2):
    t = secs(length)
    return sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * d)
               for m, a, d in [(1, 1, 3), (2.76, 0.4, 6), (5.4, 0.15, 10)])


def sfx_chime():
    out = np.zeros(int(1.5 * SR))
    for i, note in enumerate([76, 83]):
        b = bell(midi(note))
        out[int(i * 0.09 * SR):int(i * 0.09 * SR) + len(b)] += b
    return out * 0.5


def sfx_sparkle():
    out = np.zeros(int(1.2 * SR))
    for i, note in enumerate([84, 88, 91, 96]):
        b = bell(midi(note), 0.8) * 0.5
        out[int(i * 0.06 * SR):int(i * 0.06 * SR) + len(b)] += b
    return out * 0.4


def sfx_tick():
    t = secs(0.03)
    return np.sin(2 * np.pi * 2600 * t) * np.exp(-t * 200)


def sfx_riser(seconds=1.6):
    t = secs(seconds)
    freq = 180 * (8 ** (t / seconds))
    tone = np.sin(2 * np.pi * np.cumsum(freq) / SR) * 0.25
    return (sweep_noise(seconds, 400, 9000) * 0.9 + tone) * (t / seconds) ** 2


def sfx_impact():
    t = secs(1.6)
    freq = 38 + 60 * np.exp(-t * 8)
    boom = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 3)
    splash = lowpass(noise(1.6), 6000) * np.exp(-t * 4) * 0.35
    return boom + splash


# ---------------------------------------------------------------- music

BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
# (bass note, chord notes) for one bar each
BRIGHT = [(48, [60, 64, 67, 71]), (43, [59, 62, 67, 74]), (45, [57, 60, 64, 69]), (41, [57, 60, 65, 69])]
GLUM = [(45, [57, 60, 64]), (50, [57, 62, 65]), (45, [57, 60, 64]), (40, [56, 59, 64])]


def music(mix, start, end, style):
    bars = int(np.ceil((end - start) / BAR))
    for i in range(bars):
        t0 = start + i * BAR
        root, chord = (GLUM if style == "before" else BRIGHT)[i % 4]
        if style == "intro":
            mix.add(pad(chord, BAR + 0.6), t0, 0.55)
            for j, note in enumerate([chord[0] + 12, chord[2] + 12, chord[1] + 12]):
                mix.add(epiano(note, 0.6, 0.5), t0 + j * BEAT * 1.33, 0.10, pan=-0.3 + 0.3 * j)
        elif style == "before":
            # Sparse and a bit plodding, with a ticking clock: this part is the slow way.
            mix.add(pad(chord, BAR + 0.6), t0, 0.32)
            for b in range(4):
                mix.add(tick(b % 2 == 0), t0 + b * BEAT, 0.13, pan=0.35)
                mix.add(pluck(root + 12 if b % 2 == 0 else chord[b % len(chord)], 0.9), t0 + b * BEAT, 0.12)
            mix.add(bass(root, BAR * 0.9), t0, 0.22)
        elif style == "after":
            mix.add(pad(chord, BAR + 0.6), t0, 0.40)
            for b in range(4):
                mix.add(kick(), t0 + b * BEAT, 0.34 if b in (0, 2) else 0.16)
                if b in (1, 3):
                    mix.add(clap(), t0 + b * BEAT, 0.13, pan=0.1)
            for e in range(8):
                mix.add(hat(open_=(e % 4 == 3)), t0 + e * BEAT / 2, 0.075 if e % 2 else 0.045, pan=0.4)
                mix.add(bass(root if e % 4 != 3 else root + 7, BEAT / 2 * 0.9), t0 + e * BEAT / 2, 0.22)
                arp = chord[[0, 1, 2, 3, 2, 1, 2, 3][e] % len(chord)] + 12
                mix.add(epiano(arp, BEAT / 2, 0.8 if e % 2 == 0 else 0.6), t0 + e * BEAT / 2, 0.075,
                        pan=-0.4 + 0.8 * (e / 7))
    return bars


def outro(mix, start, seconds):
    root, chord = BRIGHT[0]
    mix.add(bass(root, seconds), start, 0.25)
    mix.add(pad(chord + [72], seconds), start, 0.6)
    for j, note in enumerate(chord + [72, 76]):
        mix.add(epiano(note + 12, seconds - j * 0.12, 0.6), start + j * 0.12, 0.08, pan=-0.5 + 0.2 * j)
    mix.add(bell(midi(84), 2.5) * 0.3, start, 0.25)


# ---------------------------------------------------------------- put it together

SFX = {
    "click": (sfx_click, 0.75), "key": (sfx_key, 0.35), "pop": (sfx_pop, 0.30), "whoosh": (sfx_whoosh, 0.45),
    "swoosh": (lambda: sfx_whoosh(0.4), 0.32), "stamp": (sfx_stamp, 0.9), "chime": (sfx_chime, 0.40),
    "sparkle": (sfx_sparkle, 0.45), "tick": (sfx_tick, 0.25), "impact": (sfx_impact, 0.75),
}


def build(events_file=HERE / "raw" / "events.json", out=HERE / "raw" / "soundtrack.wav"):
    data = json.loads(Path(events_file).read_text())
    marks, duration = data["marks"], data["duration"]
    mix = Mix(duration)

    music(mix, 0.0, marks["before"], "intro")
    music(mix, marks["before"], marks["after"] - 0.2, "before")
    music(mix, marks["after"], marks["end"], "after")
    outro(mix, marks["end"], duration - marks["end"] + 0.5)
    # Fade the music under each section change so the bars do not collide.
    for edge in (marks["before"], marks["after"], marks["end"]):
        a, b = int((edge - 0.25) * SR), int((edge + 0.02) * SR)
        mix.buf[a:b] *= np.linspace(1, 0.2, b - a)[:, None]
    mix.add(sfx_riser(), marks["after"] - 1.6, 0.5)
    mix.add(sfx_impact(), marks["after"], 0.75)

    for event in data["events"]:
        make, gain = SFX[event["kind"]]
        mix.add(make(), event["t"], gain * event.get("gain", 1.0), pan=event.get("pan", 0.0))

    buf = mix.buf[: int(duration * SR)]
    fade = int(1.5 * SR)
    buf[-fade:] *= np.linspace(1, 0, fade)[:, None]
    buf[: int(0.3 * SR)] *= np.linspace(0, 1, int(0.3 * SR))[:, None]
    buf = np.tanh(buf * 0.9)  # gentle limiter
    buf /= np.max(np.abs(buf)) / 0.89
    wavfile.write(out, SR, (buf * 32767).astype(np.int16))
    return out


if __name__ == "__main__":
    print("Wrote", build())

"""Sound for STARFALL KEEPER: voices (Kokoro TTS), synthesized score and SFX.

Everything here is generated: there are no sampled instruments. The score is
built from tiny additive / Karplus-Strong / subtractive synths and a
convolution reverb made from shaped noise.
"""
import hashlib
import json
import math
import os

import numpy as np
from scipy import signal

SR = 48000
RNG = np.random.default_rng(7)


# ======================================================================
#  helpers
# ======================================================================
def secs(n):
    return int(round(n * SR))


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def env_adsr(n, a=0.01, d=0.1, s=0.7, r=0.2, sr=SR):
    a_n, d_n, r_n = max(1, int(a * sr)), max(1, int(d * sr)), max(1, int(r * sr))
    s_n = max(0, n - a_n - d_n - r_n)
    e = np.concatenate([np.linspace(0, 1, a_n, endpoint=False),
                        np.linspace(1, s, d_n, endpoint=False),
                        np.full(s_n, s),
                        np.linspace(s, 0, r_n)])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def lp(x, fc, order=2):
    b, a = signal.butter(order, min(fc / (SR / 2), 0.99), "low")
    return signal.lfilter(b, a, x)


def hp(x, fc, order=2):
    b, a = signal.butter(order, min(fc / (SR / 2), 0.99), "high")
    return signal.lfilter(b, a, x)


def bp(x, f1, f2, order=2):
    b, a = signal.butter(order, [f1 / (SR / 2), min(f2 / (SR / 2), 0.99)], "band")
    return signal.lfilter(b, a, x)


def noise(n):
    return RNG.standard_normal(n)


def brown(n):
    x = np.cumsum(RNG.standard_normal(n))
    x = hp(x, 20)
    return x / (np.abs(x).max() + 1e-9)


def pink(n):
    # Voss-ish via filtering white noise
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1, -2.494956002, 2.017265875, -0.522189400]
    return signal.lfilter(b, a, noise(n)) * 4


class Bus:
    """Stereo timeline buffer."""

    def __init__(self, length_s):
        self.n = secs(length_s) + SR
        self.buf = np.zeros((2, self.n), dtype=np.float64)

    def add(self, t, sig, gain=1.0, pan=0.0):
        i = secs(t)
        if i >= self.n or len(sig) == 0:
            return
        if i < 0:
            sig = sig[-i:] if sig.ndim == 1 else sig[:, -i:]
            i = 0
        if sig.ndim == 1:
            ang = (pan + 1) * math.pi / 4
            st = np.vstack([sig * math.cos(ang), sig * math.sin(ang)])
        else:
            st = sig
        m = min(st.shape[1], self.n - i)
        self.buf[:, i:i + m] += st[:, :m] * gain


# ======================================================================
#  instruments
# ======================================================================
def piano(m, dur, vel=0.8, bright=1.0):
    f = midi_hz(m)
    n = secs(dur + 1.2)
    t = np.arange(n) / SR
    out = np.zeros(n)
    B = 0.0003
    for k in range(1, 9):
        fk = f * k * math.sqrt(1 + B * k * k)
        if fk > SR / 2.2:
            break
        amp = (1.0 / k ** 1.4) * (bright if k > 2 else 1.0)
        dec = 1.6 + 0.9 * k + f / 600
        out += amp * np.sin(2 * math.pi * fk * t + k) * np.exp(-t * dec / 2.2)
    rel = np.ones(n)
    r0 = secs(dur)
    rel[r0:] = np.exp(-np.arange(n - r0) / (SR * 0.18))
    att = np.minimum(1, t / 0.004)
    hammer = lp(noise(n), 3000) * np.exp(-t * 90) * 0.15
    return (out * rel * att + hammer) * vel * 0.32


def bell(m, dur=1.5, vel=0.6):
    f = midi_hz(m)
    n = secs(dur)
    t = np.arange(n) / SR
    parts = [(1, 1.0, 2.2), (2.0, 0.5, 3.2), (2.76, 0.35, 4.0), (5.4, 0.2, 6.5), (8.9, 0.1, 9.0)]
    out = sum(a * np.sin(2 * math.pi * f * r * t) * np.exp(-t * d) for r, a, d in parts)
    return out * np.minimum(1, t / 0.002) * vel * 0.25


def pluck(m, dur=1.6, vel=0.7, damp=0.996):
    f = midi_hz(m)
    N = int(SR / f)
    n = secs(dur)
    exc = np.zeros(n)
    exc[:N] = lp(RNG.uniform(-1, 1, N), 4000)
    a = np.zeros(N + 2)
    a[0] = 1
    a[N] = -0.5 * damp
    a[N + 1] = -0.5 * damp
    y = signal.lfilter([1.0], a, exc)
    y *= np.minimum(1, np.arange(n) / (SR * 0.002))
    y[-secs(0.05):] *= np.linspace(1, 0, secs(0.05))
    return y * vel * 0.5


def saw(f, n, detune=0.0, phase=0.0):
    t = np.arange(n) / SR
    ph = (f * (1 + detune) * t + phase) % 1.0
    return 2 * ph - 1


def pad(ms, dur, vel=0.5, cutoff=1800, attack=0.8, release=1.2, bright=False):
    n = secs(dur + release)
    out = np.zeros(n)
    for m in ms:
        f = midi_hz(m)
        for d in (-0.004, 0.0, 0.005):
            out += saw(f, n, d, RNG.random())
    out = lp(out, cutoff if not bright else cutoff * 2, 2)
    e = env_adsr(n, attack, 0.3, 0.85, release)
    return out * e * vel * 0.06


def strings(ms, dur, vel=0.5, attack=0.6, release=1.0):
    n = secs(dur + release)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in ms:
        f = midi_hz(m)
        vib = 1 + 0.004 * np.sin(2 * math.pi * 5.2 * t + m)
        ph = np.cumsum(f * vib) / SR
        for d in (-0.003, 0.003):
            out += 2 * ((ph * (1 + d) + RNG.random()) % 1.0) - 1
    out = lp(out, 2600, 2)
    return out * env_adsr(n, attack, 0.2, 0.9, release) * vel * 0.05


def lead(m, dur, vel=0.6):
    f = midi_hz(m)
    n = secs(dur + 0.15)
    t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * math.pi * 5.5 * t) * np.minimum(1, t / 0.25)
    ph = np.cumsum(f * vib) / SR
    x = 0.6 * (2 * (ph % 1) - 1) + 0.4 * np.sign(np.sin(2 * math.pi * ph))
    x = lp(x, 3200)
    return x * env_adsr(n, 0.01, 0.1, 0.75, 0.12) * vel * 0.16


def bass(m, dur, vel=0.7):
    f = midi_hz(m)
    n = secs(dur + 0.05)
    t = np.arange(n) / SR
    x = np.sin(2 * math.pi * f * t) + 0.35 * np.sin(4 * math.pi * f * t) + 0.15 * saw(f, n)
    x = np.tanh(x * 1.5)
    return lp(x, 900) * env_adsr(n, 0.005, 0.12, 0.7, 0.05) * vel * 0.3


def kick(vel=1.0):
    n = secs(0.45)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    ph = np.cumsum(f) / SR
    return np.sin(2 * math.pi * ph) * np.exp(-t * 8) * vel * 0.9


def snare(vel=1.0):
    n = secs(0.3)
    t = np.arange(n) / SR
    x = hp(noise(n), 1200) * np.exp(-t * 18) * 0.6 + np.sin(2 * math.pi * 190 * t) * np.exp(-t * 25) * 0.5
    return x * vel * 0.5


def hat(vel=1.0, open_=False):
    n = secs(0.25 if open_ else 0.06)
    t = np.arange(n) / SR
    return hp(noise(n), 7000) * np.exp(-t * (12 if open_ else 70)) * vel * 0.22


def crash(vel=1.0):
    n = secs(2.0)
    t = np.arange(n) / SR
    return hp(noise(n), 4000) * np.exp(-t * 2.2) * vel * 0.25


def timpani(m=38, vel=1.0):
    n = secs(1.6)
    t = np.arange(n) / SR
    f = midi_hz(m)
    x = np.sin(2 * math.pi * f * t) * np.exp(-t * 2.5) + 0.4 * np.sin(2 * math.pi * f * 1.5 * t) * np.exp(-t * 4)
    x += lp(noise(n), 600) * np.exp(-t * 20) * 0.5
    return x * vel * 0.6


def brass(ms, dur, vel=0.7):
    n = secs(dur + 0.3)
    out = np.zeros(n)
    for m in ms:
        f = midi_hz(m)
        out += saw(f, n, -0.003) + saw(f, n, 0.003)
    t = np.arange(n) / SR
    cut = 600 + 2400 * np.exp(-t * 3)
    # cheap time-varying filter: blend two filtered copies
    lo, hi = lp(out, 600), lp(out, 3000)
    w = (cut - 600) / 2400
    x = lo * (1 - w) + hi * w
    return x * env_adsr(n, 0.04, 0.3, 0.6, 0.3) * vel * 0.07


# ======================================================================
#  reverb
# ======================================================================
_IR = {}


def reverb_ir(rt=2.2, tone=5000):
    key = (rt, tone)
    if key not in _IR:
        n = secs(rt * 1.2)
        t = np.arange(n) / SR
        decay = np.exp(-6.9 * t / rt)
        irs = []
        for ch in range(2):
            x = noise(n) * decay
            x = lp(x, tone)
            x[:secs(0.012)] *= np.linspace(0, 1, secs(0.012))
            irs.append(x / np.sqrt(np.sum(x ** 2)))
        _IR[key] = np.vstack(irs)
    return _IR[key]


def add_reverb(st, wet=0.3, rt=2.2, tone=5000):
    ir = reverb_ir(rt, tone)
    mono = st.mean(axis=0)
    out = np.vstack([signal.fftconvolve(mono, ir[c])[:st.shape[1]] for c in range(2)])
    return st * (1 - wet * 0.5) + out * wet


# ======================================================================
#  SFX
# ======================================================================
def sfx_waves(L, intensity=1.0):
    n = secs(L)
    out = []
    for ch in range(2):
        x = lp(brown(n) * 0.6 + pink(n) * 0.02, 900)
        t = np.arange(n) / SR
        swell = 0.55 + 0.45 * np.sin(2 * math.pi * 0.11 * t + ch * 0.8) ** 2
        out.append(x * swell)
    st = np.vstack(out)
    return st / (np.abs(st).max() + 1e-9) * 0.25 * intensity


def sfx_wind(L, intensity=1.0):
    n = secs(L)
    t = np.arange(n) / SR
    out = []
    for ch in range(2):
        x = bp(pink(n), 250, 1400)
        mod = 0.5 + 0.5 * np.sin(2 * math.pi * 0.07 * t + ch) * np.sin(2 * math.pi * 0.023 * t)
        out.append(x * mod)
    st = np.vstack(out)
    return st / (np.abs(st).max() + 1e-9) * 0.12 * intensity


def sfx_rain(L, intensity=1.0):
    n = secs(L)
    st = np.vstack([bp(noise(n), 1500, 9000) for _ in range(2)])
    drops = np.zeros((2, n))
    drop = hp(noise(600), 3000) * np.exp(-np.arange(600) / 80) * 0.6
    for i in range(int(L * 30)):
        p = RNG.integers(0, n - 2000)
        drops[RNG.integers(0, 2), p:p + 600] += drop * (0.5 + RNG.random())
    st = st / (np.abs(st).max() + 1e-9) * 0.05 + drops * 0.05
    return st * intensity


def sfx_whoosh(dur=1.6, up=True, gain=1.0):
    n = secs(dur)
    x = noise(n)
    out = np.zeros(n)
    blocks = 40
    zi = None
    bl = n // blocks
    for i in range(blocks):
        f = i / (blocks - 1)
        fc = (400 + 5000 * f) if up else (5400 - 5000 * f)
        b, a = signal.butter(2, [max(fc * 0.6, 60) / (SR / 2), min(fc * 1.4, SR / 2.2) / (SR / 2)], "band")
        seg = x[i * bl:(i + 1) * bl]
        if zi is None:
            zi = signal.lfilter_zi(b, a) * 0
        y, zi = signal.lfilter(b, a, seg, zi=zi)
        out[i * bl:i * bl + len(y)] = y
    e = np.sin(np.linspace(0, math.pi, n)) ** 1.5
    return out * e * gain * 0.8


def sfx_boom(gain=1.0):
    n = secs(3.0)
    t = np.arange(n) / SR
    f = 30 + 70 * np.exp(-t * 4)
    x = np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t * 1.4)
    x += lp(noise(n), 300) * np.exp(-t * 2.0) * 0.8
    return x * gain * 0.8


def sfx_splash(gain=1.0):
    n = secs(2.0)
    t = np.arange(n) / SR
    x = bp(noise(n), 400, 5000) * np.exp(-t * 3.0) * 0.6
    for i in range(40):
        p = int(RNG.uniform(0.1, 1.6) * SR)
        f = RNG.uniform(600, 2200)
        ln = secs(0.06)
        tt = np.arange(ln) / SR
        if p + ln < n:
            x[p:p + ln] += np.sin(2 * math.pi * f * (1 + tt * 8) * tt) * np.exp(-tt * 60) * 0.25
    return x * gain


def sfx_sparkle(n_notes=7, spread=0.08, base=84, gain=1.0):
    scale = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24]
    out = np.zeros(secs(n_notes * spread + 1.6))
    for i in range(n_notes):
        m = base + scale[i % len(scale)]
        s = bell(m, 1.4, 0.5 + 0.3 * RNG.random())
        p = secs(i * spread)
        out[p:p + len(s)] += s
    return out * gain


def sfx_shimmer(dur=4.0, gain=1.0):
    n = secs(dur)
    out = np.zeros(n + secs(1.5))
    for i in range(int(dur * 9)):
        m = int(RNG.choice([79, 81, 83, 86, 88, 90, 91, 93, 95, 98]))
        s = bell(m, 1.4, 0.25 + 0.25 * RNG.random())
        p = secs(RNG.random() * dur)
        out[p:p + len(s)] += s * (0.3 + 0.7 * p / n)
    sw = sfx_whoosh(dur, True, 0.25)
    out[:len(sw)] += sw
    return out * gain


def sfx_thunder(gain=1.0):
    n = secs(4.5)
    t = np.arange(n) / SR
    crack = hp(noise(n), 1500) * np.exp(-t * 14) * 0.5
    rumble = lp(brown(n), 250) * (np.exp(-t * 0.9) * (0.7 + 0.3 * np.sin(2 * math.pi * 3 * t) ** 2))
    return (crack + rumble * 1.4) * gain * 0.7


def sfx_heartbeat(gain=1.0):
    n = secs(1.0)
    out = np.zeros(n)
    for off, v in ((0.0, 1.0), (0.22, 0.7)):
        k = lp(kick(v), 200)
        p = secs(off)
        out[p:p + len(k)] += k[:n - p]
    return out * gain


def sfx_steps(dur, rate=0.32, gain=1.0):
    n = secs(dur)
    out = np.zeros(n)
    t = 0.0
    while t < dur - 0.15:
        ln = secs(0.12)
        s = lp(noise(ln), 1800) * np.exp(-np.arange(ln) / (SR * 0.03))
        p = secs(t)
        out[p:p + ln] += s[:max(0, min(ln, n - p))] * (0.7 + 0.3 * RNG.random())
        t += rate * (0.9 + 0.2 * RNG.random())
    return out * gain * 0.3


def sfx_ting(gain=1.0):
    a = bell(93, 1.6, 0.7)
    b = bell(100, 1.6, 0.5)
    out = np.zeros(len(a) + secs(0.09))
    out[:len(a)] += a
    out[secs(0.09):secs(0.09) + len(b)] += b
    return out * gain


def sfx_hit(gain=1.0):
    k = kick(1.0)
    c = crash(0.6)
    out = np.zeros(len(c))
    out[:len(k)] += k
    out += c
    return out * gain


# ======================================================================
#  score
# ======================================================================
class Score:
    def __init__(self, L):
        self.bus = Bus(L)
        self.L = L

    def add(self, t, sig, gain=1.0, pan=0.0):
        if t < self.L:
            self.bus.add(t, sig, gain, pan)


def _fade(st, fade_in=0.5, fade_out=1.5):
    n = st.shape[1]
    fi, fo = secs(fade_in), secs(fade_out)
    if fi > 0:
        st[:, :fi] *= np.linspace(0, 1, fi)
    if fo > 0 and fo < n:
        st[:, -fo:] *= np.linspace(1, 0, fo)
    return st


def cue_night(L):
    """Gentle piano under the cold open. D major, 72 bpm."""
    s = Score(L)
    beat = 60 / 72
    bar = 4 * beat
    chords = [[50, 57, 61, 66], [47, 54, 57, 62], [43, 50, 54, 59], [45, 52, 57, 61]]
    pat = [0, 1, 2, 3, 2, 1, 3, 2]
    mel = [(0, 78, 1.5), (1.5, 76, 0.5), (2, 74, 2), (4, 71, 1.5), (5.5, 73, 0.5), (6, 74, 2),
           (8, 74, 1), (9, 76, 1), (10, 78, 1.5), (11.5, 81, 0.5), (12, 76, 4)]
    nb = int(L / bar) + 1
    for b in range(nb):
        ch = chords[b % 4]
        t0 = b * bar
        s.add(t0, piano(ch[0] - 12, bar, 0.5), 1.0, -0.1)
        for i, k in enumerate(pat):
            m = ch[k] + (12 if i in (3, 6) else 0)
            s.add(t0 + i * beat / 2, piano(m, beat * 0.9, 0.35 + 0.1 * (i == 0)), 1.0, 0.2 * math.sin(i))
        s.add(t0, pad([x + 12 for x in ch[1:]], bar, 0.35, 1200, 1.2, 1.5), 1.0)
        if b >= 2 and (b // 4) % 2 == 0:
            for (bt, m, ln) in mel:
                if (b % 4) * 4 <= bt < (b % 4 + 1) * 4:
                    s.add(t0 + (bt - (b % 4) * 4) * beat, bell(m, ln * beat + 1.0, 0.5), 1.0, 0.25)
    return _fade(add_reverb(s.bus.buf[:, :secs(L)], 0.45, 2.6), 1.5, 2.5)


def cue_op(L):
    """Upbeat opening theme. D major, 150 bpm."""
    s = Score(L)
    beat = 60 / 150
    bar = 4 * beat
    prog = [[43, 55, 59, 62], [45, 57, 61, 64], [42, 54, 57, 61], [47, 59, 62, 66]]
    mel = [(0, 74, 1.5), (1.5, 76, 0.5), (2, 78, 1), (3, 79, 1), (4, 81, 1.5), (5.5, 79, 0.5), (6, 78, 1),
           (7, 76, 1), (8, 78, 1.5), (9.5, 76, 0.5), (10, 73, 1), (11, 76, 1), (12, 74, 2), (14, 71, 1),
           (15, 73, 1), (16, 74, 1.5), (17.5, 76, 0.5), (18, 78, 1), (19, 79, 1), (20, 81, 1), (21, 83, 1),
           (22, 85, 1), (23, 86, 1), (24, 86, 4)]
    intro_bars = 2
    nb = int(L / bar) + 1
    # intro riser
    s.add(0, sfx_whoosh(bar * intro_bars, True, 0.5), 1.0)
    for b in range(intro_bars):
        for i in range(4):
            s.add(b * bar + i * beat, kick(0.8), 1.0)
            if b == 1:
                s.add(b * bar + i * beat + beat / 2, snare(0.4 + 0.15 * i), 1.0)
    for b in range(intro_bars, nb):
        t0 = b * bar
        bi = b - intro_bars
        final = bi >= 6
        ch = [50, 62, 66, 69] if final else prog[bi % 4]
        if bi == 0 or bi == 6:
            s.add(t0, crash(0.9), 1.0, 0.3)
        for i in range(4):
            s.add(t0 + i * beat, kick(1.0 if i % 2 == 0 else 0.7), 1.0)
            if i % 2 == 1:
                s.add(t0 + i * beat, snare(0.9), 1.0, 0.1)
        for i in range(8):
            s.add(t0 + i * beat / 2, hat(0.6 + 0.3 * (i % 2 == 0)), 1.0, 0.35)
            s.add(t0 + i * beat / 2, bass(ch[0] - (0 if ch[0] < 45 else 12), beat / 2 * 0.9, 0.8), 1.0)
        s.add(t0, pad(ch[1:], bar, 0.6, 2400, 0.02, 0.3), 1.0)
        for (bt, m, ln) in mel:
            if bi * 4 <= bt < (bi + 1) * 4:
                s.add(t0 + (bt - bi * 4) * beat, lead(m, ln * beat * 0.95, 0.75), 1.0, -0.1)
                s.add(t0 + (bt - bi * 4) * beat, bell(m + 12, 0.8, 0.25), 1.0, 0.3)
    return _fade(add_reverb(s.bus.buf[:, :secs(L)], 0.25, 1.6), 0.05, 1.5)


def cue_mystery(L):
    """Hushed B minor pads with celesta for the beach."""
    s = Score(L)
    bar = 4.0
    chords = [[47, 54, 59, 62], [43, 50, 55, 59], [40, 52, 55, 59], [42, 54, 58, 61]]
    scale = [71, 73, 74, 76, 78, 79, 81, 83, 86]
    for b in range(int(L / bar) + 1):
        ch = chords[b % 4]
        s.add(b * bar, pad(ch, bar, 0.55, 1100, 1.5, 2.0), 1.0)
        s.add(b * bar, bass(ch[0] - 12, bar * 0.9, 0.4), 1.0)
        for k in range(4):
            if RNG.random() < 0.8:
                s.add(b * bar + k + RNG.random() * 0.3, bell(int(RNG.choice(scale)) + 12, 2.0, 0.35), 1.0,
                      RNG.uniform(-0.6, 0.6))
    return _fade(add_reverb(s.bus.buf[:, :secs(L)], 0.55, 3.0), 2.0, 2.0)


def cue_reveal(L):
    """Bright D major swell as Lumi appears."""
    s = Score(L)
    bar = 3.2
    chords = [[50, 57, 62, 66, 69], [49, 57, 61, 64, 69], [47, 54, 59, 62, 66], [43, 55, 59, 62, 67]]
    for b in range(int(L / bar) + 1):
        ch = chords[b % 4]
        s.add(b * bar, strings(ch, bar, 0.7, 0.8, 1.5), 1.0)
        s.add(b * bar, pad([m + 12 for m in ch[1:]], bar, 0.35, 3000, 0.8, 1.5), 1.0)
        for i in range(8):
            s.add(b * bar + i * bar / 8, bell(ch[i % len(ch)] + 24, 1.2, 0.25), 1.0, 0.5 * math.sin(i))
    return _fade(add_reverb(s.bus.buf[:, :secs(L)], 0.5, 3.0), 1.0, 2.5)


def cue_warm(L):
    """Plucked guitar arpeggios inside the lighthouse. G major, 84 bpm."""
    s = Score(L)
    beat = 60 / 84
    bar = 4 * beat
    chords = [[43, 50, 55, 59, 62], [42, 50, 54, 57, 62], [40, 47, 52, 55, 59], [36, 48, 52, 55, 60]]
    pat = [0, 2, 3, 4, 3, 2, 1, 3]
    for b in range(int(L / bar) + 1):
        ch = chords[b % 4]
        for i, k in enumerate(pat):
            s.add(b * bar + i * beat / 2, pluck(ch[k], 1.4, 0.55 if i else 0.75), 1.0, 0.3 * math.sin(i * 1.3))
        s.add(b * bar, pad([m + 12 for m in ch[2:]], bar, 0.25, 900, 1.0, 1.5), 1.0)
    return _fade(add_reverb(s.bus.buf[:, :secs(L)], 0.3, 1.4, 4000), 1.5, 1.5)


def cue_tension(L):
    s = Score(L)
    n = secs(L)
    t = np.arange(n) / SR
    drone = (np.sin(2 * math.pi * midi_hz(38) * t) + 0.6 * np.sin(2 * math.pi * midi_hz(39) * t)) * 0.12
    drone *= np.minimum(1, t / 2.0)
    s.add(0, drone, 1.0)
    s.add(0, strings([62, 63, 68], L, 0.5, L * 0.8, 0.5), 1.0)
    for k in range(int(L / 1.1)):
        s.add(k * 1.1 + 0.3, sfx_heartbeat(0.5 + 0.1 * k), 1.0)
    return _fade(add_reverb(s.bus.buf[:, :secs(L)], 0.4, 2.5), 0.5, 0.4)


def cue_tender(L):
    """Piano + strings for the balcony promise. D major, 66 bpm."""
    s = Score(L)
    beat = 60 / 66
    bar = 4 * beat
    chords = [[50, 57, 62, 66], [49, 57, 61, 64], [47, 54, 59, 62], [45, 54, 57, 61],
              [43, 55, 59, 62], [42, 54, 57, 62], [40, 55, 59, 64], [45, 52, 57, 61]]
    mel = [(0, 78, 2), (2, 76, 1), (3, 74, 1), (4, 76, 3), (7, 73, 1), (8, 74, 2), (10, 73, 1), (11, 71, 1),
           (12, 73, 3), (15, 69, 1), (16, 71, 2), (18, 74, 1), (19, 79, 1), (20, 78, 2), (22, 74, 2),
           (24, 76, 2), (26, 74, 1), (27, 76, 1), (28, 76, 4)]
    for b in range(int(L / bar) + 1):
        ch = chords[b % 8]
        t0 = b * bar
        s.add(t0, piano(ch[0] - 12, bar, 0.45), 1.0)
        for i in range(4):
            s.add(t0 + i * beat, piano(ch[1 + i % 3] + (12 if i == 2 else 0), beat, 0.3), 1.0, 0.2)
        s.add(t0, strings(ch[1:], bar, 0.5 + 0.1 * (b > 3), 1.0, 1.4), 1.0)
        bi = b % 8
        for (bt, m, ln) in mel:
            if bi * 4 <= bt < (bi + 1) * 4:
                s.add(t0 + (bt - bi * 4) * beat, piano(m, ln * beat, 0.55, 1.2), 1.0, -0.15)
    return _fade(add_reverb(s.bus.buf[:, :secs(L)], 0.45, 2.8), 2.0, 3.0)


def cue_villain(L):
    """Low brass, timpani and drone. D minor, 80 bpm."""
    s = Score(L)
    beat = 60 / 80
    bar = 4 * beat
    chords = [[38, 50, 53, 57], [34, 46, 50, 53], [33, 45, 49, 52], [38, 50, 53, 57]]
    n = secs(L)
    t = np.arange(n) / SR
    s.add(0, (np.sin(2 * math.pi * midi_hz(26) * t) * 0.2 + lp(brown(n), 120) * 0.15) * np.minimum(1, t), 1.0)
    for b in range(int(L / bar) + 1):
        ch = chords[b % 4]
        t0 = b * bar
        s.add(t0, brass(ch, bar * 0.6, 0.9), 1.0)
        s.add(t0, timpani(ch[0], 1.0), 1.0)
        s.add(t0 + beat * 2.5, timpani(ch[0], 0.6), 1.0)
        s.add(t0, pad([m + 24 for m in ch[1:]], bar, 0.25, 800, 1.0, 1.0), 1.0)
    return _fade(add_reverb(s.bus.buf[:, :secs(L)], 0.5, 3.2, 3000), 0.3, 2.0)


def cue_ed(L):
    """Slow ending ballad using the night-theme melody."""
    s = Score(L)
    beat = 60 / 68
    bar = 4 * beat
    chords = [[50, 57, 61, 66], [47, 54, 57, 62], [43, 50, 54, 59], [45, 52, 57, 61]]
    mel = [(0, 78, 1.5), (1.5, 76, 0.5), (2, 74, 2), (4, 71, 1.5), (5.5, 73, 0.5), (6, 74, 2),
           (8, 74, 1), (9, 76, 1), (10, 78, 1.5), (11.5, 81, 0.5), (12, 76, 4)]
    for b in range(int(L / bar) + 1):
        ch = chords[b % 4]
        t0 = b * bar
        s.add(t0, piano(ch[0] - 12, bar, 0.5), 1.0)
        for i, k in enumerate([0, 1, 2, 3, 2, 1, 3, 2]):
            s.add(t0 + i * beat / 2, piano(ch[k] + 12 * (i == 3), beat, 0.3), 1.0, 0.25 * math.sin(i))
        s.add(t0, strings(ch[1:], bar, 0.55, 1.2, 1.4), 1.0)
        for (bt, m, ln) in mel:
            if (b % 4) * 4 <= bt < (b % 4 + 1) * 4:
                s.add(t0 + (bt - (b % 4) * 4) * beat, piano(m, ln * beat, 0.55, 1.3), 1.0, -0.1)
                if b >= 4:
                    s.add(t0 + (bt - (b % 4) * 4) * beat, bell(m + 12, ln * beat + 0.8, 0.25), 1.0, 0.3)
    return _fade(add_reverb(s.bus.buf[:, :secs(L)], 0.45, 2.8), 1.5, 4.0)


def cue_sting(L):
    """Rising tension under the falling-star moment."""
    s = Score(L)
    s.add(0, strings([62, 69, 74, 78], L, 0.6, L * 0.7, 0.4), 1.0)
    s.add(0, sfx_shimmer(L, 0.4), 1.0)
    return _fade(add_reverb(s.bus.buf[:, :secs(L)], 0.5, 2.5), 0.3, 0.5)


CUES = {
    "night": cue_night, "op": cue_op, "mystery": cue_mystery, "reveal": cue_reveal,
    "warm": cue_warm, "tension": cue_tension, "tender": cue_tender, "villain": cue_villain,
    "ed": cue_ed, "sting": cue_sting,
}

SFX = {
    "whoosh": lambda: sfx_whoosh(1.4, True, 0.9),
    "whoosh_down": lambda: sfx_whoosh(1.2, False, 0.9),
    "boom": sfx_boom, "splash": sfx_splash, "sparkle": sfx_sparkle, "shimmer": sfx_shimmer,
    "thunder": sfx_thunder, "heartbeat": sfx_heartbeat, "ting": sfx_ting, "hit": sfx_hit,
}

AMBIENCE = {"waves": sfx_waves, "wind": sfx_wind, "rain": sfx_rain}


# ======================================================================
#  voices
# ======================================================================
VOICES = {
    # speaker: (kokoro voice, speed, pitch factor, reverb wet)
    "mio": ("af_heart", 1.02, 1.0, 0.12),
    "lumi": ("af_nicole", 0.88, 1.0, 0.25),
    "genzo": ("bm_george", 0.9, 1.0, 0.12),
    "collector": ("bm_lewis", 0.85, 0.8, 0.45),
}

_KOKORO = None


def kokoro():
    global _KOKORO
    if _KOKORO is None:
        from kokoro_onnx import Kokoro
        mdir = os.environ.get("KOKORO_DIR", os.path.join(os.path.dirname(__file__), "..", "models"))
        _KOKORO = Kokoro(os.path.join(mdir, "kokoro-v1.0.onnx"), os.path.join(mdir, "voices-v1.0.bin"))
    return _KOKORO


def synth_line(speaker, text, cache_dir):
    """Returns mono float array at SR (48k). Cached on disk."""
    voice, speed, pitch, _ = VOICES[speaker]
    key = hashlib.sha1(f"{voice}|{speed}|{pitch}|{text}".encode()).hexdigest()[:16]
    path = os.path.join(cache_dir, f"{speaker}_{key}.npy")
    if os.path.exists(path):
        return np.load(path)
    samples, sr = kokoro().create(text, voice=voice, speed=speed, lang="en-us" if voice[0] == "a" else "en-gb")
    x = np.asarray(samples, dtype=np.float64)
    up = 2 if sr == 24000 else SR / sr
    x = signal.resample_poly(x, int(up), 1) if up == 2 else signal.resample(x, int(len(x) * SR / sr))
    if pitch != 1.0:
        # lower pitch (and tempo) by stretching
        x = signal.resample(x, int(len(x) / pitch))
    # trim silence
    a = np.abs(x)
    idx = np.where(a > 0.01)[0]
    if len(idx):
        x = x[max(0, idx[0] - secs(0.02)):min(len(x), idx[-1] + secs(0.08))]
    x = x / (np.abs(x).max() + 1e-9) * 0.8
    os.makedirs(cache_dir, exist_ok=True)
    np.save(path, x)
    return x


def lip_envelope(x, fps=24):
    """Per-frame mouth openness 0..1 from the voice waveform."""
    hop = SR // fps
    n = len(x) // hop + 1
    env = np.zeros(n)
    for i in range(n):
        seg = x[i * hop:(i + 1) * hop]
        if len(seg):
            env[i] = np.sqrt(np.mean(seg ** 2))
    ref = np.percentile(env[env > 0], 90) if np.any(env > 0) else 1.0
    env = np.clip(env / (ref + 1e-9), 0, 1.2)
    env = np.where(env < 0.12, 0, env)
    # make the mouth flap a bit: emphasise changes
    out = np.convolve(env, [0.25, 0.5, 0.25], mode="same")
    return np.clip(out, 0, 1).tolist()


def master(st):
    st = st - st.mean(axis=1, keepdims=True)
    peak = np.abs(st).max() + 1e-9
    st = st / peak * 1.4
    st = np.tanh(st) / np.tanh(1.4)
    return st * 0.92


def write_wav(path, st):
    import soundfile as sf
    sf.write(path, st.T.astype(np.float32), SR, subtype="PCM_16")


def save_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)

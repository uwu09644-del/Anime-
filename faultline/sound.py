"""FAULTLINE score, SFX, ambience and voice processing (all synthesized)."""
import math

import numpy as np
from scipy import signal

import audio as A
from audio import (RNG, SR, Bus, add_reverb, bass, bell, brown, crash, env_adsr, hat, hp, kick, lp, bp,
                   midi_hz, noise, pad, piano, pink, saw, secs, snare, strings, _fade)


# ======================================================================
#  instruments
# ======================================================================
def dist_chord(ms, dur, vel=0.7, cutoff=2600):
    """Distorted power-chord guitar-ish synth."""
    n = secs(dur + 0.2)
    x = np.zeros(n)
    for m in ms:
        f = midi_hz(m)
        for d in (-0.006, 0.0, 0.007):
            x += saw(f, n, d, RNG.random())
    x = np.tanh(x * 2.2)
    x = lp(x, cutoff, 2)
    return x * env_adsr(n, 0.005, 0.15, 0.8, 0.12) * vel * 0.12


def tom(m=45, vel=1.0):
    n = secs(0.9)
    t = np.arange(n) / SR
    f = midi_hz(m) * (1 + 0.8 * np.exp(-t * 18))
    x = np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t * 5.5)
    x += lp(noise(n), 1200) * np.exp(-t * 30) * 0.4
    return np.tanh(x * 1.5) * vel * 0.6


def choir(ms, dur, vel=0.5, vowel=(700, 1150)):
    n = secs(dur + 1.0)
    x = np.zeros(n)
    t = np.arange(n) / SR
    for m in ms:
        f = midi_hz(m)
        vib = 1 + 0.005 * np.sin(2 * math.pi * 5 * t + m)
        ph = np.cumsum(f * vib) / SR
        for d in (-0.004, 0.004):
            x += 2 * ((ph * (1 + d) + RNG.random()) % 1) - 1
    y = bp(x, vowel[0] * 0.7, vowel[0] * 1.3) + 0.6 * bp(x, vowel[1] * 0.8, vowel[1] * 1.2)
    return y * env_adsr(n, 0.8, 0.3, 0.85, 1.0) * vel * 0.12


def braam_sig(root=26, dur=2.6, vel=1.0):
    n = secs(dur)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for m in (root, root + 12, root + 19, root + 24):
        f = midi_hz(m)
        x += saw(f, n, -0.004) + saw(f, n, 0.004)
    x = np.tanh(x * 1.6)
    lo, hi = lp(x, 300), lp(x, 2400)
    w = np.clip(np.minimum(t / 0.25, 1) * np.exp(-t * 0.9), 0, 1)
    y = lo * (1 - w) + hi * w
    return y * env_adsr(n, 0.03, 0.4, 0.7, 0.8) * vel * 0.18


def arp_pluck(m, dur=0.3, vel=0.5):
    n = secs(dur + 0.2)
    t = np.arange(n) / SR
    f = midi_hz(m)
    x = np.sign(np.sin(2 * math.pi * f * t)) * 0.5 + np.sin(2 * math.pi * f * t)
    return lp(x, 2400) * np.exp(-t * 9) * vel * 0.15


# ======================================================================
#  cues
# ======================================================================
def cue_dread(L):
    s = Bus(L)
    n = secs(L)
    t = np.arange(n) / SR
    drone = np.sin(2 * math.pi * midi_hz(26) * t) * 0.18 + lp(brown(n), 140) * 0.25
    s.add(0, drone * np.minimum(1, t / 3), 1.0)
    s.add(0, pad([38, 45, 50, 53], L, 0.4, 700, 4.0, 3.0), 1.0)
    notes = [74, 77, 81, 76, 74, 69, 72, 74]
    for i, tt in enumerate(np.arange(2.0, L - 1, 2.6)):
        s.add(tt, piano(notes[i % len(notes)], 2.0, 0.35, 1.3), 1.0, 0.3 * math.sin(i))
    for tt in np.arange(4.0, L - 2, 8.0):
        s.add(tt, braam_sig(26, 3.0, 0.6), 1.0)
    return _fade(add_reverb(s.buf[:, :secs(L)], 0.5, 3.2), 2.0, 1.5)


def cue_op(L):
    """Hard-driving opening theme. D minor, 160 bpm."""
    s = Bus(L)
    beat = 60 / 160
    bar = 4 * beat
    prog = [38, 34, 41, 36]  # D, Bb, F, C (roots)
    mel = [(0, 74, 1), (1, 77, 1), (2, 81, 1.5), (3.5, 79, 0.5), (4, 77, 1), (5, 74, 1), (6, 72, 2),
           (8, 77, 1), (9, 81, 1), (10, 84, 1.5), (11.5, 82, 0.5), (12, 81, 2), (14, 79, 1), (15, 76, 1),
           (16, 74, 1), (17, 77, 1), (18, 81, 1.5), (19.5, 79, 0.5), (20, 82, 1), (21, 84, 1), (22, 86, 2),
           (24, 86, 4)]
    intro = 2
    s.add(0, A.sfx_whoosh(bar * intro, True, 0.6), 1.0)
    for b in range(intro):
        for i in range(8 if b else 4):
            s.add(b * bar + i * (beat / (2 if b else 1)), tom(45 - (i % 3) * 2, 0.7 + 0.04 * i), 1.0)
    nb = int(L / bar) + 1
    for b in range(intro, nb):
        t0 = b * bar
        bi = b - intro
        final = bi >= 6
        root = 38 if final else prog[bi % 4]
        if bi % 4 == 0:
            s.add(t0, crash(1.0), 1.0, 0.3)
            s.add(t0, braam_sig(root - 12, 1.2, 0.6), 1.0)
        for i in range(4):
            s.add(t0 + i * beat, kick(1.0), 1.0)
            if i % 2 == 1:
                s.add(t0 + i * beat, snare(1.0), 1.0, 0.1)
        for i in range(16):
            s.add(t0 + i * beat / 4, hat(0.5 + 0.3 * (i % 4 == 0)), 1.0, 0.4)
        for i in range(8):
            s.add(t0 + i * beat / 2, bass(root, beat / 2 * 0.85, 0.9), 1.0)
            s.add(t0 + i * beat / 2, dist_chord([root + 12, root + 19, root + 24], beat / 2 * 0.8, 0.8), 1.0, -0.3)
        for (bt, m, ln) in mel:
            if bi * 4 <= bt < (bi + 1) * 4:
                s.add(t0 + (bt - bi * 4) * beat, A.lead(m, ln * beat * 0.95, 0.85), 1.0, 0.15)
    return _fade(add_reverb(s.buf[:, :secs(L)], 0.2, 1.4), 0.05, 1.0)


def cue_dungeon(L):
    s = Bus(L)
    beat = 60 / 70
    for i in range(int(L / beat)):
        s.add(i * beat, lp(kick(0.5), 120), 1.0)
    for i, tt in enumerate(np.arange(0.5, L, 3.1)):
        s.add(tt, bell(int(RNG.choice([50, 53, 57, 60, 62])) + 12, 3.0, 0.25), 1.0, RNG.uniform(-0.7, 0.7))
    chords = [[38, 45, 50, 53], [34, 41, 46, 50], [36, 43, 48, 51], [33, 40, 45, 49]]
    bar = 6.0
    for b in range(int(L / bar) + 1):
        s.add(b * bar, pad(chords[b % 4], bar, 0.45, 600 + 200 * (b % 2), 2.0, 2.0), 1.0)
    return _fade(add_reverb(s.buf[:, :secs(L)], 0.55, 3.5, 4000), 2.0, 1.5)


def cue_battle(L):
    """Fast string ostinato + taiko + brass. D minor, 150 bpm."""
    s = Bus(L)
    beat = 60 / 150
    bar = 4 * beat
    roots = [50, 46, 48, 45]
    pat = [0, 0, 3, 0, 2, 0, -2, 0]
    for b in range(int(L / bar) + 1):
        t0 = b * bar
        r = roots[b % 4]
        for i in range(16):
            m = r + pat[i % 8] + (12 if i >= 8 and b % 2 else 0)
            s.add(t0 + i * beat / 4, strings([m], beat / 4 * 0.9, 0.9, 0.005, 0.05), 1.0, 0.3)
            s.add(t0 + i * beat / 4, strings([m - 12], beat / 4 * 0.9, 0.6, 0.005, 0.05), 1.0, -0.3)
        for i, v in ((0, 1.0), (1.5, 0.7), (2, 0.9), (3, 0.6), (3.5, 0.8)):
            s.add(t0 + i * beat, tom(40 if i in (0, 2) else 45, v), 1.0)
        s.add(t0 + beat, snare(0.7), 1.0)
        s.add(t0 + 3 * beat, snare(0.8), 1.0)
        if b % 2 == 0:
            s.add(t0, braam_sig(r - 24, bar * 1.6, 0.8), 1.0)
            s.add(t0, crash(0.7), 1.0, -0.3)
        s.add(t0, choir([r, r + 3, r + 7], bar, 0.6), 1.0)
    return _fade(add_reverb(s.buf[:, :secs(L)], 0.3, 2.0), 0.1, 0.8)


def cue_awaken(L):
    """Slow-motion: heartbeat, rising choir and a riser that cuts to silence."""
    s = Bus(L)
    n = secs(L)
    t = np.arange(n) / SR
    tt, gap = 0.2, 1.35
    while tt < L - 0.6:
        s.add(tt, A.sfx_heartbeat(0.9), 1.0)
        tt += gap
        gap = max(0.75, gap * 0.94)
    s.add(0, choir([50, 57, 62], L, 0.7, (500, 900)), 1.0)
    s.add(L * 0.4, choir([62, 69, 74], L * 0.6, 0.6, (700, 1150)), 1.0)
    rise = np.sin(2 * math.pi * np.cumsum(200 + 1600 * (t / L) ** 2) / SR) * (t / L) ** 2 * 0.15
    s.add(0, rise, 1.0)
    s.add(0, A.sfx_whoosh(L, True, 0.5), 1.0)
    out = add_reverb(s.buf[:, :secs(L)], 0.5, 3.0)
    return _fade(out, 1.0, 0.05)


def cue_after(L):
    s = Bus(L)
    beat = 60 / 72
    bar = 4 * beat
    chords = [[50, 57, 62, 66], [46, 53, 58, 62], [41, 53, 57, 60], [48, 55, 60, 64]]
    for b in range(int(L / bar) + 1):
        ch = chords[b % 4]
        s.add(b * bar, strings(ch, bar, 0.55, 1.2, 1.5), 1.0)
        s.add(b * bar, pad([m + 12 for m in ch[1:]], bar, 0.3, 2400, 1.0, 1.5), 1.0)
        for i in range(4):
            s.add(b * bar + i * beat, piano(ch[1 + i % 3] + 12, beat, 0.3, 1.2), 1.0, 0.25)
    return _fade(add_reverb(s.buf[:, :secs(L)], 0.5, 3.0), 2.0, 2.0)


def cue_bureau(L):
    s = Bus(L)
    beat = 60 / 120
    seq = [62, 65, 69, 72, 69, 65, 62, 57]
    for i in range(int(L / (beat / 2))):
        s.add(i * beat / 2, arp_pluck(seq[i % 8], 0.25, 0.5), 1.0, 0.4 * math.sin(i))
        if i % 2 == 0:
            s.add(i * beat / 2, hat(0.3), 1.0, 0.5)
    s.add(0, pad([38, 45, 50, 53], L, 0.4, 800, 2.0, 2.0), 1.0)
    for tt in np.arange(0, L, beat * 8):
        s.add(tt, lp(kick(0.7), 150), 1.0)
    return _fade(add_reverb(s.buf[:, :secs(L)], 0.35, 2.2), 1.0, 1.5)


def cue_ed(L):
    """Lo-fi piano ballad for the ending. 80 bpm."""
    s = Bus(L)
    beat = 60 / 80
    bar = 4 * beat
    chords = [[50, 57, 60, 64, 65], [46, 57, 62, 65, 69], [41, 57, 60, 64, 67], [48, 55, 60, 64, 69]]
    mel = [(0, 77, 1.5), (1.5, 76, 0.5), (2, 74, 2), (4, 77, 1), (5, 79, 1), (6, 81, 2), (8, 79, 1.5),
           (9.5, 77, 0.5), (10, 76, 2), (12, 74, 3), (15, 72, 1)]
    n = secs(L)
    s.add(0, lp(pink(n), 3000) * 0.012, 1.0)  # vinyl hiss
    for b in range(int(L / bar) + 1):
        ch = chords[b % 4]
        t0 = b * bar
        for i, m in enumerate(ch):
            s.add(t0 + i * 0.03, piano(m, bar * 0.95, 0.32, 0.8), 1.0, 0.1 * (i - 2))
        if b >= 2:
            for i in range(4):
                s.add(t0 + i * beat, lp(kick(0.6), 400) if i % 2 == 0 else lp(snare(0.4), 2500), 1.0)
            for i in range(8):
                s.add(t0 + i * beat / 2, lp(hat(0.35), 6000), 1.0, 0.3)
        bi = b % 4
        for (bt, m, ln) in mel:
            if bi * 4 <= bt < (bi + 1) * 4:
                s.add(t0 + (bt - bi * 4) * beat, piano(m, ln * beat, 0.5, 1.0), 1.0, -0.2)
    return _fade(add_reverb(s.buf[:, :secs(L)], 0.35, 2.0, 3500), 1.5, 3.0)


CUES = {"fl_dread": cue_dread, "fl_op": cue_op, "fl_dungeon": cue_dungeon, "fl_battle": cue_battle,
        "fl_awaken": cue_awaken, "fl_after": cue_after, "fl_bureau": cue_bureau, "fl_ed": cue_ed}
CUE_GAINS = {"fl_op": 0.6, "fl_battle": 0.6, "fl_awaken": 0.7, "fl_dread": 0.75, "fl_dungeon": 0.75,
             "fl_after": 0.7, "fl_bureau": 0.6, "fl_ed": 0.8}


# ======================================================================
#  SFX
# ======================================================================
def _metal(freqs, dur, decay, gain):
    n = secs(dur)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * math.pi * f * t + RNG.random() * 6) * np.exp(-t * decay * (1 + i * 0.3)) / (1 + i * 0.4)
            for i, f in enumerate(freqs))
    return x * gain


def sfx_shing():
    n = secs(1.4)
    t = np.arange(n) / SR
    x = _metal([2140, 3420, 5230, 7910, 9800], 1.4, 2.5, 0.25)
    x += hp(noise(n), 3000) * np.exp(-t * 12) * 0.35 * np.minimum(1, t / 0.05)
    return x


def sfx_clang():
    n = secs(1.2)
    t = np.arange(n) / SR
    x = _metal([780, 1340, 2260, 3720, 5100], 1.2, 4.0, 0.4)
    x += bp(noise(n), 800, 6000) * np.exp(-t * 35) * 0.8
    return np.tanh(x * 1.5) * 0.8


def sfx_roar():
    n = secs(2.6)
    t = np.arange(n) / SR
    f0 = 62 + 18 * np.sin(2 * math.pi * 0.7 * t) + 6 * RNG.standard_normal(n).cumsum() / SR * 30
    ph = np.cumsum(f0) / SR
    x = 2 * (ph % 1) - 1 + 0.5 * (2 * ((ph * 2.01) % 1) - 1)
    x = np.tanh(x * 3)
    form = bp(x, 250, 900) * 0.8 + bp(x, 1100, 2400) * 0.35
    form += lp(brown(n), 500) * 0.6
    e = np.minimum(1, t / 0.3) * np.exp(-np.maximum(0, t - 1.6) * 3)
    return np.tanh(form * e * 2.5) * 0.7


def sfx_shatter():
    n = secs(2.6)
    t = np.arange(n) / SR
    x = hp(noise(n), 1500) * np.exp(-t * 6) * 0.6
    x += lp(noise(n), 200) * np.exp(-t * 3) * 0.6
    for i in range(70):
        p = secs(RNG.random() ** 1.6 * 2.0)
        s = bell(int(RNG.integers(96, 112)), 0.5, 0.4 * RNG.random() + 0.1)
        m = min(len(s), n - p)
        x[p:p + m] += s[:m]
    k = A.kick(1.0)
    x[:len(k)] += k * 0.8
    return np.tanh(x * 1.3) * 0.8


def sfx_impact():
    n = secs(1.8)
    t = np.arange(n) / SR
    f = 30 + 90 * np.exp(-t * 14)
    x = np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t * 3)
    x += hp(noise(n), 800) * np.exp(-t * 25) * 0.8
    x += lp(brown(n), 300) * np.exp(-t * 2.5) * 0.6
    return np.tanh(x * 2.2) * 0.85


def sfx_crackle(dur=1.4):
    n = secs(dur)
    x = np.zeros(n)
    for i in range(int(dur * 60)):
        p = int(RNG.random() * (n - 800))
        ln = int(RNG.integers(80, 700))
        x[p:p + ln] += hp(noise(ln), 2000) * np.exp(-np.arange(ln) / (ln * 0.3)) * RNG.random()
    x += np.sin(2 * math.pi * 120 * np.arange(n) / SR) * 0.08
    return x * 0.6


def sfx_braam():
    return braam_sig(26, 3.0, 1.0) * 2.5


def sfx_radio():
    n = secs(0.5)
    t = np.arange(n) / SR
    beep = np.sin(2 * math.pi * 1800 * t) * (t < 0.08) * 0.3
    st = bp(noise(n), 800, 4000) * np.exp(-t * 6) * 0.25
    return beep + st


def sfx_rumble():
    n = secs(3.5)
    t = np.arange(n) / SR
    x = lp(brown(n), 140) * (0.6 + 0.4 * np.sin(2 * math.pi * 7 * t) ** 2)
    return x * np.minimum(1, t / 0.4) * np.exp(-np.maximum(0, t - 2.4) * 2) * 1.2


def sfx_riser():
    n = secs(2.5)
    t = np.arange(n) / SR
    f = 150 + 2500 * (t / 2.5) ** 2
    x = np.sin(2 * math.pi * np.cumsum(f) / SR) * 0.2 + A.sfx_whoosh(2.5, True, 0.8)[:n]
    return x * (t / 2.5) ** 1.5


def sfx_debris():
    n = secs(1.8)
    x = np.zeros(n)
    for i in range(25):
        p = int(RNG.random() ** 1.5 * (n - 6000))
        ln = 3000
        x[p:p + ln] += lp(noise(ln), 1500) * np.exp(-np.arange(ln) / 400) * RNG.random()
    return x * 0.7


def sfx_glitch():
    n = secs(0.7)
    x = np.zeros(n)
    for i in range(12):
        p = int(RNG.random() * (n - 3000))
        ln = int(RNG.integers(400, 3000))
        f = RNG.choice([400, 800, 1600, 3200])
        x[p:p + ln] += np.sign(np.sin(2 * math.pi * f * np.arange(ln) / SR)) * 0.25
    x = np.round(x * 6) / 6
    return x * 0.6


def sfx_swish():
    return A.sfx_whoosh(0.35, True, 1.2)


def sfx_ring():
    n = secs(3.5)
    t = np.arange(n) / SR
    return np.sin(2 * math.pi * 3600 * t) * np.minimum(1, t / 0.3) * np.exp(-t * 0.8) * 0.06


SFX = {"shing": sfx_shing, "clang": sfx_clang, "roar": sfx_roar, "shatter": sfx_shatter, "impact": sfx_impact,
       "crackle": sfx_crackle, "braam": sfx_braam, "radio": sfx_radio, "rumble": sfx_rumble, "riser": sfx_riser,
       "debris": sfx_debris, "glitch": sfx_glitch, "swish": sfx_swish, "ring": sfx_ring}


# ======================================================================
#  ambience
# ======================================================================
def amb_tunnel(L):
    n = secs(L)
    t = np.arange(n) / SR
    hum = np.sin(2 * math.pi * 50 * t) * 0.05 + np.sin(2 * math.pi * 100 * t) * 0.02
    air = lp(pink(n), 400) * 0.04
    drips = np.zeros(n)
    for i in range(int(L / 1.7)):
        p = int(RNG.random() * (n - 4000))
        tt = np.arange(3000) / SR
        drips[p:p + 3000] += np.sin(2 * math.pi * (1200 + 800 * RNG.random()) * tt * (1 + tt * 6)) * np.exp(-tt * 50) * 0.15
    mono = hum + air + drips
    return np.vstack([mono, np.roll(mono, 900)]) * 1.4


def amb_city(L):
    n = secs(L)
    st = np.vstack([lp(pink(n), 700) for _ in range(2)])
    return st / (np.abs(st).max() + 1e-9) * 0.12


def amb_room(L):
    n = secs(L)
    t = np.arange(n) / SR
    mono = np.sin(2 * math.pi * 60 * t) * 0.03 + bp(pink(n), 200, 2000) * 0.01
    return np.vstack([mono, mono])


AMBIENCE = {"tunnel": amb_tunnel, "city": amb_city, "room": amb_room}


# ======================================================================
#  voices
# ======================================================================
VOICES = {
    "kai": ("am_puck", 1.0, 1.0, 0.12),
    "kai_inner": ("am_puck", 0.94, 1.0, 0.3),
    "hana": ("af_bella", 1.02, 1.0, 0.12),
    "narrator": ("am_michael", 0.95, 1.0, 0.2),
    "operator": ("af_sarah", 1.05, 1.0, 0.0),
    "director": ("am_fenrir", 0.9, 0.93, 0.2),
    "analyst": ("af_kore", 1.05, 1.0, 0.1),
}


def radio(x):
    y = bp(x, 380, 3200)
    y = np.tanh(y * 3) * 0.5
    y += bp(noise(len(y)), 1000, 5000) * 0.015
    return y


VOICE_FX = {"operator": radio}
VOICE_REVERB = {"narrator": (0.18, 1.6, 6000), "kai_inner": (0.4, 2.0, 5000), "director": (0.2, 1.2, 5000),
                "kai": (0.18, 1.4, 6000), "hana": (0.18, 1.4, 6000)}

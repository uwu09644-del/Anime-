"""Background art for STARFALL KEEPER: skies, sea, lighthouse, beach, interior."""
import math

import numpy as np
import skia

from gfx import (ADD, H, W, Saved, fill, glow, hash01, linear, mix, poly_path, radial, rgb,
                 smooth_path, snapshot_layer, sparkle, stroke)

# ---------------------------------------------------------------- star field (cached)
_CACHE = {}


def _starfield_img(seed=1, w=W * 2, h=H * 2, density=1.0):
    key = ("stars", seed, w, h, density)
    if key in _CACHE:
        return _CACHE[key]
    rng = np.random.default_rng(seed)

    def draw(c):
        # milky way band
        for i in range(60):
            x = rng.random() * w
            y = h * 0.35 + (x / w - 0.5) * h * 0.5 + rng.normal() * 90
            r = 60 + rng.random() * 160
            c.drawCircle(x, y, r, fill(rgb(["#8f7bd6", "#5d7fd6", "#d68fc7"][i % 3]),
                                       0.05 + rng.random() * 0.05, blur=r * 0.6))
        n = int(1400 * density)
        xs, ys = rng.random(n) * w, rng.random(n) * h
        ss = rng.random(n) ** 3
        for x, y, s in zip(xs, ys, ss):
            r = 0.7 + s * 2.6
            col = ["#ffffff", "#cfe0ff", "#fff1d0", "#e6d6ff"][int(rng.random() * 4)]
            c.drawCircle(x, y, r, fill(rgb(col), 0.45 + 0.55 * s))
            if s > 0.55:
                c.drawCircle(x, y, r * 4, fill(rgb(col), 0.18, blur=r * 2))

    img = snapshot_layer(draw, w, h)
    _CACHE[key] = img
    return img


def night_sky(c, t, pan=(0.0, 0.0), top="#070b24", mid="#1a1f55", bottom="#4b3a78",
              horizon=None, stars=1.0, twinkle=True, seed=1):
    horizon = H if horizon is None else horizon
    c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(0, shader=linear((0, 0), (0, horizon),
               [rgb(top), rgb(mid), rgb(bottom)], [0, 0.55, 1])))
    if stars > 0:
        img = _starfield_img(seed)
        p = skia.Paint()
        p.setAlphaf(stars)
        c.drawImage(img, -W * 0.25 - pan[0], -H * 0.5 - pan[1], skia.SamplingOptions(), p)
        if twinkle:
            for i in range(26):
                x = (hash01(i, 1, seed) * W * 1.4 - pan[0] * 1.0) % W
                y = hash01(i, 2, seed) * horizon * 0.85
                a = 0.5 + 0.5 * math.sin(t * (1.5 + hash01(i, 3) * 3) + i)
                sparkle(c, x, y, 5 + hash01(i, 4) * 8, "#ffffff", alpha=a * stars)


def moon(c, x, y, r=70, alpha=1.0):
    glow(c, x, y, r * 4.5, "#bcd0ff", 0.35 * alpha)
    c.drawCircle(x, y, r, fill(rgb("#fff6dc"), alpha))
    c.drawCircle(x + r * 0.25, y - r * 0.1, r * 0.25, fill(rgb("#efe1bd"), 0.6 * alpha))
    c.drawCircle(x - r * 0.35, y + r * 0.3, r * 0.15, fill(rgb("#efe1bd"), 0.5 * alpha))


def clouds(c, t, y, color="#2a2f66", alpha=0.6, speed=12, seed=3, scale=1.0, n=7):
    for i in range(n):
        x = ((hash01(i, seed) * W * 1.6 + t * speed * (0.6 + hash01(i, 9))) % (W + 800)) - 400
        yy = y + (hash01(i, seed, 2) - 0.5) * 120 * scale
        for k in range(5):
            cx = x + (k - 2) * 70 * scale
            cy = yy - math.sin(k / 4 * math.pi) * 40 * scale
            r = (60 + 30 * math.sin(k * 1.7 + i)) * scale
            c.drawCircle(cx, cy, r, fill(rgb(color), alpha, blur=18 * scale))


# ---------------------------------------------------------------- sea
def sea(c, t, horizon, color_top="#1b2a5e", color_bottom="#0a1030", moon_x=None, sparkle_amt=1.0):
    r = skia.Rect.MakeLTRB(-W, horizon, 2 * W, 2 * H)
    c.drawRect(r, fill(0, shader=linear((0, horizon), (0, H), [rgb(color_top), rgb(color_bottom)])))
    # horizon haze
    c.drawRect(skia.Rect.MakeLTRB(-W, horizon - 30, 2 * W, horizon + 30),
               fill(rgb("#7a7ac8"), 0.25, blur=18))
    # wave lines
    rows = 26
    for j in range(rows):
        f = j / rows
        yy = horizon + (H - horizon) * (f ** 1.7) + 4
        n = int(14 + 30 * (1 - f))
        for i in range(n):
            ph = hash01(i, j) * W
            x = (ph + t * (8 + 30 * f) * (1 if j % 2 else -1)) % (W + 200) - 100
            ln = (20 + 90 * f) * (0.5 + hash01(i, j, 5))
            a = (0.15 + 0.25 * f) * (0.5 + 0.5 * math.sin(t * 1.3 + i + j))
            c.drawLine(x, yy, x + ln, yy, stroke(rgb("#8fb0ff"), 1.5 + 2.5 * f, alpha=a))
    # moon reflection column
    if moon_x is not None:
        for j in range(40):
            f = j / 40
            yy = horizon + (H - horizon) * f
            wv = (10 + 120 * f) * (0.6 + 0.4 * math.sin(t * 2.2 + j * 1.3))
            off = math.sin(t * 1.7 + j * 0.9) * 12 * f
            c.drawLine(moon_x - wv / 2 + off, yy, moon_x + wv / 2 + off, yy,
                       stroke(rgb("#fff3c8"), 2 + 3 * f, alpha=0.55 * sparkle_amt * (1 - f * 0.5)))


# ---------------------------------------------------------------- lighthouse
def lighthouse(c, x, y, s=1.0, beam=0.0, lit=1.0, night=True, beam_alpha=1.0):
    """Base centre at (x, y). Tower height ~ 460*s. beam = rotation angle (rad)."""
    with Saved(c):
        c.translate(x, y)
        c.scale(s, s)
        line = rgb("#151530")
        tower = poly_path([(-70, 0), (70, 0), (44, -380), (-44, -380)])
        c.drawPath(tower, fill(rgb("#e9e6f2" if not night else "#aeb3d6")))
        with Saved(c):
            c.clipPath(tower, doAntiAlias=True)
            for k in range(3):
                yy = -60 - k * 110
                c.drawRect(skia.Rect.MakeLTRB(-90, yy - 45, 90, yy), fill(rgb("#c8384a" if not night else "#7a2a4a")))
            c.drawRect(skia.Rect.MakeLTRB(0, -400, 90, 0), fill(rgb("#000000"), 0.25))
        c.drawPath(tower, stroke(line, 3 / s))
        # door + windows
        c.drawRoundRect(skia.Rect.MakeXYWH(-14, -46, 28, 46), 10, 10, fill(rgb("#2a2440")))
        for yy in (-170, -280):
            c.drawRoundRect(skia.Rect.MakeXYWH(-8, yy, 16, 24), 6, 6,
                            fill(rgb("#ffd27a" if night else "#3a3a5a"), 0.9))
        # gallery
        c.drawRect(skia.Rect.MakeLTRB(-66, -392, 66, -378), fill(rgb("#2a2a44")))
        for k in range(-60, 64, 12):
            c.drawLine(k, -420, k, -392, stroke(rgb("#2a2a44"), 3))
        c.drawLine(-66, -420, 66, -420, stroke(rgb("#2a2a44"), 4))
        # lantern room
        c.drawRect(skia.Rect.MakeLTRB(-36, -470, 36, -420), fill(rgb("#fff3c4") if lit > 0.5 else rgb("#4a4a6a")))
        for k in (-36, -12, 12, 36):
            c.drawLine(k, -470, k, -420, stroke(rgb("#2a2a44"), 3))
        dome = smooth_path([(-44, -470), (0, -520), (44, -470)])
        c.drawPath(dome, fill(rgb("#a8303f" if not night else "#5a2038")))
        c.drawLine(0, -520, 0, -545, stroke(rgb("#2a2a44"), 4))
        if lit > 0:
            glow(c, 0, -445, 180, "#ffe7a0", 0.85 * lit)
            # rotating beam: draw cone pointing left/right depending on angle
            for ofs in (0.0, math.pi):
                a = beam + ofs
                k = math.cos(a)            # -1..1: towards left/right
                depth = math.sin(a)        # >0: pointing towards viewer
                length = 1900 * abs(k) + 200
                spread = 60 + 140 * (1 - abs(k))
                al = (0.38 + 0.4 * max(depth, 0)) * lit * beam_alpha
                ex = k * length
                p = poly_path([(0, -452), (ex, -445 - spread), (ex, -445 + spread), (0, -438)])
                c.drawPath(p, fill(0, shader=linear((0, -445), (ex if ex else 1, -445),
                           [rgb("#fff3c0", al), rgb("#fff3c0", 0)]), blend=ADD))
            if math.sin(beam) > 0.85:  # beam pointing at camera -> flare
                fl = (math.sin(beam) - 0.85) / 0.15
                glow(c, 0, -445, 600, "#fff7d0", 0.8 * fl * lit * beam_alpha)


def cliff(c, x0, y, w, color="#0d1030", grass="#1a2348", t=0.0):
    pts = [(x0 - 40, H + 10), (x0, y + 30), (x0 + w * 0.1, y), (x0 + w * 0.5, y - 12),
           (x0 + w * 0.85, y + 4), (x0 + w, y + 60), (x0 + w + 60, y + 260), (x0 + w + 140, H + 10)]
    p = smooth_path(pts, closed=False)
    p.lineTo(x0 - 40, H + 10)
    p.close()
    c.drawPath(p, fill(rgb(color)))
    # grass tufts swaying
    for i in range(50):
        gx = x0 + w * i / 50
        gy = y - 10 + math.sin(i * 0.7) * 6
        sw = math.sin(t * 2 + i * 0.5) * 5
        c.drawLine(gx, gy + 8, gx + sw, gy - 14, stroke(rgb(grass), 4))


def cottage(c, x, y, s=1.0, window=1.0):
    with Saved(c):
        c.translate(x, y)
        c.scale(s, s)
        body = poly_path([(-90, 0), (90, 0), (90, -90), (-90, -90)])
        c.drawPath(body, fill(rgb("#1c1f44")))
        roof = poly_path([(-110, -86), (0, -160), (110, -86)])
        c.drawPath(roof, fill(rgb("#2a1f3e")))
        for wx in (-45, 40):
            glow(c, wx, -50, 70, "#ffc670", 0.4 * window)
            c.drawRect(skia.Rect.MakeXYWH(wx - 16, -66, 32, 30), fill(rgb("#ffd88a"), window))
        c.drawRect(skia.Rect.MakeXYWH(50, -190, 18, 50), fill(rgb("#1c1f44")))


# ---------------------------------------------------------------- beach
def beach(c, t, horizon=430, glow_amt=0.0, glow_x=1180, glow_y=820):
    sea(c, t, horizon, color_top="#1a2a60", color_bottom="#14204a")
    # sand
    sand = smooth_path([(-600, 720), (-20, 700), (400, 650), (900, 640), (1400, 660), (1940, 620),
                        (2500, 640), (2500, 2 * H), (-600, 2 * H)])
    c.drawPath(sand, fill(0, shader=linear((0, 620), (0, H), [rgb("#3a3f6e"), rgb("#262a52")])))
    # surf line moving in and out
    for k in range(3):
        ph = t * 0.6 + k * 2.1
        reach = (math.sin(ph) * 0.5 + 0.5)
        yy = 650 + reach * 40 + k * 14
        pts = [(-20, yy + 20)] + [(x, yy + math.sin(x * 0.01 + ph * 2) * 8) for x in range(0, 2000, 200)]
        p = smooth_path(pts, closed=False)
        c.drawPath(p, stroke(rgb("#cfe0ff"), 5 - k, alpha=0.55 - k * 0.12))
        wet = skia.Path(p)
        wet.lineTo(1940, yy - 60)
        wet.lineTo(-20, yy - 60)
        wet.close()
        c.drawPath(wet, fill(rgb("#2a3a7a"), 0.18))
    # rocks
    for (rx, ry, rw, rh) in ((180, 760, 260, 140), (1600, 720, 330, 170), (1440, 820, 160, 90)):
        rock = smooth_path([(rx - rw / 2, ry + rh / 2), (rx - rw * 0.4, ry - rh * 0.2), (rx - rw * 0.1, ry - rh / 2),
                            (rx + rw * 0.3, ry - rh * 0.35), (rx + rw / 2, ry + rh / 2)])
        c.drawPath(rock, fill(rgb("#14163a")))
        c.drawPath(rock, stroke(rgb("#3a4380"), 3, alpha=0.6))
    # the net
    net(c, glow_x, glow_y, t, glow_amt)


def net(c, x, y, t, glow_amt):
    if glow_amt > 0:
        glow(c, x, y, 520 * (0.6 + 0.4 * glow_amt), "#cfe0ff", 0.65 * glow_amt)
        glow(c, x, y, 160, "#ffffff", 0.9 * glow_amt)
    with Saved(c):
        c.translate(x, y)
        shape = smooth_path([(-260, 40), (-180, -50), (-40, -90), (120, -70), (250, -10), (230, 70),
                             (60, 100), (-140, 90)])
        c.drawPath(shape, fill(rgb("#1e2450"), 0.5))
        with Saved(c):
            c.clipPath(shape, doAntiAlias=True)
            col = "#e8f0ff" if glow_amt > 0.3 else "#8a90b8"
            for k in range(-300, 320, 26):
                sway = math.sin(t + k * 0.02) * 4
                c.drawLine(k + sway, -120, k + 120 + sway, 140, stroke(rgb(col), 2.2, alpha=0.7))
                c.drawLine(k + sway, -120, k - 120 + sway, 140, stroke(rgb(col), 2.2, alpha=0.7))
        c.drawPath(shape, stroke(rgb("#b8b0a0"), 4, alpha=0.8))
        # floats
        for fx, fy in ((-200, 10), (-60, -80), (140, -60), (210, 40)):
            c.drawCircle(fx, fy, 14, fill(rgb("#d8823a")))


# ---------------------------------------------------------------- lighthouse balcony
def balcony_bg(c, t, pan=0.0, storm=0.0):
    night_sky(c, t, pan=(pan * 0.3, 0), horizon=820, bottom="#5a4a88")
    moon(c, 1500 - pan * 0.2, 220, 64)
    clouds(c, t, 330, color="#2c2f6a", alpha=0.45 + storm * 0.4, speed=10)
    sea(c, t, 820, moon_x=1500 - pan * 0.2)


def railing(c, y=760, color="#151532", lit="#3a3a6a"):
    c.drawRect(skia.Rect.MakeLTRB(0, y, W, y + 22), fill(rgb(color)))
    c.drawLine(0, y + 2, W, y + 2, stroke(rgb(lit), 3))
    for k in range(0, W + 1, 70):
        c.drawRect(skia.Rect.MakeLTRB(k - 6, y, k + 6, H), fill(rgb(color)))
    c.drawRect(skia.Rect.MakeLTRB(0, y + 210, W, y + 230), fill(rgb(color)))


# ---------------------------------------------------------------- interior
def interior(c, t, lightning=0.0, lamp_flicker=True):
    c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(0, shader=linear((0, 0), (0, H),
               [rgb("#4a2f24"), rgb("#6e4630"), rgb("#3a2419")], [0, 0.6, 1])))
    # curved stone wall planks
    for k in range(-480, W + 481, 120):
        c.drawLine(k, -200, k + (k - W / 2) * 0.06, H + 200, stroke(rgb("#3a2419"), 4, alpha=0.6))
    # porthole window
    wx, wy, wr = 1460, 360, 190
    c.drawCircle(wx, wy, wr + 26, fill(rgb("#2a1a12")))
    with Saved(c):
        win = skia.Path()
        win.addCircle(wx, wy, wr)
        c.clipPath(win, doAntiAlias=True)
        c.drawCircle(wx, wy, wr, fill(0, shader=linear((0, wy - wr), (0, wy + wr),
                     [rgb("#0b0f2e"), rgb("#1c2456")])))
        if lightning > 0:
            c.drawCircle(wx, wy, wr, fill(rgb("#e8ecff"), lightning))
        for i in range(60):  # rain
            rx = wx - wr + hash01(i, 1) * wr * 2
            ry = (hash01(i, 2) * 500 + t * 900) % (wr * 2 + 60) + wy - wr - 30
            c.drawLine(rx, ry, rx - 10, ry + 34, stroke(rgb("#a8b8ff"), 2, alpha=0.55))
    c.drawCircle(wx, wy, wr, stroke(rgb("#b88a4a"), 14))
    c.drawLine(wx - wr, wy, wx + wr, wy, stroke(rgb("#2a1a12"), 10))
    c.drawLine(wx, wy - wr, wx, wy + wr, stroke(rgb("#2a1a12"), 10))
    # shelves with jars and a ship in a bottle
    for sy in (300, 520):
        c.drawRect(skia.Rect.MakeLTRB(80, sy, 620, sy + 18), fill(rgb("#2e1c14")))
        for j in range(6):
            jx = 120 + j * 82
            h = 60 + hash01(j, sy) * 50
            col = ["#7aa0c8", "#c87a5a", "#9ac87a", "#c8b47a"][j % 4]
            c.drawRoundRect(skia.Rect.MakeXYWH(jx, sy - h, 54, h), 10, 10, fill(rgb(col), 0.75))
            c.drawRoundRect(skia.Rect.MakeXYWH(jx + 8, sy - h + 8, 10, h - 20), 5, 5, fill(rgb("#ffffff"), 0.3))
    # hanging lamp
    fl = 1.0 + (0.05 * math.sin(t * 13) + 0.04 * math.sin(t * 7.3)) if lamp_flicker else 1.0
    c.drawLine(960, 0, 960, 150, stroke(rgb("#1a120c"), 5))
    glow(c, 960, 200, 900 * fl, "#ffb056", 0.5)
    c.drawPath(smooth_path([(910, 150), (1010, 150), (990, 230), (930, 230)]), fill(rgb("#ffe2a0")))
    c.drawPath(smooth_path([(900, 150), (960, 120), (1020, 150)]), fill(rgb("#2e1c14")))
    if lightning > 0:
        c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(rgb("#c8d0ff"), lightning * 0.35))


def table_fg(c):
    c.drawRect(skia.Rect.MakeLTRB(0, 930, W, H), fill(0, shader=linear((0, 930), (0, H),
               [rgb("#5a3420"), rgb("#2e1a10")])))
    c.drawLine(0, 932, W, 932, stroke(rgb("#8a5a34"), 5))


# ---------------------------------------------------------------- crimson sky (villain)
def crimson_sky(c, t, flash=0.0):
    c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(0, shader=linear((0, 0), (0, H),
               [rgb("#12030c"), rgb("#4a0c22"), rgb("#8a2a2a")], [0, 0.6, 1])))
    c.drawCircle(W * 0.5, H * 0.32, 230, fill(rgb("#ff5a3a"), 0.18, blur=80))
    c.drawCircle(W * 0.5, H * 0.32, 150, fill(rgb("#2a0310")))
    c.drawCircle(W * 0.5, H * 0.32, 150, stroke(rgb("#ff6a4a"), 6, alpha=0.6, blur=4))
    clouds(c, t, 760, color="#1a0410", alpha=0.85, speed=40, seed=7, scale=1.6, n=9)
    clouds(c, t, 940, color="#0c0208", alpha=0.95, speed=70, seed=8, scale=2.0, n=9)
    if flash > 0:
        c.drawRect(skia.Rect.MakeWH(W, H), fill(rgb("#ffd0e0"), flash * 0.5))
        p = smooth_path([(300, 0), (360, 160), (320, 200), (420, 380), (380, 420), (460, 600)], closed=False)
        c.drawPath(p, stroke(rgb("#ffffff"), 6, alpha=flash))
        c.drawPath(p, stroke(rgb("#ff9ad0"), 24, alpha=flash * 0.4, blur=10))


def ship_prow(c, t):
    bob = math.sin(t * 1.2) * 10
    with Saved(c):
        c.translate(0, bob)
        hull = smooth_path([(-40, 1100), (-40, 860), (700, 820), (1380, 900), (1500, 960), (1300, 1100)])
        c.drawPath(hull, fill(rgb("#0a0610")))
        c.drawPath(hull, stroke(rgb("#ff4a6a"), 3, alpha=0.5))
        for k in range(0, 1400, 90):
            c.drawLine(k, 840 + k * 0.05, k, 800 + k * 0.05, stroke(rgb("#0a0610"), 10))
        c.drawLine(-40, 800, 1450, 870, stroke(rgb("#0a0610"), 10))


# ---------------------------------------------------------------- falling star streak
def falling_star(c, x, y, angle, length=600, alpha=1.0, width=10):
    dx, dy = math.cos(angle), math.sin(angle)
    tx, ty = x - dx * length, y - dy * length
    sh = linear((tx, ty), (x, y), [rgb("#9ab8ff", 0), rgb("#cfe0ff", 0.6 * alpha), rgb("#ffffff", alpha)],
                [0, 0.7, 1])
    p = poly_path([(tx, ty), (x - dy * width, y + dx * width), (x + dy * width, y - dx * width)])
    c.drawPath(p, fill(0, shader=sh, blend=ADD))
    glow(c, x, y, 120, "#dfe8ff", alpha)
    sparkle(c, x, y, 40, "#ffffff", alpha)

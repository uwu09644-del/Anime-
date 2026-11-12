"""FAULTLINE backgrounds: city at dusk with a Gate, the subway dungeon, the Bureau."""
import math

import numpy as np
import skia

from gfx import (ADD, H, W, Saved, clamp, draw_text, fill, font, glow, hash01, lerp, linear, mix, poly_path,
                 radial, rgb, smooth_path, snapshot_layer, stroke)
from faultline import fx

_CACHE = {}


def big_rect():
    return skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H)


# ======================================================================
#  city at dusk
# ======================================================================
def _skyline_img(layer, seed, color, win_col, win_density, h_min, h_max, base_y):
    key = ("sky", layer, seed)
    if key in _CACHE:
        return _CACHE[key]
    rng = np.random.default_rng(seed)
    w = W * 2

    def draw(c):
        x = -40
        while x < w:
            bw = rng.integers(60, 190)
            bh = rng.integers(h_min, h_max)
            top = base_y - bh
            c.drawRect(skia.Rect.MakeLTRB(x, top, x + bw, H * 2), fill(rgb(color)))
            if rng.random() < 0.25:  # antenna / spire
                c.drawRect(skia.Rect.MakeLTRB(x + bw * 0.45, top - 60, x + bw * 0.55, top), fill(rgb(color)))
                c.drawCircle(x + bw * 0.5, top - 62, 4, fill(rgb("#ff4050")))
            if rng.random() < 0.3:  # stepped roof
                c.drawRect(skia.Rect.MakeLTRB(x + 10, top - 26, x + bw - 10, top), fill(rgb(color)))
            for wy in range(int(top) + 14, int(base_y + 40), 22):
                for wx in range(int(x) + 8, int(x + bw) - 8, 16):
                    if rng.random() < win_density:
                        a = 0.35 + 0.65 * rng.random()
                        c.drawRect(skia.Rect.MakeXYWH(wx, wy, 8, 10), fill(rgb(win_col), a))
            x += bw + rng.integers(0, 14)

    img = snapshot_layer(draw, w, H * 2)
    _CACHE[key] = img
    return img


def city_dusk(c, t, pan=0.0, gate=1.0, gate_pos=(1240, 260), gate_r=210, sky_top="#0c0a2a",
              sky_mid="#4a1d5a", sky_low="#ff7a4a", tilt=0.0):
    c.drawRect(big_rect(), fill(0, shader=linear((0, 0), (0, 760), [rgb(sky_top), rgb(sky_mid), rgb(sky_low)],
                                                     [0, 0.55, 1])))
    # sun glow at the horizon
    glow(c, 500 - pan * 0.1, 760, 700, "#ff9a5a", 0.5)
    # clouds lit from below
    for i in range(10):
        cx = (hash01(i, 1) * 2400 - pan * 0.15 + t * 6) % 2600 - 300
        cy = 180 + hash01(i, 2) * 380
        for k in range(4):
            r = 70 + 50 * hash01(i, k)
            c.drawOval(skia.Rect.MakeXYWH(cx + k * 90 - r, cy - r * 0.35, r * 2.4, r * 0.7),
                       fill(rgb(mix("#3a1a4a", "#ff8a6a", cy / 700)), 0.55, blur=10))
    if gate > 0:
        gx, gy = gate_pos
        fx.portal(c, gx - pan * 0.2, gy, gate_r, t, intensity=gate)
        fx.god_rays(c, gx - pan * 0.2, gy, t, n=7, length=900, color="#ff6070", alpha=0.08 * gate, spread=1.0)
    # three skyline layers with haze between
    layers = [(0.25, 1, "#3a2a5a", "#ffcf9a", 0.12, 200, 420, 760),
              (0.5, 2, "#221a3a", "#ffd9a0", 0.22, 160, 520, 840),
              (0.85, 3, "#0e0a1a", "#ffe2b0", 0.3, 120, 600, 980)]
    for par, seed, col, win, dens, hmin, hmax, base in layers:
        img = _skyline_img(par, seed, col, win, dens, hmin, hmax, base)
        c.drawImage(img, -((pan * par) % W) - 200, 0)
        c.drawRect(skia.Rect.MakeLTRB(-W, base - 200, 2 * W, base + 40),
                   fill(0, shader=linear((0, base - 200), (0, base + 40), [rgb("#ff8a6a", 0), rgb("#ff8a6a", 0.12)])))


# ======================================================================
#  subway dungeon (one-point perspective)
# ======================================================================
VP = (960, 470)


def _persp(x, y, z):
    """World x,y at depth z (1 = picture plane, larger = further) -> screen."""
    return VP[0] + (x - VP[0]) / z, VP[1] + (y - VP[1]) / z


def subway(c, t, red=0.0, cam_x=0.0, crystals=1.0, crack_open=0.0, sight=0.0):
    base = mix("#0a1022", "#1a0408", red)
    c.drawRect(big_rect(), fill(rgb(base)))
    # tunnel walls: quads from near plane to the vanishing point
    wall = mix("#1c2640", "#3a0c14", red)
    floor = mix("#151b2c", "#2a0a0e", red)
    ceil = mix("#0c1020", "#14040a", red)
    L, R, T, B = -260 + cam_x, W + 260 + cam_x, -120, H + 80
    vx, vy = VP[0] + cam_x * 0.05, VP[1]
    far = 0.12
    fl = lambda x, y: (vx + (x - vx) * far, vy + (y - vy) * far)  # noqa: E731
    c.drawPath(poly_path([(L, T), fl(L, T), fl(L, B), (L, B)]), fill(rgb(wall)))
    c.drawPath(poly_path([(R, T), fl(R, T), fl(R, B), (R, B)]), fill(rgb(mix(wall, "#000000", 0.25))))
    c.drawPath(poly_path([(L, T), (R, T), fl(R, T), fl(L, T)]), fill(rgb(ceil)))
    c.drawPath(poly_path([(L, B), (R, B), fl(R, B), fl(L, B)]), fill(rgb(floor)))
    # tile grid on walls (receding lines + depth slices)
    tile = mix("#2c3a5c", "#5a1420", red)
    for k in range(1, 9):
        yy = T + (B - T) * k / 9
        for xx in (L, R):
            a, b = (xx, yy), fl(xx, yy)
            c.drawLine(a[0], a[1], b[0], b[1], stroke(rgb(tile), 2, alpha=0.6))
    zs = [1.0 + i * 0.55 for i in range(14)]
    for z in zs:
        s = 1 / z
        if s < far:
            continue
        lx, rx = vx + (L - vx) * s, vx + (R - vx) * s
        ty, by = vy + (T - vy) * s, vy + (B - vy) * s
        al = 0.5 * s + 0.1
        c.drawLine(lx, ty, lx, by, stroke(rgb(tile), 3 * s + 1, alpha=al))
        c.drawLine(rx, ty, rx, by, stroke(rgb(tile), 3 * s + 1, alpha=al))
    # platform edge + safety line + track pit
    for z in (1.0,):
        pass
    py = H - 200
    c.drawPath(poly_path([(L, py), (R * 0.42 + cam_x * 0.5, py), fl(R * 0.42 + cam_x * 0.5, py), fl(L, py)]),
               fill(rgb(mix("#202a40", "#3a1014", red))))
    c.drawLine(L, py + 4, fl(L, py)[0], fl(L, py)[1], stroke(rgb("#e8c040"), 10, alpha=0.8))
    pit_l = R * 0.42 + cam_x * 0.5
    c.drawPath(poly_path([(pit_l, py), (R, py), fl(R, py), fl(pit_l, py)]), fill(rgb("#05060c")))
    for off in (0.55, 0.8):
        rx0 = lerp(pit_l, R, off)
        a, b = (rx0, B), fl(rx0, py)
        c.drawLine(a[0], a[1], b[0], b[1], stroke(rgb(mix("#7a8aa8", "#c06070", red)), 8, alpha=0.7))
    # pillars
    for i, z in enumerate((1.4, 2.2, 3.4, 5.2)):
        s = 1 / z
        for side in (0.18, 0.82):
            wx = lerp(L, R, side)
            px = vx + (wx - vx) * s
            w = 140 * s
            top = vy + (T - vy) * s
            bot = vy + (B - vy) * s
            col = mix(mix("#26304c", "#4a1018", red), base, 1 - s)
            c.drawRect(skia.Rect.MakeLTRB(px - w / 2, top, px + w / 2, bot), fill(rgb(col)))
            c.drawRect(skia.Rect.MakeLTRB(px - w / 2, top, px - w / 2 + w * 0.18, bot),
                       fill(rgb(mix("#7fa6ff", "#ff5060", red)), 0.25 * s))
    # hanging cables + broken ceiling panels
    for i in range(7):
        x0 = lerp(L, R, hash01(i, 3))
        sw = math.sin(t * 0.8 + i) * 8
        p = skia.Path()
        p.moveTo(x0, T)
        p.quadTo(x0 + 40 + sw, T + 160 + 60 * hash01(i, 4), x0 + 90 + sw * 2, T + 80 + 120 * hash01(i, 5))
        c.drawPath(p, stroke(rgb("#05060c"), 5))
    # glowing crystals (cyan; red tinted in alert)
    if crystals > 0:
        ccol = mix("#5ad1ff", "#ff5a6a", red)
        for i in range(16):
            z = 1.0 + hash01(i, 8) * 5
            s = 1 / z
            side = -1 if i % 2 else 1
            wx = L if side < 0 else R
            wy = lerp(T, B, 0.55 + 0.4 * hash01(i, 9))
            px, py_ = vx + (wx - vx) * s, vy + (wy - vy) * s
            px += side * -30 * s
            hh = (60 + 90 * hash01(i, 10)) * s
            ww = hh * 0.35
            pulse = 0.7 + 0.3 * math.sin(t * 2 + i)
            glow(c, px, py_ - hh * 0.4, hh * 2.2, ccol, 0.35 * pulse * crystals)
            for k in range(3):
                off = (k - 1) * ww * 0.8
                hk = hh * (1 - abs(k - 1) * 0.35)
                c.drawPath(poly_path([(px + off - ww / 2, py_), (px + off, py_ - hk), (px + off + ww / 2, py_)]),
                           fill(rgb(mix(ccol, "#ffffff", 0.3)), 0.9))
    # depth haze toward the vanishing point
    c.drawCircle(vx, vy, 520, fill(0, shader=radial((vx, vy), 520, [rgb(mix("#4a6aa8", "#ff3048", red), 0.5),
                                                                       rgb(base, 0)])))
    # emergency lights
    for i, z in enumerate((1.2, 2.0, 3.2)):
        s = 1 / z
        lx = vx + (L + 200 - vx) * s
        ly = vy + (T + 40 - vy) * s
        on = (0.5 + 0.5 * math.sin(t * 4 + i)) if red > 0.3 else 0.3
        col = "#ff3040" if red > 0.3 else "#ffb060"
        glow(c, lx, ly, 160 * s, col, 0.8 * on)
        c.drawRect(skia.Rect.MakeXYWH(lx - 30 * s, ly - 8 * s, 60 * s, 16 * s), fill(rgb(col), 0.9))
    fx.dust(c, t, n=50, color=mix("#bcd8ff", "#ffb0b8", red), alpha=0.45, seed=3)


def wall_crack(c, t, x, y, open_amt, scale=1.0):
    """The red fracture splitting a tiled wall."""
    lines = fx.make_cracks(12, x, y, 380 * scale, -math.pi / 2, 5, 0.7, 16)
    fx.draw_cracks(c, lines, clamp(open_amt * 1.4), "#ff2a40", 4 * scale, 1.0, "#ffd0d8")
    if open_amt > 0.5:
        u = (open_amt - 0.5) * 2
        w = 160 * u * scale
        hh = 360 * scale
        rift = poly_path([(x, y - hh), (x + w * 0.4, y - hh * 0.5), (x + w * 0.2, y), (x + w * 0.5, y + hh * 0.4),
                          (x, y + hh * 0.6), (x - w * 0.4, y + hh * 0.3), (x - w * 0.2, y - hh * 0.2)])
        glow(c, x, y, 500 * u * scale, "#ff2a40", 0.8 * u)
        c.drawPath(rift, fill(rgb("#ffe0e4"), u))
        c.drawPath(rift, stroke(rgb("#ff2a40"), 10 * scale, alpha=u, blur=6, blend=ADD))
        fx.god_rays(c, x, y, t, n=9, length=1400 * scale, color="#ff4058", alpha=0.12 * u, spread=2.6,
                    angle=math.pi / 2, width=90)


# ======================================================================
#  Hunter Bureau control room
# ======================================================================
def control_room(c, t, alert=0.0, cam=0.0):
    c.drawRect(big_rect(), fill(0, shader=linear((0, 0), (0, H), [rgb("#04060e"), rgb("#0a1428")])))
    # wall of screens
    for r in range(3):
        for k in range(7):
            x = 120 + k * 250 - cam * 0.3
            y = 90 + r * 170
            sc = skia.Rect.MakeXYWH(x, y, 230, 150)
            red = alert > 0 and (k + r) % 3 == 0
            col = "#ff3048" if red else "#3aa0ff"
            glow(c, x + 115, y + 75, 220, col, 0.18)
            c.drawRect(sc, fill(rgb("#06101e")))
            # data: bars / graph / map
            if (k + r) % 3 == 0:
                for b in range(8):
                    hh = 20 + 90 * (0.5 + 0.5 * math.sin(t * 2 + b + k))
                    c.drawRect(skia.Rect.MakeXYWH(x + 14 + b * 26, y + 140 - hh, 16, hh), fill(rgb(col), 0.7))
            elif (k + r) % 3 == 1:
                p = skia.Path()
                p.moveTo(x + 10, y + 100)
                for q in range(1, 22):
                    p.lineTo(x + 10 + q * 10, y + 80 + 40 * math.sin(q * 0.7 + t * 3 + k))
                c.drawPath(p, stroke(rgb(col), 3, alpha=0.9))
            else:
                c.drawCircle(x + 115, y + 75, 50, stroke(rgb(col), 3, alpha=0.7))
                a = t * 2 + k
                c.drawLine(x + 115, y + 75, x + 115 + math.cos(a) * 50, y + 75 + math.sin(a) * 50,
                           stroke(rgb(col), 3))
            c.drawRect(sc, stroke(rgb(col), 3, alpha=0.6))
    # desks + operator silhouettes in the foreground
    c.drawRect(skia.Rect.MakeLTRB(-W, 820, 2 * W, 2 * H), fill(rgb("#020308")))
    for k in range(4):
        x = 260 + k * 460 - cam * 0.8
        c.drawPath(smooth_path([(x - 70, 820), (x - 60, 700), (x - 30, 660), (x + 30, 660), (x + 60, 700),
                                (x + 70, 820)]), fill(rgb("#010206")))
        c.drawCircle(x, 630, 46, fill(rgb("#010206")))
        c.drawLine(x - 50, 650, x + 50, 650, stroke(rgb("#3aa0ff"), 3, alpha=0.4))
    if alert > 0:
        c.drawRect(big_rect(), fill(rgb("#ff1030"), 0.12 * alert * (0.5 + 0.5 * math.sin(t * 6))))


def id_screen(c, t, glitch=0.0):
    """Big monitor: the salvager registry entry for Kai."""
    c.drawRect(big_rect(), fill(rgb("#030712")))
    r = skia.Rect.MakeXYWH(260, 140, 1400, 800)
    glow(c, W / 2, H / 2, 900, "#3aa0ff", 0.25)
    c.drawRect(r, fill(rgb("#06142a")))
    c.drawRect(r, stroke(rgb("#3aa0ff"), 4))
    for yy in range(140, 940, 6):
        c.drawLine(260, yy, 1660, yy, stroke(rgb("#000000"), 2, alpha=0.25))
    f1 = font("MPlusRounded1c-ExtraBold.ttf", 40)
    f2 = font("DelaGothicOne-Latin.ttf", 140)
    draw_text(c, "HUNTER BUREAU  /  SALVAGE REGISTRY", 300, 210, f1, "#8fc8ff", align="left")
    # photo box with a simplified portrait
    ph = skia.Rect.MakeXYWH(320, 270, 380, 460)
    c.drawRect(ph, fill(rgb("#0e2240")))
    c.drawRect(ph, stroke(rgb("#3aa0ff"), 3))
    from faultline.chars import Pose, draw_kai
    with Saved(c):
        c.clipRect(ph)
        draw_kai(c, 510, 470, 0.95, Pose(t=t, rim="#3aa0ff", rim_side=-1, rim_w=6))
    rows = [("NAME", "ARISAWA, KAI"), ("AGE", "19"), ("CLASS", "SALVAGE / NON-COMBAT"), ("GATE", "7-C  (SHINJUKU LINE)")]
    for i, (k, v) in enumerate(rows):
        draw_text(c, k, 760, 320 + i * 70, f1, "#5a8ac8", align="left")
        draw_text(c, v, 980, 320 + i * 70, f1, "#e8f2ff", align="left")
    draw_text(c, "RANK", 760, 640, f1, "#5a8ac8", align="left")
    jx = (hash01(int(t * 20), 1) - 0.5) * 40 * glitch
    if glitch < 0.5:
        draw_text(c, "F", 1060 + jx, 720, f2, "#e8f2ff", align="left")
    else:
        for dx, col in ((-8, "#ff3048"), (8, "#3aa0ff"), (0, "#ffffff")):
            draw_text(c, "?", 1060 + jx + dx, 720, f2, col, align="left")
        draw_text(c, "MEASUREMENT FAILED", 1200, 690, f1, "#ff3048", align="left")
    if glitch > 0:
        for i in range(6):
            yy = 140 + hash01(int(t * 15), i) * 800
            hh = 10 + 30 * hash01(int(t * 15), i, 2)
            c.drawRect(skia.Rect.MakeXYWH(260 + (hash01(i, int(t * 9)) - 0.5) * 60 * glitch, yy, 1400, hh),
                       fill(rgb("#3aa0ff" if i % 2 else "#ff3048"), 0.25 * glitch))


# ======================================================================
#  rooftop at night (ED)
# ======================================================================
def rooftop_night(c, t):
    city_dusk(c, t, pan=t * 4, gate=0.6, gate_pos=(1500, 200), gate_r=120, sky_top="#03040e",
              sky_mid="#0c1030", sky_low="#2a1840")
    c.drawRect(skia.Rect.MakeLTRB(-W, 900, 2 * W, 2 * H), fill(rgb("#05060a")))
    c.drawLine(-W, 900, 2 * W, 900, stroke(rgb("#3a4a7a"), 3))
    for k in range(-2, 30):
        c.drawLine(k * 80, 860, k * 80, 900, stroke(rgb("#05060a"), 6))
    c.drawLine(-W, 860, 2 * W, 860, stroke(rgb("#05060a"), 8))


# ======================================================================
#  rank crests (cold open)
# ======================================================================
RANK_COL = {"S": "#ffd25a", "A": "#ff4a60", "B": "#c070ff", "C": "#5ab0ff", "D": "#5ae0a0", "E": "#a0a8b8",
            "F": "#6a707e"}


def rank_crest(c, x, y, s, letter, alpha=1.0, t=0.0):
    col = RANK_COL[letter]
    with Saved(c):
        c.translate(x, y)
        c.scale(s, s)
        hexp = poly_path([(math.cos(a) * 120, math.sin(a) * 120) for a in
                          [math.pi / 6 + k * math.pi / 3 for k in range(6)]])
        glow(c, 0, 0, 260, col, 0.4 * alpha)
        c.drawPath(hexp, fill(rgb("#0a0c16"), alpha))
        c.drawPath(hexp, stroke(rgb(col), 10, alpha=alpha))
        inner = poly_path([(math.cos(a) * 96, math.sin(a) * 96) for a in
                           [math.pi / 6 + k * math.pi / 3 for k in range(6)]])
        c.drawPath(inner, stroke(rgb(col), 3, alpha=0.6 * alpha))
        draw_text(c, letter, 0, 52, font("DelaGothicOne-Latin.ttf", 150), col, alpha)

"""FAULTLINE characters (all original), drawn in a TV-action-anime style.

  Kai Arisawa     19, Rank-F salvager. Messy dark-brown hair, bandage on the
                  cheek, grey hoodie under an orange hi-vis salvage vest.
                  When his power wakes, his eyes turn gold and crack with light.
  Hana Kirishima  20, A-rank swordswoman. Black hair with crimson tips in a
                  high ponytail, red eyes, black high-collared coat with
                  crimson lining, a silver shoulder plate, a katana.
  Director Odaka  Head of the Hunter Bureau. Grey swept-back hair, glasses
                  that only ever show reflected screens.
  The Warden      A towering obsidian monster with one burning eye, curled
                  horns and glowing red seams in its armour.

Studio look: hard two-tone cel shadows, coloured rim lights, 3/4 head turns
(yaw) via a cylinder mapping of the face, tapered line art.
"""
import math
from dataclasses import dataclass

import skia

from gfx import (ADD, Saved, clamp, difference, fill, glow, lerp, linear, lock, mix, oval, poly_path,
                 radial, rgb, smooth_path, star_path, stroke, union, hash01)

INK = "#14101c"


@dataclass
class Pose:
    yaw: float = 0.0        # -1..1 head turn (positive = turns to screen right)
    tilt: float = 0.0       # degrees
    blink: float = 0.0
    mouth: float = 0.0
    smile: float = 0.0
    grit: float = 0.0       # clenched teeth
    brow: float = 0.0       # -1 angry/determined .. +1 worried
    look: tuple = (0.0, 0.0)
    surprise: float = 0.0
    hurt: float = 0.0       # pained squint
    awaken: float = 0.0     # Kai's gold eyes
    t: float = 0.0
    sway: float = 0.0
    light: float = 1.0      # key light direction: +1 from screen right, -1 from left
    rim: str = "#7fd4ff"    # rim light colour
    rim_side: float = -1.0  # which edge gets the rim (+1 right, -1 left)
    rim_w: float = 9.0      # rim width in local units
    shade: float = 1.0      # strength of cel shadow
    blush: float = 0.0
    sweat: float = 0.0


# ======================================================================
#  head rig (3/4 turns)
# ======================================================================
class Rig:
    def __init__(self, yaw):
        self.a = clamp(yaw, -1, 1) * 0.62  # radians

    def x(self, x, R=100.0):
        if abs(x) > R:
            R = abs(x)
        phi = math.asin(clamp(x / R, -1, 1)) + self.a
        return R * math.sin(clamp(phi, -math.pi / 2, math.pi / 2))

    def k(self, x, R=100.0):
        phi = math.asin(clamp(x / R, -1, 1)) + self.a
        return max(0.12, math.cos(clamp(phi, -math.pi / 2, math.pi / 2)))

    def P(self, pts, R=100.0):
        return [(self.x(px, R), py) for px, py in pts]

    def p(self, pt, R=100.0):
        return (self.x(pt[0], R), pt[1])


FACE = [(-88, -80), (-90, -10), (-84, 40), (-66, 80), (-36, 110), (-11, 127), (0, 129), (11, 127),
        (36, 110), (66, 80), (84, 40), (90, -10), (88, -80), (50, -118), (0, -126), (-50, -118)]


class Look:
    def __init__(self, skin, shade, line, iris_d, iris_l, hair_line, brow_col, lash=INK):
        self.skin, self.shade, self.line = skin, shade, line
        self.iris_d, self.iris_l = iris_d, iris_l
        self.hair_line, self.brow_col, self.lash = hair_line, brow_col, lash


def face_path(rig):
    return smooth_path(rig.P(FACE))


def draw_face(c, rig, lk, lw, ps: Pose, bangs=True):
    fp = face_path(rig)
    c.drawPath(fp, fill(rgb(lk.skin)))
    with Saved(c):
        c.clipPath(fp, doAntiAlias=True)
        # hard cel shadow on the side away from the key light
        s = -1 if ps.light > 0 else 1
        shp = [(s * 130, -150), (s * 30, -140), (s * 46, -50), (s * 58, 26), (s * 42, 92), (s * 12, 150),
               (s * 130, 150)]
        c.drawPath(smooth_path(rig.P(shp), tension=0.8), fill(rgb(lk.shade), 0.95 * ps.shade))
        # bangs cast shadow (zig-zag)
        if bangs:
            band = [(-130, -150), (130, -150), (130, -38)]
            for i in range(9):
                xx = 120 - i * 30
                band.append((xx, -20 if i % 2 else -44))
            band.append((-130, -30))
            c.drawPath(poly_path(rig.P(band)), fill(rgb(lk.shade), 0.95))
        # neck shadow under the jaw is drawn with the neck; blush
        if ps.blush > 0:
            for sx in (-1, 1):
                cx = rig.x(sx * 54)
                c.drawOval(skia.Rect.MakeXYWH(cx - 20, 50, 40, 14), fill(rgb("#ff7d8a"), 0.45 * ps.blush, blur=6))
    return fp


def face_outline(c, rig, lw, color):
    jaw = [(-90, -10), (-84, 40), (-66, 80), (-36, 110), (-11, 127), (0, 129), (11, 127), (36, 110),
           (66, 80), (84, 40), (90, -10)]
    c.drawPath(smooth_path(rig.P(jaw), closed=False), stroke(rgb(color), lw))


def draw_eye(c, rig, lk, lw, s, ps: Pose, gold=None):
    """Sharp almond action-anime eye. s=+1 screen-right eye, -1 screen-left."""
    op = clamp(1 - ps.blink) * (1 - 0.45 * ps.hurt)
    up = [(16, 14), (28, 3), (46, -2), (62, 3), (72, 12)]
    low = [(68, 20), (54, 27), (36, 27), (20, 22)]
    sq = ps.surprise * 5
    pivot = 24.0

    def tf(pts, upper):
        out = []
        for x, y in pts:
            yy = y - (sq if upper else -sq * 0.4)
            if upper and ps.brow < 0:
                yy += (-ps.brow) * 3 * (1 - abs(x - 44) / 30)  # determined: lid lowers in the middle
            yy = pivot + (yy - pivot) * op
            out.append(rig.p((s * x, yy)))
        return out

    U, Lo = tf(up, True), tf(low, False)
    if op < 0.15:
        p = smooth_path(U, closed=False)
        c.drawPath(p, stroke(rgb(lk.lash), lw * 1.5))
        return
    white = smooth_path(U + Lo, tension=0.85)
    c.drawPath(white, fill(rgb("#f4f1f2")))
    iris_d, iris_l = lk.iris_d, lk.iris_l
    if gold is not None and gold > 0:
        iris_d, iris_l = mix(iris_d, "#c07a08", gold), mix(iris_l, "#ffe48a", gold)
    with Saved(c):
        c.clipPath(white, doAntiAlias=True)
        cx = rig.x(s * 44 + ps.look[0] * 9)
        cy = 13 + ps.look[1] * 5
        kx = rig.k(s * 44)
        rx, ry = 13 * kx * (1 - 0.35 * ps.surprise), 15 * (1 - 0.3 * ps.surprise)
        c.drawPath(oval(cx, cy, rx, ry), fill(0, shader=linear((cx, cy - ry), (cx, cy + ry),
                   [rgb(mix(iris_d, "#000000", 0.3)), rgb(iris_d), rgb(iris_l)], [0, 0.45, 1])))
        c.drawPath(oval(cx, cy + 1, rx * 0.45, ry * 0.5), fill(rgb(INK)))
        c.drawPath(oval(cx, cy, rx, ry), stroke(rgb(INK), lw * 0.5))
        # lid shadow
        lid = smooth_path([(p[0], p[1] - 3) for p in U] + [(p[0], p[1] + 9) for p in reversed(U)])
        c.drawPath(lid, fill(rgb("#2a2030"), 0.35))
        c.drawCircle(cx - rx * 0.35, cy - ry * 0.45, 3.4 * kx + 0.6, fill(rgb("#ffffff")))
        if gold is not None and gold > 0:
            # cracks of light across the iris
            for k in range(5):
                a = k / 5 * math.tau + 0.4
                c.drawLine(cx, cy, cx + math.cos(a) * rx * 1.4, cy + math.sin(a) * ry * 1.4,
                           stroke(rgb("#fffbe0"), lw * 0.45, alpha=gold))
    c.drawPath(smooth_path(U, closed=False), stroke(rgb(lk.lash), lw * 1.9))
    ox, oy = U[-1]
    c.drawLine(ox, oy, ox + s * 8 * rig.k(s * 72), oy - 4, stroke(rgb(lk.lash), lw * 1.3))
    c.drawPath(smooth_path(Lo[:2], closed=False), stroke(rgb(lk.lash), lw * 0.7))
    if gold is not None and gold > 0:
        gx, gy = rig.x(s * 44), 13
        glow(c, gx, gy, 34, "#ffd25a", 0.45 * gold)


def draw_brows(c, rig, lk, lw, ps: Pose):
    for s in (-1, 1):
        inner_y = -24 - ps.brow * 7 - ps.surprise * 8
        outer_y = -31 + ps.brow * 4 - ps.surprise * 6
        if ps.brow < 0:
            inner_y = -18 + ps.brow * -2
        pts = [(s * 18, inner_y), (s * 44, min(inner_y, outer_y) - 6), (s * 74, outer_y),
               (s * 72, outer_y + 5), (s * 44, min(inner_y, outer_y) + 1), (s * 20, inner_y + 7)]
        c.drawPath(smooth_path(rig.P(pts), tension=0.6), fill(rgb(lk.brow_col)))


def draw_nose(c, rig, lk, lw, ps: Pose):
    tip = rig.p((2, 66))
    side = 1 if rig.a >= 0 else -1
    br = rig.p((-side * 6, 30))
    c.drawLine(br[0], br[1], tip[0], tip[1], stroke(rgb(mix(lk.shade, INK, 0.4)), lw * 0.6, alpha=0.6))
    c.drawLine(tip[0], tip[1], tip[0] - side * 8 * rig.k(0), tip[1] + 2, stroke(rgb(mix(lk.shade, INK, 0.5)), lw * 0.8))


def draw_mouth(c, rig, lk, lw, ps: Pose):
    cx = rig.x(0)
    kx = rig.k(0)
    y = 92
    m = clamp(ps.mouth)
    if ps.grit > 0.3 and m < 0.3:
        w = 22 * kx
        r = skia.Rect.MakeXYWH(cx - w, y - 6, w * 2, 11)
        c.drawRoundRect(r, 4, 4, fill(rgb("#f8f4f0")))
        c.drawLine(cx - w, y, cx + w, y, stroke(rgb(INK), lw * 0.5))
        c.drawRoundRect(r, 4, 4, stroke(rgb(INK), lw * 0.8))
        return
    if m < 0.08:
        w = 14 * kx
        p = skia.Path()
        p.moveTo(cx - w, y - ps.smile * 3 + ps.hurt * 2)
        p.quadTo(cx, y + ps.smile * 4 - ps.hurt * 3, cx + w, y - ps.smile * 3 + ps.hurt * 2)
        c.drawPath(p, stroke(rgb(mix(lk.shade, INK, 0.6)), lw * 0.9))
        return
    w = (10 + 8 * m) * kx + 4
    h = 5 + 22 * m
    p = skia.Path()
    p.moveTo(cx - w, y - 2)
    p.quadTo(cx, y - 5, cx + w, y - 2)
    p.quadTo(cx + w * 0.8, y + h, cx, y + h)
    p.quadTo(cx - w * 0.8, y + h, cx - w, y - 2)
    p.close()
    c.drawPath(p, fill(rgb("#5a1420")))
    with Saved(c):
        c.clipPath(p, doAntiAlias=True)
        c.drawRect(skia.Rect.MakeXYWH(cx - w, y - 6, w * 2, 6 + 2 * m), fill(rgb("#f6f2ee")))
        c.drawOval(skia.Rect.MakeXYWH(cx - w * 0.6, y + h * 0.55, w * 1.2, h * 0.7), fill(rgb("#c85a68")))
    c.drawPath(p, stroke(rgb(INK), lw * 0.8))


def draw_neck(c, rig, lk, lw):
    sh = rig.a * 14
    neck = poly_path([(-26 + sh, 80), (-30 + sh, 190), (30 + sh, 190), (26 + sh, 80)])
    c.drawPath(neck, fill(rgb(lk.skin)))
    with Saved(c):
        c.clipPath(neck, doAntiAlias=True)
        c.drawPath(smooth_path([(-60 + sh, 70), (-40 + sh, 130), (sh + 10, 160), (40 + sh, 130), (60 + sh, 70)]),
                   fill(rgb(lk.shade)))
    c.drawLine(-26 + sh, 104, -30 + sh, 186, stroke(rgb(lk.line), lw * 0.8))
    c.drawLine(26 + sh, 104, 30 + sh, 186, stroke(rgb(lk.line), lw * 0.8))


def rim_light(c, silhouette, ps: Pose, alpha=0.95, lw=3.0):
    if ps.rim_w <= 0:
        return
    shifted = skia.Path(silhouette)
    m = skia.Matrix()
    m.setTranslate(-ps.rim_side * ps.rim_w * 1.6, ps.rim_w * 0.4)
    shifted.transform(m)
    band = difference(silhouette, shifted)
    c.drawPath(band, fill(rgb(ps.rim), alpha))
    c.drawPath(silhouette, stroke(rgb(INK), lw))


def hair_mass(c, locks, base, shade, light, line, lw, hl_y=-108, extra=None):
    mass = union(*locks)
    c.drawPath(mass, fill(rgb(base)))
    with Saved(c):
        c.clipPath(mass, doAntiAlias=True)
        b = mass.getBounds()
        # hard cel shadow on the lower part of the hair
        sh = []
        xs = [b.left() + b.width() * i / 12 for i in range(13)]
        for i, x in enumerate(xs):
            sh.append((x, hl_y + 70 + (16 if i % 2 else -6)))
        sh += [(b.right(), b.bottom() + 10), (b.left(), b.bottom() + 10)]
        c.drawPath(poly_path(sh), fill(rgb(shade)))
        # sharp highlight streaks
        for i in range(7):
            x = b.left() + b.width() * (0.15 + i * 0.12)
            p = poly_path([(x - 8, hl_y), (x + 10, hl_y - 4), (x + 2, hl_y + 26 + (i % 3) * 6)])
            c.drawPath(p, fill(rgb(light), 0.85))
        if extra:
            extra(c, mass)
    with Saved(c):
        c.clipRect(skia.Rect.MakeLTRB(-1000, -96, 1000, 2000))
        for lk_ in locks[1:]:
            c.drawPath(lk_, stroke(rgb(line), lw * 0.55))
    c.drawPath(mass, stroke(rgb(line), lw))
    return mass


# ======================================================================
#  KAI
# ======================================================================
KAI_LOOK = Look(skin="#f2cdb4", shade="#c99383", line="#3a2420", iris_d="#3a4a68", iris_l="#8ea6cc",
                hair_line="#1a0e0a", brow_col="#2a1810")
KAI_HAIR = ("#4a2c1e", "#2a1810", "#8a5a3a")


def kai_locks(rig, ps):
    sw = ps.sway * 6
    R = 128
    crown = smooth_path(rig.P([(-112, -24), (-110, -100), (-76, -152), (-10, -172), (60, -160), (104, -116),
                               (114, -30), (60, -64), (0, -76), (-60, -64)], R))
    L = lambda a, b, tip, bend=0, belly=0.35: lock(rig.p(a, R), rig.p(b, R), rig.p(tip, R), bend, belly)  # noqa
    return [
        crown,
        # messy spikes sweeping to screen-right
        L((-116, -70), (-70, -112), (-112 + sw, 6), -8),
        L((-90, -116), (-36, -136), (-70 + sw, 30), -2, 0.45),
        L((-50, -134), (4, -140), (-26 + sw, 22), 6, 0.45),
        L((-14, -140), (40, -132), (24 + sw, 34), 10, 0.45),
        L((22, -134), (76, -114), (70 + sw, 10), 14, 0.45),
        L((60, -118), (108, -84), (114 + sw, 0), 14, 0.4),
        L((-20, -150), (20, -156), (-6 + sw, -10), 2, 0.2),
        # top spikes sticking up
        L((-70, -146), (-26, -162), (-96, -178), -14, 0.3),
        L((-24, -166), (30, -164), (6, -214), 4, 0.35),
        L((26, -162), (76, -138), (70, -196), 12, 0.3),
        L((66, -140), (104, -110), (130, -150), 10, 0.25),
        # side locks
        L((-120, -40), (-94, -60), (-118 + sw, 74), -6, 0.4),
        L((94, -60), (120, -40), (116 + sw, 64), 6, 0.4),
    ]


def kai_body(c, lw, ps):
    sh = ps.yaw * 26
    k = 1 - 0.18 * abs(ps.yaw)
    X = lambda x: x * k + sh  # noqa: E731
    hood_col, hood_sh = "#5a5f6e", "#3c404c"
    vest, vest_sh, refl = "#ff8a1a", "#c8601a", "#dfe4ee"
    body = smooth_path([(X(-32), 160), (X(-100), 180), (X(-162), 198), (X(-196), 236), (X(-210), 320),
                        (X(-214), 600), (X(214), 600), (X(210), 320), (X(196), 236), (X(162), 198),
                        (X(100), 180), (X(32), 160)])
    c.drawPath(body, fill(rgb(hood_col)))
    # hood bunched behind the neck
    hood = smooth_path([(X(-80), 150), (X(-40), 128), (X(40), 128), (X(80), 150), (X(60), 196), (X(-60), 196)])
    c.drawPath(hood, fill(rgb(hood_sh)))
    c.drawPath(hood, stroke(rgb(INK), lw * 0.8))
    # vest panels
    for s in (-1, 1):
        panel = smooth_path([(X(s * 46), 196), (X(s * 120), 186), (X(s * 182), 214), (X(s * 200), 300),
                             (X(s * 204), 600), (X(s * 60), 600), (X(s * 52), 360)], tension=0.7)
        c.drawPath(panel, fill(rgb(vest)))
        with Saved(c):
            c.clipPath(panel, doAntiAlias=True)
            for yy in (330, 450):
                c.drawRect(skia.Rect.MakeLTRB(-260, yy, 260, yy + 30), fill(rgb(refl)))
                c.drawRect(skia.Rect.MakeLTRB(-260, yy + 30, 260, yy + 34), fill(rgb("#8a92a6")))
            c.drawRect(skia.Rect.MakeLTRB(X(s * 130) if s < 0 else X(s * 130) - 200,
                                          150, X(s * 130) + (200 if s < 0 else 0), 620),
                       fill(rgb(vest_sh), 0.0))
        c.drawPath(panel, stroke(rgb(INK), lw * 0.9))
    # drawstrings
    for s in (-1, 1):
        c.drawLine(X(s * 14), 196, X(s * 18), 300, stroke(rgb("#e8e8ee"), lw * 1.2))
    # cel shadow on the side away from the light
    with Saved(c):
        c.clipPath(body, doAntiAlias=True)
        side = -1 if ps.light > 0 else 1
        c.drawPath(poly_path([(X(side * 120), 150), (X(side * 260), 150), (X(side * 260), 620),
                              (X(side * 150), 620)]), fill(rgb("#000000"), 0.28 * ps.shade))
        c.drawPath(smooth_path([(X(-90), 150), (X(0), 250), (X(90), 150)]), fill(rgb("#000000"), 0.25))
    c.drawPath(body, stroke(rgb(INK), lw))
    return body


def draw_kai(c, x, y, s, ps: Pose, body=True, lw_px=3.6):
    lw = lw_px / s
    rig = Rig(ps.yaw)
    with Saved(c):
        c.translate(x, y)
        c.rotate(ps.tilt)
        c.scale(s, s)
        parts = []
        if body:
            parts.append(kai_body(c, lw, ps))
        draw_neck(c, rig, KAI_LOOK, lw)
        fp = draw_face(c, rig, KAI_LOOK, lw, ps)
        draw_eye(c, rig, KAI_LOOK, lw, 1, ps, gold=ps.awaken)
        draw_eye(c, rig, KAI_LOOK, lw, -1, ps, gold=ps.awaken)
        draw_nose(c, rig, KAI_LOOK, lw, ps)
        draw_mouth(c, rig, KAI_LOOK, lw, ps)
        # bandage on the cheek
        bx = rig.x(-58)
        b = skia.Rect.MakeXYWH(bx - 16 * rig.k(-58), 46, 32 * rig.k(-58), 14)
        c.drawRoundRect(b, 3, 3, fill(rgb("#f4e6cc")))
        c.drawRoundRect(b, 3, 3, stroke(rgb("#a08a6a"), lw * 0.5))
        face_outline(c, rig, lw, KAI_LOOK.line)
        hm = hair_mass(c, kai_locks(rig, ps), *KAI_HAIR, KAI_LOOK.hair_line, lw)
        draw_brows(c, rig, KAI_LOOK, lw, ps)
        if ps.sweat > 0:
            sx = rig.x(80)
            c.drawPath(smooth_path([(sx, -40), (sx + 8, -18), (sx, -12), (sx - 8, -18)]),
                       fill(rgb("#cfe8ff"), ps.sweat))
        sil = union(fp, hm, *parts)
        rim_light(c, sil, ps, lw=lw)
        if ps.awaken > 0:
            glow(c, rig.x(0), 10, 160, "#ffcf4a", 0.07 * ps.awaken)


# ======================================================================
#  HANA
# ======================================================================
HANA_LOOK = Look(skin="#f6dccd", shade="#d39f94", line="#40222a", iris_d="#6a0e1c", iris_l="#ff5a6a",
                 hair_line="#06050a", brow_col="#141018")
HANA_HAIR = ("#17141f", "#08070c", "#4a4a6a")


def hana_back(c, rig, lw, ps):
    """High ponytail swinging behind the head."""
    sw = ps.sway * 22 + math.sin(ps.t * 2.2) * 8
    base = rig.p((-30, -150), 130)
    tail = [
        lock((base[0] - 30, base[1] - 10), (base[0] + 30, base[1] - 20), (base[0] - 150 + sw, 260), -40, 0.6),
        lock((base[0] - 20, base[1]), (base[0] + 34, base[1] - 6), (base[0] - 90 + sw, 330), -20, 0.55),
    ]
    for p in tail:
        c.drawPath(p, fill(rgb(HANA_HAIR[0])))
    with Saved(c):
        c.clipPath(union(*tail), doAntiAlias=True)
        c.drawRect(skia.Rect.MakeLTRB(-400, 160, 400, 600), fill(0, shader=linear((0, 160), (0, 330),
                   [rgb("#a01830", 0), rgb("#d82040")])))
    for p in tail:
        c.drawPath(p, stroke(rgb(HANA_LOOK.hair_line), lw * 0.8))
    back = smooth_path(rig.P([(-104, -130), (0, -160), (104, -130), (124, -20), (120, 80), (90, 120),
                              (-90, 120), (-120, 80), (-124, -20)], 130))
    c.drawPath(back, fill(rgb(HANA_HAIR[1])))
    return union(back, *tail)


def hana_locks(rig, ps):
    R = 128
    sw = ps.sway * 6
    L = lambda a, b, tip, bend=0, belly=0.35: lock(rig.p(a, R), rig.p(b, R), rig.p(tip, R), bend, belly)  # noqa
    crown = smooth_path(rig.P([(-114, -28), (-110, -104), (-70, -154), (0, -170), (70, -154), (110, -104),
                               (114, -28), (60, -70), (0, -80), (-60, -70)], R))
    return [
        crown,
        # long side-swept bangs over one eye
        L((-118, -76), (-40, -128), (-96 + sw, 34), -10, 0.45),
        L((-70, -126), (10, -140), (-40 + sw, 46), -4, 0.5),
        L((-20, -140), (60, -128), (14 + sw, 30), 4, 0.45),
        L((30, -132), (104, -94), (66 + sw, 8), 10, 0.4),
        L((70, -110), (116, -60), (104 + sw, 30), 8, 0.4),
        # long face-framing locks to the collarbone
        L((-124, -60), (-92, -76), (-110 + sw, 190), -8, 0.45),
        L((92, -76), (124, -60), (112 + sw, 190), 8, 0.45),
    ]


def hana_body(c, lw, ps):
    sh = ps.yaw * 26
    k = 1 - 0.18 * abs(ps.yaw)
    X = lambda x: x * k + sh  # noqa: E731
    coat, coat_l, lining = "#1a1622", "#2e2a3c", "#a01830"
    body = smooth_path([(X(-30), 160), (X(-96), 182), (X(-158), 200), (X(-192), 236), (X(-204), 320),
                        (X(-208), 600), (X(208), 600), (X(204), 320), (X(192), 236), (X(158), 200),
                        (X(96), 182), (X(30), 160)])
    c.drawPath(body, fill(rgb(coat)))
    with Saved(c):
        c.clipPath(body, doAntiAlias=True)
        side = -1 if ps.light > 0 else 1
        c.drawPath(poly_path([(X(-side * 60), 150), (X(-side * 260), 150), (X(-side * 260), 620),
                              (X(-side * 140), 620)]), fill(rgb(coat_l), 0.8))
    # high stand collar with crimson lining
    for s in (-1, 1):
        col = poly_path([(X(s * 30), 120), (X(s * 74), 110), (X(s * 92), 200), (X(s * 36), 214)])
        c.drawPath(col, fill(rgb(lining)))
        c.drawPath(col, stroke(rgb(INK), lw * 0.8))
        outer = poly_path([(X(s * 74), 110), (X(s * 100), 104), (X(s * 118), 206), (X(s * 92), 200)])
        c.drawPath(outer, fill(rgb(coat)))
        c.drawPath(outer, stroke(rgb(INK), lw * 0.8))
    # front closure + silver clasp
    c.drawLine(X(0), 214, X(0), 600, stroke(rgb("#0a0810"), lw * 1.2))
    for yy in (250, 330):
        c.drawRoundRect(skia.Rect.MakeXYWH(X(-18), yy, 36, 12), 4, 4, fill(rgb("#c8ccd8")))
    # silver shoulder plate (screen-left shoulder)
    plate = smooth_path([(X(-110), 186), (X(-176), 200), (X(-214), 250), (X(-200), 290), (X(-140), 250),
                         (X(-96), 220)])
    c.drawPath(plate, fill(0, shader=linear((X(-210), 190), (X(-100), 280), [rgb("#e6eaf2"), rgb("#7a8094")])))
    c.drawPath(plate, stroke(rgb(INK), lw))
    c.drawPath(body, stroke(rgb(INK), lw))
    return body


def draw_hana(c, x, y, s, ps: Pose, body=True, lw_px=3.6):
    lw = lw_px / s
    rig = Rig(ps.yaw)
    with Saved(c):
        c.translate(x, y)
        c.rotate(ps.tilt)
        c.scale(s, s)
        parts = [hana_back(c, rig, lw, ps)]
        if body:
            parts.append(hana_body(c, lw, ps))
        draw_neck(c, rig, HANA_LOOK, lw)
        fp = draw_face(c, rig, HANA_LOOK, lw, ps)
        draw_eye(c, rig, HANA_LOOK, lw, 1, ps)
        draw_eye(c, rig, HANA_LOOK, lw, -1, ps)
        draw_nose(c, rig, HANA_LOOK, lw, ps)
        draw_mouth(c, rig, HANA_LOOK, lw, ps)
        face_outline(c, rig, lw, HANA_LOOK.line)

        def tips(cc, mass):
            b = mass.getBounds()
            cc.drawRect(skia.Rect.MakeLTRB(b.left(), b.bottom() - 70, b.right(), b.bottom() + 5),
                        fill(0, shader=linear((0, b.bottom() - 70), (0, b.bottom()),
                                              [rgb("#c01c38", 0), rgb("#e02040")])))

        hm = hair_mass(c, hana_locks(rig, ps), *HANA_HAIR, HANA_LOOK.hair_line, lw, extra=tips)
        draw_brows(c, rig, HANA_LOOK, lw, ps)
        # red gem earring
        ex = rig.x(-92)
        c.drawCircle(ex, 62, 6, fill(rgb("#ff3050")))
        if ps.hurt > 0:
            # scratch on the cheek
            cx = rig.x(50)
            c.drawLine(cx - 14, 40, cx + 10, 30, stroke(rgb("#c02030"), lw * 0.7, alpha=ps.hurt))
        sil = union(fp, hm, *parts)
        rim_light(c, sil, ps, lw=lw)


# ======================================================================
#  DIRECTOR ODAKA (mostly in shadow)
# ======================================================================
DIR_LOOK = Look(skin="#d8b8a4", shade="#8a6a62", line="#2a1c1c", iris_d="#222222", iris_l="#555555",
                hair_line="#2a2a30", brow_col="#4a4a52")


def draw_director(c, x, y, s, ps: Pose, glare=1.0):
    lw = 3.6 / s
    rig = Rig(ps.yaw)
    with Saved(c):
        c.translate(x, y)
        c.scale(s, s)
        suit = smooth_path([(-34, 160), (-110, 184), (-180, 206), (-214, 260), (-224, 600), (224, 600),
                            (214, 260), (180, 206), (110, 184), (34, 160)])
        c.drawPath(suit, fill(rgb("#14161e")))
        c.drawPath(poly_path([(-34, 160), (0, 280), (34, 160)]), fill(rgb("#e8e8ee")))
        c.drawPath(poly_path([(-10, 176), (10, 176), (16, 290), (0, 310), (-16, 290)]), fill(rgb("#2a0e18")))
        for sgn in (-1, 1):
            c.drawPath(poly_path([(sgn * 34, 160), (sgn * 100, 186), (sgn * 30, 330)]), fill(rgb("#1c1f2a")))
        draw_neck(c, rig, DIR_LOOK, lw)
        fp = draw_face(c, rig, DIR_LOOK, lw, ps, bangs=False)
        draw_nose(c, rig, DIR_LOOK, lw, ps)
        draw_mouth(c, rig, DIR_LOOK, lw, ps)
        face_outline(c, rig, lw, DIR_LOOK.line)
        # swept-back grey hair
        hair = smooth_path(rig.P([(-104, -30), (-108, -100), (-80, -150), (0, -166), (80, -150), (108, -100),
                                  (104, -30), (92, -84), (40, -98), (0, -92), (-40, -98), (-92, -84)], 128))
        c.drawPath(hair, fill(rgb("#6a6c78")))
        with Saved(c):
            c.clipPath(hair, doAntiAlias=True)
            for k in range(-90, 100, 22):
                c.drawLine(k, -96, k * 1.2, -170, stroke(rgb("#9a9ca8"), lw * 0.8))
        c.drawPath(hair, stroke(rgb(INK), lw))
        draw_brows(c, rig, DIR_LOOK, lw, ps)
        # glasses: frames + screen glare
        for sgn in (-1, 1):
            cx = rig.x(sgn * 44)
            r = skia.Rect.MakeXYWH(cx - 30 * rig.k(sgn * 44), -4, 60 * rig.k(sgn * 44), 36)
            c.drawRect(r, fill(rgb("#bfe4ff"), 0.85 * glare))
            c.drawRect(skia.Rect.MakeXYWH(r.left() + 6, r.top() + 6, r.width() * 0.5, 6),
                       fill(rgb("#ffffff"), glare))
            c.drawRect(r, stroke(rgb("#0a0a10"), lw * 1.2))
        c.drawLine(rig.x(-14), 10, rig.x(14), 10, stroke(rgb("#0a0a10"), lw))
        sil = union(fp, hair, suit)
        rim_light(c, sil, ps, lw=lw)


# ======================================================================
#  THE WARDEN (monster) - angular obsidian armour
# ======================================================================
def _plate(c, pts, base, hi, rim, lw=4, seam=None):
    p = poly_path(pts)
    c.drawPath(p, fill(rgb(base)))
    # bevel: lighter top edge band
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    with Saved(c):
        c.clipPath(p, doAntiAlias=True)
        top = min(ys)
        c.drawRect(skia.Rect.MakeLTRB(min(xs) - 10, top - 10, max(xs) + 10, top + (max(ys) - top) * 0.28),
                   fill(rgb(hi), 0.9))
    c.drawPath(p, stroke(rgb("#05040a"), lw))
    c.drawPath(p, stroke(rgb(rim), lw * 0.6, alpha=0.7))
    return p


def warden(c, x, y, s, t, eye=1.0, jaw=0.0, crack=0.0, breathe=1.0, rim="#ff3a50"):
    """Head + shoulders + chest. Origin = centre of the chest core."""
    with Saved(c):
        c.translate(x, y)
        b = 1 + 0.012 * math.sin(t * 1.6) * breathe
        c.scale(s, s * b)
        obs, hi, seam = "#141019", "#2e2838", "#ff2a40"
        # back spikes
        for k in range(-3, 4):
            c.drawPath(poly_path([(k * 90 - 40, -300), (k * 110, -520 - abs(k) * -30), (k * 90 + 40, -300)]),
                       fill(rgb("#0c0a10")))
        # torso plates
        _plate(c, [(-280, -300), (280, -300), (330, -60), (250, 220), (-250, 220), (-330, -60)], obs, hi, rim)
        _plate(c, [(-250, 220), (250, 220), (200, 520), (-200, 520)], obs, hi, rim)
        for sg in (-1, 1):
            _plate(c, [(sg * 40, -280), (sg * 270, -280), (sg * 300, -80), (sg * 120, 0), (sg * 40, -80)], obs, hi, rim)
            _plate(c, [(sg * 60, 30), (sg * 230, -40), (sg * 230, 200), (sg * 60, 210)], obs, hi, rim)
        # glowing seams
        for (ax, ay, bx, by) in ((-280, -300, -40, -80), (280, -300, 40, -80), (-230, 210, 230, 210),
                                 (-300, -80, -120, 0), (300, -80, 120, 0)):
            c.drawLine(ax, ay, bx, by, stroke(rgb(seam), 7, alpha=0.75, blend=ADD))
        # shoulders: spiked pauldrons
        for sg in (-1, 1):
            _plate(c, [(sg * 220, -330), (sg * 420, -400), (sg * 560, -300), (sg * 600, -80), (sg * 520, 60),
                       (sg * 330, -20), (sg * 250, -160)], obs, hi, rim)
            for k in range(3):
                bx = sg * (330 + k * 90)
                c.drawPath(poly_path([(bx - 34, -380 + k * 30), (bx + sg * 30, -560 + k * 60), (bx + 34, -370 + k * 30)]),
                           fill(rgb("#221c2a")))
                c.drawPath(poly_path([(bx - 34, -380 + k * 30), (bx + sg * 30, -560 + k * 60), (bx + 34, -370 + k * 30)]),
                           stroke(rgb(rim), 3, alpha=0.7))
            c.drawLine(sg * 280, -300, sg * 520, -60, stroke(rgb(seam), 6, alpha=0.75, blend=ADD))
        # chest core (the weak point)
        pulse = 0.7 + 0.3 * math.sin(t * 3)
        glow(c, 0, 0, 200, "#ff3048", 0.65 * pulse)
        c.drawPath(poly_path([(0, -80), (60, 0), (0, 80), (-60, 0)]), fill(rgb("#ff4058")))
        c.drawPath(poly_path([(0, -40), (28, 0), (0, 40), (-28, 0)]), fill(rgb("#ffe0e4")))
        # head: angular helm
        with Saved(c):
            c.translate(0, -440)
            c.rotate(math.sin(t * 0.7) * 2)
            for sg in (-1, 1):  # horns
                horn = [(sg * 80, -70), (sg * 190, -170), (sg * 300, -190), (sg * 420, -330), (sg * 330, -230),
                        (sg * 220, -220), (sg * 140, -120)]
                c.drawPath(poly_path(horn), fill(rgb("#2a2433")))
                c.drawPath(poly_path(horn), stroke(rgb(rim), 4, alpha=0.75))
            jy = 70 + jaw * 130
            if jaw > 0.05:
                c.drawPath(poly_path([(-120, 40), (120, 40), (100, jy + 30), (-100, jy + 30)]), fill(rgb("#c01828")))
                glow(c, 0, 60 + jaw * 60, 200, "#ff3048", 0.7 * jaw)
                for k in range(-4, 5):
                    c.drawPath(poly_path([(k * 26 - 11, 40), (k * 26 + 11, 40), (k * 26, 84)]), fill(rgb("#efe6e0")))
                    c.drawPath(poly_path([(k * 26 - 11, jy + 30), (k * 26 + 11, jy + 30), (k * 26, jy - 10)]),
                               fill(rgb("#efe6e0")))
            _plate(c, [(-130, 40), (130, 40), (110, jy + 40), (40, jy + 80), (-40, jy + 80), (-110, jy + 40)], obs, hi, rim)
            _plate(c, [(-170, -100), (-60, -170), (60, -170), (170, -100), (160, 40), (60, 60), (-60, 60), (-160, 40)],
                   obs, hi, rim)
            # brow ridge
            c.drawPath(poly_path([(-160, -40), (0, -10), (160, -40), (150, -70), (0, -46), (-150, -70)]),
                       fill(rgb("#0a080e")))
            ea = clamp(eye)
            glow(c, 0, -2, 260 * (0.6 + 0.4 * ea), "#ff2030", 0.85 * ea)
            c.drawPath(poly_path([(-90, 0), (0, -26), (90, 0), (0, 22)]), fill(rgb("#ff3a30"), ea))
            c.drawPath(poly_path([(-8, -24), (8, -24), (6, 20), (-6, 20)]), fill(rgb("#fff0c0"), ea))
        if crack > 0:
            from faultline.fx import draw_cracks, make_cracks
            draw_cracks(c, make_cracks(31, 0, 0, 700, 0, 9, 0.55, 26), crack, "#ffd86a", 6, 1.0)


def warden_claw(c, x, y, s, angle=0.0, rim="#ff3a50"):
    with Saved(c):
        c.translate(x, y)
        c.rotate(angle)
        c.scale(s, s)
        _plate(c, [(-1000, -110), (-300, -140), (-40, -100), (30, 0), (-40, 100), (-300, 130), (-1000, 130)],
               "#141019", "#2e2838", rim, 5)
        for k in range(-8, 0):
            c.drawPath(poly_path([(k * 110, -120), (k * 110 + 40, -200), (k * 110 + 70, -120)]), fill(rgb("#221c2a")))
        for k, a in enumerate((-0.55, 0.0, 0.55)):
            ca, sa = math.cos(a), math.sin(a)
            p = [(0, -50 + k * 50), (200 * ca - 30 * sa, 200 * sa - 25 + k * 20), (380 * ca, 380 * sa + 40 * a),
                 (190 * ca + 30 * sa, 190 * sa + 25 + k * 10)]
            c.drawPath(poly_path(p), fill(rgb("#2a2433")))
            c.drawPath(poly_path(p), stroke(rgb(rim), 4, alpha=0.85))
        c.drawLine(-800, -10, -60, -20, stroke(rgb("#ff2a40"), 7, alpha=0.8, blend=ADD))


# ======================================================================
#  full-body action figures (posed skeleton)
# ======================================================================
POSES = {
    # lean, head, front upper/lower arm, back upper/lower arm, front upper/lower leg, back upper/lower leg
    "idle":    dict(lean=0, head=0, uaf=12, laf=8, uab=-10, lab=-6, ulf=4, llf=0, ulb=-4, llb=0),
    "run_a":   dict(lean=18, head=-6, uaf=-50, laf=-80, uab=60, lab=-40, ulf=-50, llf=40, ulb=40, llb=70),
    "run_b":   dict(lean=18, head=-6, uaf=60, laf=-40, uab=-50, lab=-80, ulf=40, llf=70, ulb=-50, llb=40),
    "dash":    dict(lean=42, head=-30, uaf=70, laf=10, uab=100, lab=20, ulf=-70, llf=60, ulb=50, llb=40),
    "slash":   dict(lean=30, head=-20, uaf=-95, laf=-5, uab=-80, lab=-10, ulf=-60, llf=30, ulb=55, llb=10),
    "ready":   dict(lean=8, head=-4, uaf=-40, laf=-70, uab=-30, lab=-80, ulf=-25, llf=20, ulb=25, llb=10),
    "hurt":    dict(lean=-35, head=25, uaf=120, laf=30, uab=140, lab=40, ulf=-40, llf=50, ulb=30, llb=60),
    "down":    dict(lean=-10, head=20, uaf=20, laf=40, uab=-10, lab=30, ulf=-85, llf=80, ulb=-80, llb=100),
    "strike":  dict(lean=35, head=-15, uaf=-150, laf=-20, uab=40, lab=-30, ulf=-60, llf=40, ulb=60, llb=20),
    "strike2": dict(lean=40, head=-10, uaf=-60, laf=0, uab=60, lab=-20, ulf=-70, llf=50, ulb=70, llb=10),
    "crouch":  dict(lean=25, head=-10, uaf=-30, laf=-60, uab=20, lab=-40, ulf=-90, llf=110, ulb=10, llb=120),
    "slide":   dict(lean=-50, head=10, uaf=-120, laf=-20, uab=50, lab=-20, ulf=-80, llf=10, ulb=-40, llb=60),
}


def blend_pose(a, b, u):
    pa, pb = POSES[a], POSES[b]
    return {k: lerp(pa[k], pb[k], u) for k in pa}


def _seg(ax, ay, bx, by, wa, wb):
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy) + 1e-6
    nx, ny = -dy / L, dx / L
    p = poly_path([(ax + nx * wa, ay + ny * wa), (bx + nx * wb, by + ny * wb), (bx - nx * wb, by - ny * wb),
                   (ax - nx * wa, ay - ny * wa)])
    j = skia.Path()
    j.addCircle(bx, by, wb)
    k = skia.Path()
    k.addCircle(ax, ay, wa)
    return union(p, j, k)


def _limb(c, x0, y0, a0, l0, w0, a1, l1, w1, col, line, lw, shade=None):
    r0, r1 = math.radians(a0), math.radians(a0 + a1)
    x1, y1 = x0 + math.sin(r0) * l0, y0 + math.cos(r0) * l0
    x2, y2 = x1 + math.sin(r1) * l1, y1 + math.cos(r1) * l1
    wm = (w0 + w1) / 2
    path = union(_seg(x0, y0, x1, y1, w0, wm), _seg(x1, y1, x2, y2, wm, w1))
    c.drawPath(path, fill(rgb(col)))
    if shade:
        with Saved(c):
            c.clipPath(path, doAntiAlias=True)
            c.drawPath(_seg(x0 + 10, y0, x1 + 10, y1, w0 * 0.5, wm * 0.5), fill(rgb(shade), 0.8))
    c.drawPath(path, stroke(rgb(line), lw))
    return (x2, y2), path


def draw_figure(c, who, x, y, h, pose, t=0.0, facing=1, rim="#7fd4ff", rim_side=-1, weapon_glow=0.0,
                eye_glow=0.0, blur=0.0, coat_wave=1.0, silhouette=0.0):
    """(x, y) = hip position; h = full height in px. Faces +x when facing=1."""
    s = h / 1000.0
    lw = 2.8 / s
    if who == "kai":
        top, arm, leg, shoe, hair, skin = "#ff8a1a", "#5a5f6e", "#2a3048", "#26262c", "#4a2c1e", "#f2cdb4"
    else:
        top, arm, leg, shoe, hair, skin = "#1e1a28", "#1e1a28", "#14121c", "#0a0a10", "#17141f", "#f6dccd"
    if silhouette > 0:
        top = arm = leg = shoe = hair = skin = mix("#0a0810", top, 1 - silhouette) if silhouette < 1 else "#0a0810"
    layer = None
    if blur > 0:
        layer = skia.Paint()
        layer.setImageFilter(skia.ImageFilters.Blur(blur, blur * 0.12))
        c.saveLayer(None, layer)
    with Saved(c):
        c.translate(x, y)
        c.scale(s * facing, s)
        P = pose
        lean = math.radians(P["lean"])
        ca, sa = math.cos(lean), math.sin(lean)
        sx, sy = sa * 340, -ca * 340
        parts = []
        dark = lambda col: mix(col, "#000000", 0.4)  # noqa: E731
        _, pl = _limb(c, sx - ca * 40, sy - sa * 40, 180 + P["uab"], 160, 34, P["lab"], 150, 26, dark(arm), INK, lw)
        parts.append(pl)
        _, pl = _limb(c, -10, 0, P["ulb"], 220, 46, P["llb"], 220, 32, dark(leg), INK, lw)
        parts.append(pl)
        if who == "hana":
            wv = math.sin(t * 9) * 30 * coat_wave
            tail = poly_path([(-50, -60), (50, -60), (30 - P["lean"] * 2, 300 + wv * 0.3),
                              (-90 - P["lean"] * 5, 380 + wv), (-200 - P["lean"] * 7, 300 - wv),
                              (-120 - P["lean"] * 4, 140)])
            c.drawPath(tail, fill(rgb(mix(top, "#000000", 0.2))))
            c.drawPath(tail, stroke(rgb("#b01c34"), lw * 1.6))
            parts.append(tail)
        # torso: shoulders -> waist -> hips
        shl = (sx - ca * 92, sy - sa * 92)
        shr = (sx + ca * 92, sy + sa * 92)
        wl = (sa * 150 - ca * 56, -ca * 150 - sa * 56)
        wr = (sa * 150 + ca * 56, -ca * 150 + sa * 56)
        tor = poly_path([(-64, 20), (64, 20), wr, shr, (sx + sa * 30, sy - ca * 30), shl, wl])
        c.drawPath(tor, fill(rgb(top)))
        with Saved(c):
            c.clipPath(tor, doAntiAlias=True)
            if who == "kai":
                for f in (0.38, 0.62):
                    c.drawLine(-260, sy * f + 30, 260, sy * f - 30, stroke(rgb("#dfe4ee"), 24))
                c.drawPath(poly_path([shl, (sx, sy - 40), shr, (sx + sa * -60, sy + ca * 60)]), fill(rgb(arm)))
            c.drawPath(poly_path([(-200, 40), (-20, 40), (sx - 20, sy - 60), (-200, sy - 60)]),
                       fill(rgb("#000000"), 0.3))
        c.drawPath(tor, stroke(rgb(INK), lw))
        parts.append(tor)
        # head (profile facing +x)
        hx, hy = sx + sa * 110, sy - ca * 110
        with Saved(c):
            c.translate(hx, hy)
            c.rotate(P["head"] + P["lean"] * 0.35)
            if who == "kai":  # hood lump
                c.drawPath(smooth_path([(-80, 60), (-40, 90), (30, 90), (0, 50)]), fill(rgb(arm)))
            head = smooth_path([(-56, -50), (10, -70), (58, -40), (66, -6), (80, 10), (64, 22), (58, 50),
                                (30, 76), (-30, 70), (-62, 20)], tension=0.7)
            c.drawPath(head, fill(rgb(skin)))
            with Saved(c):
                c.clipPath(head, doAntiAlias=True)
                c.drawRect(skia.Rect.MakeLTRB(-80, -80, 0, 90), fill(rgb("#000000"), 0.22))
            if who == "kai":
                spikes = [(-74, 30), (-100, -40), (-70, -60), (-96, -110), (-30, -96), (-10, -146), (24, -102),
                          (96, -110), (66, -56), (82, -30), (40, -44), (16, -20), (-30, -36), (-40, 10)]
            else:
                spikes = [(-74, 40), (-80, -50), (-36, -96), (36, -98), (78, -56), (84, 6), (56, -30), (20, -40),
                          (-30, -30), (-40, 30)]
            hp = poly_path(spikes)
            c.drawPath(hp, fill(rgb(hair)))
            if who == "hana":
                sw = math.sin(t * 6)
                pt = smooth_path([(-40, -86), (-190 - 40 * sw, -60), (-300, 20 + 30 * sw), (-180, 0), (-70, -40)])
                c.drawPath(pt, fill(rgb(hair)))
                c.drawPath(pt, stroke(rgb("#e02040"), lw * 1.4))
            c.drawPath(head, stroke(rgb(INK), lw))
            c.drawPath(hp, stroke(rgb(INK), lw))
            c.drawLine(36, -2, 56, -4, stroke(rgb(INK), lw * 1.6))
            if eye_glow > 0:
                c.drawLine(32, -4, 60, -6, stroke(rgb("#ffe48a"), 10, alpha=eye_glow))
                glow(c, 46, -4, 80, "#ffcf4a", eye_glow)
                c.drawLine(46, -4, -260, 14, stroke(rgb("#ffd86a"), 7, alpha=0.6 * eye_glow, blur=3, blend=ADD))
            parts.append(union(head, hp))
        (fx_, fy_), pl = _limb(c, 10, 0, P["ulf"], 220, 48, P["llf"], 220, 34, leg, INK, lw)
        parts.append(pl)
        fa = math.radians(P["ulf"] + P["llf"])
        shoe_p = poly_path([(fx_ - 30, fy_ - 20), (fx_ + 60 * math.cos(fa) + 20, fy_ - 10 + 60 * math.sin(fa) * 0),
                            (fx_ + 70, fy_ + 26), (fx_ - 34, fy_ + 30)])
        c.drawPath(shoe_p, fill(rgb(shoe)))
        c.drawPath(shoe_p, stroke(rgb(INK), lw))
        (hx2, hy2), pl = _limb(c, sx + ca * 30, sy + sa * 30, 180 + P["uaf"], 160, 36, P["laf"], 150, 27, arm, INK, lw)
        parts.append(pl)
        c.drawCircle(hx2, hy2, 28, fill(rgb(skin)))
        c.drawCircle(hx2, hy2, 28, stroke(rgb(INK), lw))
        wa = math.radians(180 + P["uaf"] + P["laf"])
        if who == "hana":
            ex, ey = hx2 + math.sin(wa) * 560, hy2 + math.cos(wa) * 560
            c.drawLine(hx2, hy2, ex, ey, stroke(rgb("#ff2a4a"), 34, alpha=0.35 * weapon_glow + 0.1, blur=10, blend=ADD))
            c.drawLine(hx2, hy2, ex, ey, stroke(rgb("#eef2fa"), 13))
            c.drawLine(hx2 - math.sin(wa) * 80, hy2 - math.cos(wa) * 80, hx2, hy2, stroke(rgb("#2a1018"), 20))
            c.drawLine(hx2 - 30 * math.cos(wa), hy2 + 30 * math.sin(wa), hx2 + 30 * math.cos(wa),
                       hy2 - 30 * math.sin(wa), stroke(rgb("#c8a040"), 10))
        elif who == "kai" and weapon_glow >= 0:
            ex, ey = hx2 + math.sin(wa) * 400, hy2 + math.cos(wa) * 400
            if weapon_glow > 0:
                c.drawLine(hx2, hy2, ex, ey, stroke(rgb("#ffd86a"), 40, alpha=0.6 * weapon_glow, blur=12, blend=ADD))
            c.drawLine(hx2 - math.sin(wa) * 50, hy2 - math.cos(wa) * 50, ex, ey, stroke(rgb("#6a707e"), 22))
            c.drawLine(hx2, hy2, ex, ey, stroke(rgb("#c8ccd8"), 7))
        sil = union(*parts)
        shifted = skia.Path(sil)
        m = skia.Matrix()
        m.setTranslate(-rim_side * 16, 5)
        shifted.transform(m)
        c.drawPath(difference(sil, shifted), fill(rgb(rim), 0.95))
        c.drawPath(sil, stroke(rgb(INK), lw * 1.2))
    if layer is not None:
        c.restore()

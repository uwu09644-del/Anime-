"""Original characters for STARFALL KEEPER, drawn entirely with vector code.

Cast
  Mio Tsukishima  - 16, granddaughter of the lighthouse keeper. Navy bob with a
                    side ponytail, amber eyes, yellow raincoat, star hair clip.
  Lumi            - a star that fell from the sky. Long silver hair that floats,
                    gold eyes with star-shaped pupils, soft white glow.
  Grandpa Genzo   - the lighthouse keeper. Captain's cap, white moustache,
                    cream fisherman's sweater, permanently kind squint.
  The Collector   - a hooded figure who keeps stars in a lantern.

Portrait coordinates: the head is ~220 units wide, origin between the eyes,
chin at y=+119, crown at y=-166. The torso continues down to about y=+520.
"""
import math
from dataclasses import dataclass

import skia

from gfx import (ADD, Saved, clamp, difference, fill, glow, lerp, lock, mix,
                 oval, poly_path, radial, linear, rgb, smooth_path, sparkle,
                 star_path, stroke, union, hash01)

LINE = "#2b1d2e"


@dataclass
class Expr:
    blink: float = 0.0      # 0 open .. 1 closed
    mouth: float = 0.0      # 0 closed .. 1 wide open (lip sync)
    smile: float = 0.3      # 0 neutral .. 1 big smile
    look: tuple = (0.0, 0.0)  # iris offset (-1..1)
    brow: float = 0.0       # -1 angry .. 0 .. +1 worried
    blush: float = 0.0
    surprise: float = 0.0   # wide eyes, tiny pupils
    happy_eyes: float = 0.0  # ^^ closed smiling eyes
    sway: float = 0.0       # hair sway (-1..1)
    t: float = 0.0          # time, for floating hair / glows
    glow: float = 0.0       # Lumi's light strength
    tear: float = 0.0
    sad: float = 0.0        # droopy eyes / mouth down


# ======================================================================
#  Shared face construction
# ======================================================================
FACE_PTS = [(-90, -80), (-92, -10), (-86, 38), (-70, 72), (-40, 100), (-13, 116),
            (0, 119), (13, 116), (40, 100), (70, 72), (86, 38), (92, -10),
            (90, -80), (50, -118), (0, -126), (-50, -118)]


class Style:
    """Per-character palette and proportions."""

    def __init__(self, skin, skin_shade, iris_dark, iris_light, hair_line,
                 eye_scale=1.0, line=LINE, star_pupil=False, brow_col=None,
                 lash_col=None):
        self.skin = skin
        self.skin_shade = skin_shade
        self.iris_dark = iris_dark
        self.iris_light = iris_light
        self.hair_line = hair_line
        self.eye_scale = eye_scale
        self.line = line
        self.star_pupil = star_pupil
        self.brow_col = brow_col or hair_line
        self.lash_col = lash_col or LINE


def draw_neck(c, st, lw):
    neck = poly_path([(-27, 70), (-30, 175), (30, 175), (27, 70)])
    c.drawPath(neck, fill(rgb(st.skin)))
    with Saved(c):
        c.clipPath(neck, doAntiAlias=True)
        sh = smooth_path([(-40, 60), (-36, 100), (0, 150), (36, 100), (40, 60)], closed=True)
        c.drawPath(sh, fill(rgb(st.skin_shade)))
    c.drawLine(-27, 95, -30, 172, stroke(rgb(st.line), lw * 0.8))
    c.drawLine(27, 95, 30, 172, stroke(rgb(st.line), lw * 0.8))


def draw_ears(c, st, lw):
    for s in (-1, 1):
        e = oval(s * 90, 16, 13, 22)
        c.drawPath(e, fill(rgb(st.skin)))
        c.drawPath(e, stroke(rgb(st.line), lw * 0.8))
        c.drawArc(skia.Rect.MakeXYWH(s * 90 - 6, 6, 12, 22), 90 if s > 0 else -90, 180, False,
                  stroke(rgb(st.skin_shade), lw * 0.7))


def face_path():
    return smooth_path(FACE_PTS)


def draw_face_base(c, st, lw, ex: Expr):
    fp = face_path()
    c.drawPath(fp, fill(rgb(st.skin)))
    with Saved(c):
        c.clipPath(fp, doAntiAlias=True)
        # soft shading at the sides of the face
        c.drawPath(fp, fill(0, shader=linear((-95, 0), (95, 0),
                   [rgb(st.skin_shade, 0.55), rgb(st.skin_shade, 0.0), rgb(st.skin_shade, 0.0),
                    rgb(st.skin_shade, 0.35)], [0, 0.22, 0.75, 1])))
        # cel shadow cast by the bangs
        band = smooth_path([(-100, -130), (100, -130), (100, -30), (70, -14), (40, -26), (10, -8),
                            (-20, -22), (-55, -10), (-85, -24), (-100, -20)])
        c.drawPath(band, fill(rgb(st.skin_shade, 0.9)))
        # blush
        if ex.blush > 0.01:
            for s in (-1, 1):
                c.drawOval(skia.Rect.MakeXYWH(s * 55 - 24, 48, 48, 18),
                           fill(rgb("#ff7d92"), 0.5 * ex.blush, blur=7))
                if ex.blush > 0.45:
                    for k in range(3):
                        x0 = s * 55 - 14 + k * 10
                        c.drawLine(x0 + 4, 50, x0 - 2, 62,
                                   stroke(rgb("#e0526e"), lw * 0.45, alpha=ex.blush * 0.8))
    return fp


def draw_face_outline(c, st, lw):
    jaw = smooth_path([(-92, -10), (-86, 38), (-70, 72), (-40, 100), (-13, 116), (0, 119),
                       (13, 116), (40, 100), (70, 72), (86, 38), (92, -10)], closed=False)
    c.drawPath(jaw, stroke(rgb(st.line), lw))


def _eye_white_pts(s):
    up = [(18, 16), (30, 0), (48, -7), (65, -2), (77, 11)]
    low = [(74, 18), (66, 36), (50, 45), (32, 41), (21, 26)]
    return [(s * x, y) for x, y in up], [(s * x, y) for x, y in low]


def draw_eye(c, st, lw, s, ex: Expr):
    """s = +1 (screen-right eye) or -1 (screen-left eye)."""
    sc = st.eye_scale
    openness = clamp(1 - ex.blink)
    if ex.happy_eyes > 0.5:
        # ^ ^ closed smiling eye
        p = skia.Path()
        p.moveTo(s * 20, 30)
        p.quadTo(s * 47, -4, s * 76, 26)
        c.drawPath(p, stroke(rgb(st.lash_col), lw * 1.6))
        return
    if openness < 0.18:
        p = skia.Path()
        p.moveTo(s * 18, 26)
        p.quadTo(s * 48, 40 + ex.sad * 4, s * 78, 22)
        c.drawPath(p, stroke(rgb(st.lash_col), lw * 1.5))
        c.drawLine(s * 76, 22, s * 84, 16, stroke(rgb(st.lash_col), lw * 0.9))
        return

    pivot = 40.0
    cx0 = s * 47

    def tf(pts):
        out = []
        for x, y in pts:
            y2 = pivot + (y - pivot) * openness
            # sad: droop outer corner
            if ex.sad > 0 and abs(x) > 55:
                y2 += ex.sad * 6 * (abs(x) - 55) / 22
            # widen with surprise
            y2 = pivot + (y2 - pivot) * (1 + 0.12 * ex.surprise)
            out.append((cx0 + (x - cx0) * sc, 20 + (y2 - 20) * sc))
        return out

    up, low = _eye_white_pts(s)
    up, low = tf(up), tf(low)
    white = smooth_path(up + low, closed=True, tension=0.9)
    c.drawPath(white, fill(rgb("#fffaf7")))
    with Saved(c):
        c.clipPath(white, doAntiAlias=True)
        ix = cx0 + ex.look[0] * 12 * s * s
        iy = 22 + ex.look[1] * 8
        rx, ry = 19 * sc, 26 * sc
        iris = oval(ix, iy, rx, ry)
        c.drawPath(iris, fill(0, shader=linear((ix, iy - ry), (ix, iy + ry),
                   [rgb(st.iris_dark), rgb(st.iris_dark), rgb(st.iris_light)], [0, 0.35, 1])))
        c.drawPath(iris, stroke(rgb(mix(st.iris_dark, "#000000", 0.4)), lw * 0.6))
        pr = 1.0 - 0.55 * ex.surprise
        if st.star_pupil:
            c.drawPath(star_path(ix, iy + 2, 12 * sc * pr, 4 * sc * pr, 4, rot=ex.t * 0.4),
                       fill(rgb("#fff6c9")))
            glow(c, ix, iy + 2, 14 * sc, "#fff2a0", 0.5)
        else:
            c.drawPath(oval(ix, iy + 1, 9 * sc * pr, 13 * sc * pr),
                       fill(rgb(mix(st.iris_dark, "#000000", 0.55))))
        # lower iris glow
        c.drawOval(skia.Rect.MakeXYWH(ix - 12 * sc, iy + 6 * sc, 24 * sc, 16 * sc),
                   fill(rgb(st.iris_light), 0.6, blur=4))
        # lid shadow
        lid = smooth_path([(p[0], p[1] - 2) for p in up] + [(p[0], p[1] + 12) for p in reversed(up)],
                          closed=True)
        c.drawPath(lid, fill(rgb(st.iris_dark), 0.35, blur=2))
        # highlights
        c.drawOval(skia.Rect.MakeXYWH(ix - 12 * sc, iy - 18 * sc, 11 * sc, 14 * sc), fill(rgb("#ffffff")))
        c.drawCircle(ix + 8 * sc, iy + 11 * sc, 3.2 * sc, fill(rgb("#ffffff"), 0.9))
    # upper lash line
    lash = smooth_path(up, closed=False)
    c.drawPath(lash, stroke(rgb(st.lash_col), lw * 2.1))
    ox, oy = up[-1]
    c.drawLine(ox, oy, ox + s * 9 * sc, oy - 7 * sc, stroke(rgb(st.lash_col), lw * 1.2))
    c.drawLine(ox - s * 4, oy - 3, ox + s * 5 * sc, oy - 12 * sc, stroke(rgb(st.lash_col), lw * 0.8))
    # lower lash
    lx0, ly0 = low[0]
    lx1, ly1 = low[1]
    c.drawLine(lx0, ly0 + 2, lx1, ly1 + 2, stroke(rgb(st.lash_col), lw * 0.7))
    # crease
    cr = skia.Path()
    cr.moveTo(s * 32, up[1][1] - 9)
    cr.quadTo(s * 50, up[2][1] - 12, s * 66, up[3][1] - 8)
    c.drawPath(cr, stroke(rgb(st.line), lw * 0.45, alpha=0.6))
    # tear
    if ex.tear > 0.01:
        ty = low[2][1] + 4 + ex.tear * 40
        tx = s * 60
        c.drawPath(smooth_path([(tx, ty - 14), (tx + 6, ty), (tx, ty + 6), (tx - 6, ty)]),
                   fill(rgb("#bfe6ff"), 0.8 * min(1, ex.tear * 3)))


def draw_brows(c, st, lw, ex: Expr, alpha=0.95):
    for s in (-1, 1):
        inner_y = -30 - ex.brow * 9 + ex.surprise * -8
        outer_y = -34 + ex.brow * 5 + ex.surprise * -8 + ex.sad * 4
        p = skia.Path()
        p.moveTo(s * 22, inner_y)
        p.quadTo(s * 46, min(inner_y, outer_y) - 7, s * 70, outer_y)
        c.drawPath(p, stroke(rgb(st.brow_col), lw * 1.2, alpha=alpha))


def draw_nose(c, st, lw):
    c.drawLine(4, 55, 0, 60, stroke(rgb(mix(st.skin_shade, LINE, 0.3)), lw * 0.7))


def draw_mouth(c, st, lw, ex: Expr, y=84):
    m = clamp(ex.mouth)
    s = clamp(ex.smile) - ex.sad * 0.8
    if m < 0.08:
        p = skia.Path()
        w = 11 + 5 * max(s, 0)
        p.moveTo(-w, y - s * 3)
        p.quadTo(0, y + 5 * s, w, y - s * 3)
        c.drawPath(p, stroke(rgb(mix(st.skin_shade, LINE, 0.55)), lw * 0.9))
        return
    w = 9 + 7 * max(s, 0) + 5 * m
    h = 4 + 20 * m
    p = skia.Path()
    p.moveTo(-w, y - 1)
    p.quadTo(0, y - 4 + 2 * s, w, y - 1)
    p.quadTo(w * 0.7, y + h * 0.9, 0, y + h)
    p.quadTo(-w * 0.7, y + h * 0.9, -w, y - 1)
    p.close()
    c.drawPath(p, fill(rgb("#7a2638")))
    with Saved(c):
        c.clipPath(p, doAntiAlias=True)
        c.drawOval(skia.Rect.MakeXYWH(-w * 0.7, y + h * 0.45, w * 1.4, h * 0.9), fill(rgb("#e6727f")))
        if s > 0.4:
            c.drawRect(skia.Rect.MakeXYWH(-w, y - 6, w * 2, 5), fill(rgb("#ffffff")))
    c.drawPath(p, stroke(rgb(LINE), lw * 0.8))


def head_features(c, st, lw, ex):
    draw_eye(c, st, lw, 1, ex)
    draw_eye(c, st, lw, -1, ex)
    draw_nose(c, st, lw)
    draw_mouth(c, st, lw, ex)


def hair_render(c, locks, base, shade, light, line, lw, crown_clip_y=-100.0,
                highlight_y=-108, extra=None):
    """Fill locks as one mass, add cel shade + highlight band, then line art."""
    mass = union(*locks)
    c.drawPath(mass, fill(rgb(base)))
    with Saved(c):
        c.clipPath(mass, doAntiAlias=True)
        b = mass.getBounds()
        c.drawRect(b, fill(0, shader=linear((0, highlight_y + 30), (0, b.bottom()),
                   [rgb(shade, 0.0), rgb(shade, 0.85)], [0, 1])))
        # zig-zag "angel ring" highlight
        pts = []
        xs = [b.left() + (b.width()) * i / 14 for i in range(15)]
        for i, x in enumerate(xs):
            pts.append((x, highlight_y - 6 + (5 if i % 2 else -3)))
        for i, x in enumerate(reversed(xs)):
            pts.append((x, highlight_y + 12 + (14 if i % 2 else 0)))
        c.drawPath(poly_path(pts), fill(rgb(light), 0.85))
        if extra:
            extra(c)
    with Saved(c):
        c.clipRect(skia.Rect.MakeLTRB(-1000, crown_clip_y, 1000, 2000))
        for lk in locks[1:]:
            c.drawPath(lk, stroke(rgb(line), lw * 0.6))
    c.drawPath(mass, stroke(rgb(line), lw))
    return mass


# ======================================================================
#  MIO
# ======================================================================
MIO_STYLE = Style(skin="#fde4d6", skin_shade="#f1b9a8", iris_dark="#8a4a12",
                  iris_light="#ffc25a", hair_line="#141a33")
MIO_HAIR = ("#2d3a6b", "#1b2246", "#6a82c8")


def mio_back_hair(c, lw, ex):
    base, shade, light = MIO_HAIR
    sw = ex.sway * 10
    back = smooth_path([(-100, -130), (0, -160), (100, -130), (124, -30), (126, 60), (112 + sw, 126),
                        (60, 132), (0, 122), (-60, 132), (-112 + sw, 126), (-126, 60), (-124, -30)])
    # side ponytail (Mio's left = screen right)
    sway = ex.sway * 18 + math.sin(ex.t * 2.1) * 5
    tail1 = lock((84, -128), (128, -66), (232 + sway, 80 + sway * 0.4), bend=34, belly=0.6)
    tail2 = lock((92, -110), (128, -56), (196 + sway * 0.8, 126), bend=22, belly=0.55)
    tail3 = lock((96, -112), (130, -76), (258 + sway * 1.2, 28), bend=30, belly=0.55)
    for p in (back, tail3, tail1, tail2):
        c.drawPath(p, fill(rgb(shade)))
    with Saved(c):
        c.clipPath(union(tail1, tail2, tail3), doAntiAlias=True)
        c.drawPath(lock((96, -118), (124, -74), (214 + sway, 52), bend=28, belly=0.5), fill(rgb(base), 0.9))
        c.drawPath(lock((104, -108), (120, -84), (226 + sway, 40), bend=28, belly=0.3), fill(rgb(light), 0.35))
    for p in (back, tail3, tail1, tail2):
        c.drawPath(p, stroke(rgb(MIO_STYLE.hair_line), lw * 0.8))


def mio_front_hair(c, lw, ex):
    base, shade, light = MIO_HAIR
    sw = ex.sway * 6
    crown = smooth_path([(-112, -30), (-108, -100), (-72, -150), (0, -168), (72, -150), (108, -100),
                         (112, -30), (60, -70), (0, -82), (-60, -70)])
    locks = [
        crown,
        lock((-112, -80), (-50, -116), (-90 + sw, 4), bend=-8),
        lock((-84, -112), (-20, -132), (-56 + sw, 22), bend=-4),
        lock((-48, -128), (14, -134), (-20 + sw, 8), bend=3),
        lock((-14, -134), (48, -126), (14 + sw, 24), bend=4),
        lock((20, -130), (84, -108), (50 + sw, 6), bend=7),
        lock((54, -116), (112, -80), (84 + sw, 14), bend=10),
        lock((-30, -132), (-2, -134), (-34 + sw, 30), bend=-2, belly=0.1),
        lock((30, -130), (60, -122), (34 + sw, 34), bend=2, belly=0.1),
        # side locks framing the face
        lock((-120, -70), (-84, -84), (-100 + sw, 120), bend=-8, belly=0.45),
        lock((84, -84), (120, -70), (102 + sw, 120), bend=8, belly=0.45),
        lock((-124, -36), (-98, -50), (-118 + sw, 88), bend=-6, belly=0.4),
        lock((98, -50), (124, -36), (120 + sw, 88), bend=6, belly=0.4),
    ]
    hair_render(c, locks, base, shade, light, MIO_STYLE.hair_line, lw)
    # ahoge (antenna strand)
    a = ex.sway * 10 + math.sin(ex.t * 3.0) * 4
    p = skia.Path()
    p.moveTo(-4, -164)
    p.cubicTo(-10, -200, 26 + a, -214, 30 + a, -190)
    p.cubicTo(18 + a, -204, 4, -196, 6, -164)
    p.close()
    c.drawPath(p, fill(rgb(base)))
    c.drawPath(p, stroke(rgb(MIO_STYLE.hair_line), lw * 0.8))
    # star hair clip
    c.drawPath(star_path(104, -96, 20, 9, 5, rot=0.2), fill(rgb("#ffd34d")))
    c.drawPath(star_path(104, -96, 20, 9, 5, rot=0.2), stroke(rgb("#9a6a10"), lw * 0.7))
    c.drawCircle(99, -101, 3.5, fill(rgb("#fff6cc")))


def mio_body(c, lw, ex):
    coat, coat_shade, coat_dark = "#f6c445", "#dc9d2c", "#a8711c"
    body = smooth_path([(-30, 150), (-92, 170), (-156, 188), (-188, 222), (-200, 300), (-204, 560),
                        (204, 560), (200, 300), (188, 222), (156, 188), (92, 170), (30, 150)])
    c.drawPath(body, fill(rgb(coat)))
    with Saved(c):
        c.clipPath(body, doAntiAlias=True)
        c.drawRect(skia.Rect.MakeLTRB(-210, 140, 210, 600), fill(0, shader=linear(
            (-200, 0), (200, 0), [rgb(coat_shade), rgb(coat_shade, 0), rgb(coat_shade, 0), rgb(coat_shade, 0.8)],
            [0, 0.3, 0.7, 1])))
        c.drawPath(smooth_path([(-90, 150), (0, 240), (90, 150)]), fill(rgb(coat_shade), 0.7))
    # shirt V and ribbon
    v = poly_path([(-30, 152), (0, 238), (30, 152)])
    c.drawPath(v, fill(rgb("#f7f3ea")))
    c.drawPath(v, stroke(rgb(LINE), lw * 0.7))
    for s in (-1, 1):
        bow = smooth_path([(0, 196), (s * 22, 184), (s * 26, 204), (s * 6, 206)])
        c.drawPath(bow, fill(rgb("#d9384f")))
        c.drawPath(bow, stroke(rgb(LINE), lw * 0.6))
    c.drawCircle(0, 200, 6, fill(rgb("#b02a3f")))
    # collar flaps
    for s in (-1, 1):
        flap = poly_path([(s * 30, 150), (s * 82, 176), (s * 50, 262), (s * 6, 214)])
        c.drawPath(flap, fill(rgb("#f9d265")))
        c.drawPath(flap, stroke(rgb(coat_dark), lw * 0.8))
    c.drawLine(0, 238, 0, 560, stroke(rgb(coat_dark), lw * 0.8))
    for s in (-1, 1):
        c.drawLine(s * 158, 250, s * 166, 560, stroke(rgb(coat_dark), lw * 0.8))
    for yy in (300, 380, 460):
        c.drawRoundRect(skia.Rect.MakeXYWH(-16, yy - 5, 32, 10), 5, 5, fill(rgb("#7a4a1c")))
    c.drawPath(body, stroke(rgb(LINE), lw))


def draw_mio(c, x, y, scale, ex: Expr, body=True, lw_px=4.2):
    lw = lw_px / scale
    with Saved(c):
        c.translate(x, y)
        c.scale(scale, scale)
        mio_back_hair(c, lw, ex)
        if body:
            mio_body(c, lw, ex)
        draw_neck(c, MIO_STYLE, lw)
        draw_ears(c, MIO_STYLE, lw)
        draw_face_base(c, MIO_STYLE, lw, ex)
        head_features(c, MIO_STYLE, lw, ex)
        draw_face_outline(c, MIO_STYLE, lw)
        mio_front_hair(c, lw, ex)
        draw_brows(c, MIO_STYLE, lw, ex)


# ======================================================================
#  LUMI
# ======================================================================
LUMI_STYLE = Style(skin="#fff1ec", skin_shade="#efc8c6", iris_dark="#b07a10",
                   iris_light="#ffe27a", hair_line="#6b6fa8", star_pupil=True,
                   eye_scale=1.04, lash_col="#3a2f55", brow_col="#8f93c8")
LUMI_HAIR = ("#eef1ff", "#aeb3e6", "#ffffff")


def _float(ex, k, amp=1.0):
    return math.sin(ex.t * 1.3 + k * 1.7) * 8 * amp


def lumi_back_hair(c, lw, ex):
    base, shade, light = LUMI_HAIR
    g = ex.glow
    if g > 0:
        glow(c, 0, 40, 420, "#cfd8ff", 0.35 * g)
    pts = [(-100, -130), (0, -162), (100, -130), (130, -30), (150 + _float(ex, 1), 120),
           (172 + _float(ex, 2), 260), (196 + _float(ex, 3), 420), (160 + _float(ex, 4), 520),
           (110 + _float(ex, 5), 470), (60, 540), (0, 520), (-60, 540), (-110 + _float(ex, 6), 470),
           (-160 + _float(ex, 7), 520), (-196 + _float(ex, 8), 420), (-172 + _float(ex, 9), 260),
           (-150 + _float(ex, 10), 120), (-130, -30)]
    back = smooth_path(pts)
    c.drawPath(back, fill(rgb(shade)))
    with Saved(c):
        c.clipPath(back, doAntiAlias=True)
        c.drawPath(back, fill(0, shader=linear((0, -100), (0, 520),
                   [rgb("#d8dcff"), rgb("#b4b8ec"), rgb("#9fa6e8")], [0, 0.5, 1])))
        for i in range(9):
            xx = -160 + i * 40 + _float(ex, i, 0.6)
            c.drawLine(xx, 60, xx * 1.15, 500, stroke(rgb("#ffffff"), lw * 0.6, alpha=0.35))
    c.drawPath(back, stroke(rgb(LUMI_STYLE.hair_line), lw * 0.8))


def lumi_body(c, lw, ex):
    dress, shade = "#f6f4ff", "#c9c6ee"
    body = smooth_path([(-28, 150), (-86, 170), (-146, 188), (-176, 222), (-188, 300), (-192, 560),
                        (192, 560), (188, 300), (176, 222), (146, 188), (86, 170), (28, 150)])
    c.drawPath(body, fill(rgb(dress)))
    with Saved(c):
        c.clipPath(body, doAntiAlias=True)
        c.drawRect(skia.Rect.MakeLTRB(-200, 140, 200, 600), fill(0, shader=linear(
            (-190, 0), (190, 0), [rgb(shade), rgb(shade, 0), rgb(shade, 0), rgb(shade, 0.9)], [0, 0.3, 0.7, 1])))
        c.drawPath(smooth_path([(-80, 150), (0, 220), (80, 150)]), fill(rgb(shade), 0.6))
        # gold trim lines
        c.drawPath(smooth_path([(-140, 240), (0, 300), (140, 240)], closed=False),
                   stroke(rgb("#e6b84a"), lw * 1.4))
    # high collar
    col = smooth_path([(-34, 140), (-40, 176), (0, 190), (40, 176), (34, 140), (0, 150)])
    c.drawPath(col, fill(rgb("#ffffff")))
    c.drawPath(col, stroke(rgb("#e6b84a"), lw * 1.1))
    # star brooch
    c.drawPath(star_path(0, 232, 22, 8, 4, rot=ex.t * 0.3), fill(rgb("#ffe58a")))
    glow(c, 0, 232, 40, "#fff3b0", 0.6 + 0.3 * math.sin(ex.t * 3))
    c.drawPath(body, stroke(rgb(LUMI_STYLE.hair_line), lw))
    # translucent shawl
    shawl = smooth_path([(-150, 210), (-60, 190), (0, 260), (60, 190), (150, 210), (176, 330),
                         (0, 360), (-176, 330)])
    c.drawPath(shawl, fill(rgb("#bfe3ff"), 0.28))
    c.drawPath(shawl, stroke(rgb("#9cc9ff"), lw * 0.6, alpha=0.5))


def lumi_front_hair(c, lw, ex):
    base, shade, light = LUMI_HAIR
    f = lambda k: _float(ex, k, 0.4)  # noqa: E731
    crown = smooth_path([(-114, -30), (-110, -100), (-72, -152), (0, -170), (72, -152), (110, -100),
                         (114, -30), (60, -72), (0, -60), (-60, -72)])
    locks = [
        crown,
        # center parted bangs
        lock((-114, -84), (-56, -120), (-92 + f(1), 14), bend=-8),
        lock((-84, -118), (-22, -136), (-54 + f(2), 24), bend=-5),
        lock((-46, -134), (2, -138), (-16 + f(3), 0), bend=-3),
        lock((-2, -138), (46, -134), (16 + f(4), 2), bend=3),
        lock((22, -136), (84, -118), (54 + f(5), 26), bend=5),
        lock((56, -120), (114, -84), (92 + f(6), 16), bend=8),
        # very long side locks down to the chest
        lock((-126, -74), (-84, -88), (-110 + _float(ex, 11), 310), bend=-12, belly=0.5),
        lock((84, -88), (126, -74), (110 + _float(ex, 12), 310), bend=12, belly=0.5),
    ]

    def extra(cc):
        cc.drawRect(skia.Rect.MakeLTRB(-200, -200, 200, 400), fill(0, shader=linear(
            (0, -60), (0, 300), [rgb("#ffffff", 0), rgb("#c3c8ff", 0.6)])))

    hair_render(c, locks, base, shade, light, LUMI_STYLE.hair_line, lw, extra=extra)
    # little star ornaments
    for (sx, sy, r) in ((-96, -104, 14), (-76, -128, 9)):
        c.drawPath(star_path(sx, sy, r, r * 0.4, 4, rot=ex.t * 0.5), fill(rgb("#ffe58a")))
        glow(c, sx, sy, r * 3, "#fff3b0", 0.55)


def draw_lumi(c, x, y, scale, ex: Expr, body=True, lw_px=4.0):
    lw = lw_px / scale
    with Saved(c):
        c.translate(x, y)
        c.scale(scale, scale)
        lumi_back_hair(c, lw, ex)
        if body:
            lumi_body(c, lw, ex)
        draw_neck(c, LUMI_STYLE, lw)
        draw_face_base(c, LUMI_STYLE, lw, ex)
        head_features(c, LUMI_STYLE, lw, ex)
        draw_face_outline(c, LUMI_STYLE, lw)
        lumi_front_hair(c, lw, ex)
        draw_brows(c, LUMI_STYLE, lw, ex, alpha=0.8)
        if ex.glow > 0:
            for i in range(10):
                a = ex.t * (0.4 + 0.1 * i) + i * 0.63
                r = 230 + 40 * math.sin(ex.t + i)
                sparkle(c, math.cos(a) * r, -20 + math.sin(a) * r * 0.9,
                        6 + 5 * hash01(i, 5), "#fff7d6",
                        alpha=ex.glow * (0.5 + 0.5 * math.sin(ex.t * 3 + i)))


# ======================================================================
#  GRANDPA GENZO
# ======================================================================
GENZO_STYLE = Style(skin="#eec3a0", skin_shade="#cf9673", iris_dark="#3a2a20",
                    iris_light="#7a5a40", hair_line="#5c5c66", brow_col="#f2f2f2")


def genzo_body(c, lw, ex):
    knit, shade = "#e2d3b2", "#b9a682"
    body = smooth_path([(-36, 150), (-100, 176), (-164, 206), (-200, 260), (-214, 360), (-220, 560),
                        (220, 560), (214, 360), (200, 260), (164, 206), (100, 176), (36, 150)])
    c.drawPath(body, fill(rgb(knit)))
    with Saved(c):
        c.clipPath(body, doAntiAlias=True)
        c.drawRect(skia.Rect.MakeLTRB(-230, 140, 230, 600), fill(0, shader=linear(
            (-220, 0), (220, 0), [rgb(shade), rgb(shade, 0), rgb(shade, 0), rgb(shade, 0.9)], [0, 0.3, 0.7, 1])))
        for xx in range(-180, 200, 46):  # cable knit
            for yy in range(220, 560, 36):
                c.drawArc(skia.Rect.MakeXYWH(xx - 10, yy, 20, 30), 200, 140, False,
                          stroke(rgb(shade), lw * 0.7))
                c.drawArc(skia.Rect.MakeXYWH(xx - 10, yy, 20, 30), 20, 140, False,
                          stroke(rgb(shade), lw * 0.7))
    c.drawPath(body, stroke(rgb(LINE), lw))
    # rolled turtleneck
    tn = smooth_path([(-52, 128), (-58, 176), (0, 196), (58, 176), (52, 128), (0, 140)])
    c.drawPath(tn, fill(rgb("#d6c49e")))
    for k in range(-40, 50, 14):
        c.drawLine(k, 146, k * 1.1, 186, stroke(rgb(shade), lw * 0.6))
    c.drawPath(tn, stroke(rgb(LINE), lw * 0.9))


def genzo_head_extras(c, lw, ex):
    # white side hair
    for s in (-1, 1):
        tuft = smooth_path([(s * 84, -60), (s * 108, -40), (s * 110, 10), (s * 96, 36), (s * 88, -10)])
        c.drawPath(tuft, fill(rgb("#f0f0f2")))
        c.drawPath(tuft, stroke(rgb("#8a8a96"), lw * 0.8))
    # wrinkles
    for s in (-1, 1):
        c.drawLine(s * 66, 34, s * 80, 30, stroke(rgb(GENZO_STYLE.skin_shade), lw * 0.7))
        c.drawLine(s * 70, 42, s * 82, 40, stroke(rgb(GENZO_STYLE.skin_shade), lw * 0.7))
    for k in range(3):
        c.drawLine(-30, -48 - k * 8, 30, -48 - k * 8, stroke(rgb(GENZO_STYLE.skin_shade), lw * 0.6))
    # beard (chin)
    beard = smooth_path([(-60, 80), (-40, 118), (0, 140), (40, 118), (60, 80), (0, 100)])
    c.drawPath(beard, fill(rgb("#f4f4f6")))
    c.drawPath(beard, stroke(rgb("#9a9aa6"), lw * 0.7))
    # mouth under moustache
    m = clamp(ex.mouth)
    if m > 0.08:
        c.drawOval(skia.Rect.MakeXYWH(-14, 80, 28, 6 + 16 * m), fill(rgb("#5a2230")))
    # moustache - bobs with speech
    bob = -m * 4
    for s in (-1, 1):
        mu = smooth_path([(0, 64 + bob), (s * 30, 60 + bob), (s * 62, 78 + bob), (s * 52, 92 + bob),
                          (s * 24, 84 + bob), (0, 80 + bob)])
        c.drawPath(mu, fill(rgb("#fafafa")))
        c.drawPath(mu, stroke(rgb("#9a9aa6"), lw * 0.8))
    # cap
    cap = smooth_path([(-112, -40), (-104, -112), (-60, -150), (0, -158), (60, -150), (104, -112),
                       (112, -40), (0, -56)])
    c.drawPath(cap, fill(rgb("#24305a")))
    with Saved(c):
        c.clipPath(cap, doAntiAlias=True)
        c.drawRect(skia.Rect.MakeLTRB(-120, -170, 120, -100), fill(rgb("#33437a")))
    c.drawPath(cap, stroke(rgb(LINE), lw))
    brim = smooth_path([(-118, -44), (0, -64), (118, -44), (100, -22), (0, -36), (-100, -22)])
    c.drawPath(brim, fill(rgb("#121626")))
    c.drawPath(brim, stroke(rgb(LINE), lw))
    # anchor badge
    c.drawCircle(0, -100, 16, fill(rgb("#e8c35a")))
    c.drawLine(0, -110, 0, -90, stroke(rgb("#7a5a14"), lw))
    c.drawArc(skia.Rect.MakeXYWH(-9, -102, 18, 14), 0, 180, False, stroke(rgb("#7a5a14"), lw))


def genzo_eyes(c, lw, ex):
    # kind squinting eyes; open a little with surprise
    for s in (-1, 1):
        if ex.surprise > 0.3 and ex.blink < 0.5:
            c.drawOval(skia.Rect.MakeXYWH(s * 45 - 8, 10, 16, 20), fill(rgb("#2a1a14")))
            c.drawCircle(s * 45 - 3, 15, 3, fill(rgb("#ffffff")))
        else:
            p = skia.Path()
            p.moveTo(s * 26, 22)
            p.quadTo(s * 45, 8 + ex.blink * 10, s * 66, 22)
            c.drawPath(p, stroke(rgb(LINE), lw * 1.5))
    # bushy brows
    for s in (-1, 1):
        by = -16 - ex.brow * 6 - ex.surprise * 10
        br = smooth_path([(s * 16, by), (s * 40, by - 14), (s * 78, by - 4), (s * 84, by + 8),
                          (s * 50, by + 4), (s * 20, by + 8)])
        c.drawPath(br, fill(rgb("#f4f4f6")))
        c.drawPath(br, stroke(rgb("#9a9aa6"), lw * 0.7))


def draw_genzo(c, x, y, scale, ex: Expr, body=True, lw_px=4.2):
    lw = lw_px / scale
    st = GENZO_STYLE
    with Saved(c):
        c.translate(x, y)
        c.scale(scale, scale)
        if body:
            genzo_body(c, lw, ex)
        draw_neck(c, st, lw)
        draw_ears(c, st, lw)
        fp = face_path()
        c.drawPath(fp, fill(rgb(st.skin)))
        with Saved(c):
            c.clipPath(fp, doAntiAlias=True)
            c.drawPath(fp, fill(0, shader=linear((-95, 0), (95, 0), [rgb(st.skin_shade, 0.6),
                       rgb(st.skin_shade, 0), rgb(st.skin_shade, 0), rgb(st.skin_shade, 0.4)], [0, .22, .75, 1])))
            if ex.blush > 0:
                for s in (-1, 1):
                    c.drawOval(skia.Rect.MakeXYWH(s * 55 - 22, 40, 44, 16),
                               fill(rgb("#ff8a8a"), 0.45 * ex.blush, blur=7))
        genzo_eyes(c, lw, ex)
        c.drawPath(smooth_path([(-4, 30), (10, 56), (0, 62), (-10, 58)], closed=False),
                   stroke(rgb(st.skin_shade), lw * 0.9))
        draw_face_outline(c, st, lw)
        genzo_head_extras(c, lw, ex)


# ======================================================================
#  THE COLLECTOR (silhouette)
# ======================================================================
def draw_collector(c, x, y, scale, ex: Expr, lantern=True):
    with Saved(c):
        c.translate(x, y)
        c.scale(scale, scale)
        cloak = smooth_path([(0, -190), (90, -150), (120, -40), (130, 120), (220, 560), (-220, 560),
                             (-130, 120), (-120, -40), (-90, -150)])
        c.drawPath(cloak, fill(rgb("#140f22")))
        with Saved(c):
            c.clipPath(cloak, doAntiAlias=True)
            c.drawPath(cloak, fill(0, shader=linear((-200, 0), (200, 0),
                       [rgb("#5a1f3a", 0.7), rgb("#140f22", 0), rgb("#140f22", 0), rgb("#3a1f5a", 0.6)],
                       [0, .25, .75, 1])))
        hood = smooth_path([(0, -150), (70, -110), (84, -10), (50, 70), (0, 90), (-50, 70), (-84, -10), (-70, -110)])
        c.drawPath(hood, fill(rgb("#05030a")))
        c.drawPath(cloak, stroke(rgb("#7a3a6a"), 2.2 / scale, alpha=0.7))
        eye_a = 0.75 + 0.25 * math.sin(ex.t * 5)
        for s in (-1, 1):
            glow(c, s * 26, -4, 34, "#ff3050", 0.8 * eye_a)
            c.drawPath(smooth_path([(s * 12, -2), (s * 26, -10), (s * 40, -4), (s * 26, 2)]),
                       fill(rgb("#ffd0d6"), eye_a))
        if lantern:
            lx, ly = 170, 260
            c.drawLine(120, 200, lx, ly - 60, stroke(rgb("#3a3046"), 6))
            cage = skia.Rect.MakeXYWH(lx - 50, ly - 60, 100, 130)
            glow(c, lx, ly, 200, "#b07bff", 0.55)
            c.drawRoundRect(cage, 20, 20, fill(rgb("#2a1f3e"), 0.6))
            for i in range(6):
                a = ex.t * 1.2 + i
                sparkle(c, lx + math.cos(a) * 26, ly + math.sin(a * 1.3) * 34, 9, "#e7d6ff",
                        alpha=0.6 + 0.4 * math.sin(ex.t * 4 + i))
            for k in range(5):
                xx = lx - 40 + k * 20
                c.drawLine(xx, ly - 60, xx, ly + 70, stroke(rgb("#6a5a7a"), 4))
            c.drawRoundRect(cage, 20, 20, stroke(rgb("#8a7a9a"), 5))


# ======================================================================
#  Small full-body figures for wide shots
# ======================================================================
def draw_figure(c, who, x, y, height, ex: Expr, walk=0.0, arm_up=0.0, holding_lantern=False,
                facing=1, lantern_glow=1.0):
    """Feet at (x, y). height = total height in px. ~1:6 anime proportions."""
    s = height / 1000.0
    lw = 2.6 / s
    ph = math.sin(walk * math.tau)
    bob = abs(math.sin(walk * math.tau)) * 14 if walk else 0.0
    with Saved(c):
        c.translate(x, y)
        c.scale(s * facing, s)
        c.translate(0, -bob)
        if who == "mio":
            coat, coat_d, line, leg, shoe = "#f6c445", "#d89b2a", LINE, "#2b2a40", "#6a3a22"
        elif who == "lumi":
            coat, coat_d, line, leg, shoe = "#f6f4ff", "#c9c6ee", "#6b6fa8", "#fff1ec", "#e8e2ff"
        else:
            coat, coat_d, line, leg, shoe = "#e2d3b2", "#b9a682", LINE, "#2a3152", "#3a2a1a"
        hs = 0.65
        head_y = -1000 + 166 * hs
        if who == "lumi":
            lumi_back_hair_small = True
            with Saved(c):
                c.translate(0, head_y)
                c.scale(hs, hs)
                lumi_back_hair(c, lw / hs, ex)
        # legs
        for sgn in (-1, 1):
            off = ph * 70 * sgn
            p = poly_path([(sgn * 34 - 20, -500), (sgn * 34 + 20, -500), (sgn * 30 + off + 15, -40),
                           (sgn * 30 + off - 15, -40)])
            c.drawPath(p, fill(rgb(leg)))
            c.drawPath(p, stroke(rgb(line), lw * 0.7))
            sh = skia.Rect.MakeXYWH(sgn * 30 + off - 24, -52, 58, 52)
            c.drawRoundRect(sh, 18, 18, fill(rgb(shoe)))
            c.drawRoundRect(sh, 18, 18, stroke(rgb(line), lw * 0.7))
        # torso / coat
        if who == "lumi":
            bodyp = smooth_path([(-60, -800), (-86, -770), (-96, -640), (-120, -380), (-170, -60),
                                 (170, -60), (120, -380), (96, -640), (86, -770), (60, -800)])
        elif who == "mio":
            bodyp = smooth_path([(-56, -800), (-88, -770), (-84, -620), (-100, -480), (-124, -300),
                                 (124, -300), (100, -480), (84, -620), (88, -770), (56, -800)])
        else:
            bodyp = smooth_path([(-60, -800), (-100, -770), (-100, -620), (-96, -460),
                                 (96, -460), (100, -620), (100, -770), (60, -800)])
        c.drawPath(bodyp, fill(rgb(coat)))
        with Saved(c):
            c.clipPath(bodyp, doAntiAlias=True)
            c.drawRect(skia.Rect.MakeLTRB(20, -820, 200, 0), fill(rgb(coat_d), 0.6))
        c.drawPath(bodyp, stroke(rgb(line), lw))
        if who == "mio":
            c.drawLine(0, -760, 0, -300, stroke(rgb("#a8711c"), lw * 0.7))
        # arms
        for sgn in (-1, 1):
            up = arm_up if sgn == 1 else 0.0
            ax, ay = sgn * 80, -770
            ang = math.radians(8 + 150 * up)
            swing = ph * 0.35 * -sgn
            hx = ax + sgn * math.sin(ang + swing * sgn) * 290
            hy = ay + math.cos(ang + swing * sgn) * 290
            c.drawLine(ax, ay, hx, hy, stroke(rgb(line), 58 + lw * 2))
            c.drawLine(ax, ay, hx, hy, stroke(rgb(coat), 58))
            c.drawCircle(hx, hy, 24, fill(rgb("#fde4d6")))
            c.drawCircle(hx, hy, 24, stroke(rgb(line), lw * 0.7))
            if holding_lantern and sgn == 1:
                glow(c, hx, hy + 80, 300, "#ffc85a", 0.75 * lantern_glow)
                c.drawLine(hx, hy, hx, hy + 36, stroke(rgb("#3a2a1a"), 6))
                lr = skia.Rect.MakeXYWH(hx - 28, hy + 36, 56, 76)
                c.drawRoundRect(lr, 12, 12, fill(rgb("#fff0b8")))
                c.drawRoundRect(lr, 12, 12, stroke(rgb("#3a2a1a"), 7))
        # head
        if who == "mio":
            draw_mio(c, 0, head_y, hs, ex, body=False, lw_px=2.2 / s)
        elif who == "lumi":
            with Saved(c):
                c.translate(0, head_y)
                c.scale(hs, hs)
                lw2 = 2.2 / s / hs
                draw_neck(c, LUMI_STYLE, lw2)
                draw_face_base(c, LUMI_STYLE, lw2, ex)
                head_features(c, LUMI_STYLE, lw2, ex)
                draw_face_outline(c, LUMI_STYLE, lw2)
                lumi_front_hair(c, lw2, ex)
        else:
            draw_genzo(c, 0, head_y, hs, ex, body=False, lw_px=2.2 / s)

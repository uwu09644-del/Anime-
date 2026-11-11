"""Low-level drawing helpers on top of skia-python.

Everything in the episode is drawn with these: smooth Catmull-Rom shapes,
gradients, glows, text, and small math helpers for animation curves.
"""
import math
import os

import numpy as np
import skia

W, H = 1920, 1080
FPS = 24

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")


# ---------------------------------------------------------------- colours
def rgb(hexstr, a=1.0):
    """'#rrggbb' -> skia ARGB int with alpha a (0..1)."""
    h = hexstr.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return skia.ColorSetARGB(int(max(0, min(1, a)) * 255), r, g, b)


def mix(c1, c2, t):
    """Blend two '#rrggbb' strings -> '#rrggbb'."""
    a = [int(c1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    c = [int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3)]
    return "#%02x%02x%02x" % tuple(c)


# ---------------------------------------------------------------- easing
def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def ease_in_out(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t ** 3


def ramp(t, t0, t1):
    """0 before t0, 1 after t1, smooth between."""
    if t1 <= t0:
        return 1.0 if t >= t1 else 0.0
    return ease_in_out((t - t0) / (t1 - t0))


def pulse(t, t0, t1, fade=0.3):
    """1 inside [t0,t1] with soft edges."""
    return ramp(t, t0 - fade, t0) * (1 - ramp(t, t1, t1 + fade))


def hash01(*args):
    """Deterministic pseudo-random 0..1 from ints/floats."""
    x = 0
    for a in args:
        x = (x * 1103515245 + int(a * 1000) + 12345) & 0x7FFFFFFF
    x ^= x >> 13
    x = (x * 1274126177) & 0x7FFFFFFF
    return (x % 100000) / 100000.0


# ---------------------------------------------------------------- paints
def fill(color, alpha=None, blur=0.0, blend=None, shader=None):
    p = skia.Paint(AntiAlias=True)
    p.setStyle(skia.Paint.kFill_Style)
    if shader is not None:
        p.setShader(shader)
    else:
        p.setColor(color)
    if alpha is not None:
        p.setAlphaf(alpha)
    if blur > 0:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if blend is not None:
        p.setBlendMode(blend)
    return p


def stroke(color, width, alpha=None, cap=skia.Paint.kRound_Cap, blur=0.0, blend=None):
    p = skia.Paint(AntiAlias=True)
    p.setStyle(skia.Paint.kStroke_Style)
    p.setColor(color)
    p.setStrokeWidth(width)
    p.setStrokeCap(cap)
    p.setStrokeJoin(skia.Paint.kRound_Join)
    if alpha is not None:
        p.setAlphaf(alpha)
    if blur > 0:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if blend is not None:
        p.setBlendMode(blend)
    return p


ADD = skia.BlendMode.kPlus
SCREEN = skia.BlendMode.kScreen
MULT = skia.BlendMode.kMultiply


def linear(p0, p1, colors, pos=None):
    return skia.GradientShader.MakeLinear(
        [skia.Point(*p0), skia.Point(*p1)], colors, pos)


def radial(c, r, colors, pos=None):
    return skia.GradientShader.MakeRadial(skia.Point(*c), max(r, 0.01), colors, pos)


# ---------------------------------------------------------------- paths
def smooth_path(pts, closed=True, tension=1.0):
    """Catmull-Rom spline through points -> skia.Path (cubic beziers)."""
    path = skia.Path()
    n = len(pts)
    if n < 2:
        return path
    path.moveTo(*pts[0])
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if closed or i > 0 else pts[0]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if closed or i + 2 < n else pts[-1]
        k = tension / 6.0
        c1 = (p1[0] + (p2[0] - p0[0]) * k, p1[1] + (p2[1] - p0[1]) * k)
        c2 = (p2[0] - (p3[0] - p1[0]) * k, p2[1] - (p3[1] - p1[1]) * k)
        path.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    if closed:
        path.close()
    return path


def poly_path(pts, closed=True):
    path = skia.Path()
    path.moveTo(*pts[0])
    for p in pts[1:]:
        path.lineTo(*p)
    if closed:
        path.close()
    return path


def oval(cx, cy, rx, ry):
    path = skia.Path()
    path.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    return path


def mirror_pts(pts):
    return [(-x, y) for (x, y) in pts]


def lock(root_l, root_r, tip, bend=0.0, belly=0.35):
    """A single pointed hair lock from two root points to a tip.

    bend shifts the lock's midline sideways in x (curl); belly controls fullness.
    """
    full = 0.55 + belly
    (x0, y0), (x1, y1), (tx, ty) = root_l, root_r, tip
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = tx - mx, ty - my
    L = math.hypot(dx, dy) or 1.0
    px, py = -dy / L, dx / L
    hw = math.hypot(x1 - x0, y1 - y0) / 2
    sl = 1.0 if (x0 - mx) * px + (y0 - my) * py > 0 else -1.0

    def mid(f, b):
        return mx + dx * f + b, my + dy * f

    a = mid(0.42, bend * 0.6)
    b = mid(0.8, bend)
    k1, k2 = hw * full, hw * full * 0.42
    p = skia.Path()
    p.moveTo(x0, y0)
    p.cubicTo(a[0] + px * sl * k1, a[1] + py * sl * k1, b[0] + px * sl * k2, b[1] + py * sl * k2, tx, ty)
    p.cubicTo(b[0] - px * sl * k2, b[1] - py * sl * k2, a[0] - px * sl * k1, a[1] - py * sl * k1, x1, y1)
    p.close()
    return p


def union(*paths):
    out = skia.Path(paths[0])
    for p in paths[1:]:
        r = skia.Op(out, p, skia.PathOp.kUnion_PathOp)
        if r is not None:
            out = r
    return out


def intersect(a, b):
    r = skia.Op(a, b, skia.PathOp.kIntersect_PathOp)
    return r if r is not None else skia.Path()


def difference(a, b):
    r = skia.Op(a, b, skia.PathOp.kDifference_PathOp)
    return r if r is not None else skia.Path(a)


def star_path(cx, cy, r_out, r_in, points=4, rot=0.0):
    pts = []
    for i in range(points * 2):
        a = rot + math.pi * i / points - math.pi / 2
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return poly_path(pts)


def sparkle(canvas, x, y, size, color="#ffffff", alpha=1.0, rot=0.0):
    """Four-point anime sparkle with soft glow."""
    if alpha <= 0.01 or size <= 0.2:
        return
    canvas.drawCircle(x, y, size * 1.4, fill(rgb(color), alpha * 0.35, blur=size * 0.9, blend=ADD))
    p = skia.Path()
    s, t = size, size * 0.16
    p.moveTo(x, y - s)
    p.quadTo(x + t, y - t, x + s, y)
    p.quadTo(x + t, y + t, x, y + s)
    p.quadTo(x - t, y + t, x - s, y)
    p.quadTo(x - t, y - t, x, y - s)
    p.close()
    if rot:
        m = skia.Matrix()
        m.setRotate(math.degrees(rot), x, y)
        p.transform(m)
    canvas.drawPath(p, fill(rgb(color), alpha))


def glow(canvas, x, y, r, color, alpha=1.0, blend=ADD):
    canvas.drawCircle(x, y, r, fill(0, shader=radial(
        (x, y), r, [rgb(color, alpha), rgb(color, alpha * 0.35), rgb(color, 0)],
        [0.0, 0.35, 1.0]), blend=blend))


# ---------------------------------------------------------------- text
_TF = {}


def typeface(name):
    if name not in _TF:
        path = os.path.join(FONT_DIR, name)
        if os.path.exists(path):
            _TF[name] = skia.Typeface.MakeFromFile(path)
        else:
            _TF[name] = skia.Typeface(name)
    return _TF[name]


def font(name, size):
    f = skia.Font(typeface(name), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


def text_width(txt, fnt):
    return fnt.measureText(txt)


def draw_text(canvas, txt, x, y, fnt, color="#ffffff", alpha=1.0, align="center",
              outline=None, outline_w=0, shadow=None):
    w = fnt.measureText(txt)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    blob = skia.TextBlob(txt, fnt)
    if shadow:
        canvas.drawTextBlob(blob, x + 3, y + 4, fill(rgb(shadow), alpha * 0.6, blur=4))
    if outline:
        p = stroke(rgb(outline), outline_w, alpha)
        canvas.drawTextBlob(blob, x, y, p)
    canvas.drawTextBlob(blob, x, y, fill(rgb(color), alpha))
    return w


def wrap_text(txt, fnt, max_w):
    words = txt.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if fnt.measureText(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- canvas helpers
class Saved:
    """with Saved(canvas): ... -> save/restore."""

    def __init__(self, canvas, layer_paint=None, bounds=None):
        self.c, self.p, self.b = canvas, layer_paint, bounds

    def __enter__(self):
        if self.p is not None:
            self.c.saveLayer(self.b, self.p)
        else:
            self.c.save()
        return self.c

    def __exit__(self, *a):
        self.c.restore()


def tint_paint(r=1.0, g=1.0, b=1.0, add=(0, 0, 0), alpha=1.0, sat=1.0):
    """Layer paint applying a colour matrix (night grading etc.)."""
    # saturation matrix
    lr, lg, lb = 0.2126, 0.7152, 0.0722
    s = sat
    m = [
        (lr * (1 - s) + s) * r, lg * (1 - s) * r, lb * (1 - s) * r, 0, add[0] / 255.0,
        lr * (1 - s) * g, (lg * (1 - s) + s) * g, lb * (1 - s) * g, 0, add[1] / 255.0,
        lr * (1 - s) * b, lg * (1 - s) * b, (lb * (1 - s) + s) * b, 0, add[2] / 255.0,
        0, 0, 0, alpha, 0,
    ]
    p = skia.Paint()
    p.setColorFilter(skia.ColorFilters.Matrix(m))
    return p


def new_surface():
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    return skia.Surface.MakeRaster(info)


def snapshot_layer(draw_fn, w=W, h=H):
    """Render something once into an image (for cached backgrounds)."""
    info = skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    s = skia.Surface.MakeRaster(info)
    c = s.getCanvas()
    c.clear(skia.ColorTRANSPARENT)
    draw_fn(c)
    return s.makeImageSnapshot()


def vignette(canvas, strength=0.55, color="#000000"):
    sh = radial((W / 2, H / 2), W * 0.75,
                [rgb(color, 0), rgb(color, 0), rgb(color, strength)], [0.0, 0.55, 1.0])
    canvas.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=sh))


def letterbox(canvas, amount):
    """Cinematic bars, amount 0..1 -> up to 110px each."""
    if amount <= 0:
        return
    h = 110 * amount
    p = fill(rgb("#000000"))
    canvas.drawRect(skia.Rect.MakeLTRB(0, 0, W, h), p)
    canvas.drawRect(skia.Rect.MakeLTRB(0, H - h, W, H), p)


def screen_fade(canvas, amount, color="#000000"):
    if amount > 0.001:
        canvas.drawRect(skia.Rect.MakeWH(W, H), fill(rgb(color), amount))


def speed_lines(canvas, cx, cy, t, n=90, alpha=0.6, color="#ffffff", r0=380):
    """Radial anime focus lines."""
    for i in range(n):
        a = hash01(i, 7) * math.tau
        jitter = hash01(i, int(t * 12)) * 120
        rr = r0 + jitter
        w = 2 + hash01(i, 3) * 7
        x0, y0 = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        x1, y1 = cx + math.cos(a) * 1500, cy + math.sin(a) * 1500
        p = skia.Path()
        nx, ny = -math.sin(a) * w, math.cos(a) * w
        p.moveTo(x0, y0)
        p.lineTo(x1 + nx, y1 + ny)
        p.lineTo(x1 - nx, y1 - ny)
        p.close()
        canvas.drawPath(p, fill(rgb(color), alpha * (0.4 + 0.6 * hash01(i, 11))))


def film_grain(canvas, t, alpha=0.05):
    """Cheap animated grain: random tiny dots."""
    rng = np.random.default_rng(int(t * FPS) + 99)
    xs = rng.random(500) * W
    ys = rng.random(500) * H
    p = fill(rgb("#ffffff"), alpha)
    for x, y in zip(xs, ys):
        canvas.drawRect(skia.Rect.MakeXYWH(x, y, 2, 2), p)

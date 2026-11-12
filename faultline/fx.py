"""Studio-style effects for FAULTLINE.

Post-processing (bloom, grain, chromatic aberration, impact frames) and
in-scene effects (sparks, embers, dust, god rays, glowing cracks, shattering
shards, the gate portal, slash arcs, action backgrounds).
"""
import math

import numpy as np
import skia
from scipy.spatial import Delaunay

from gfx import (ADD, H, SCREEN, W, Saved, clamp, fill, glow, hash01, lerp, linear, poly_path, radial, rgb,
                 smooth_path, sparkle, stroke)

LIN = skia.SamplingOptions(skia.FilterMode.kLinear)


# ======================================================================
#  post-processing
# ======================================================================
def _threshold_paint(th, gain):
    k = gain
    m = [k, 0, 0, 0, -th * k,
         0, k, 0, 0, -th * k,
         0, 0, k, 0, -th * k,
         0, 0, 0, 1, 0]
    p = skia.Paint()
    p.setColorFilter(skia.ColorFilters.Matrix(m))
    return p


_SMALL = {}


def _small_surface(w, h):
    key = (w, h)
    if key not in _SMALL:
        info = skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
        _SMALL[key] = skia.Surface.MakeRaster(info)
    return _SMALL[key]


def bloom(c, surf, strength=0.6, threshold=0.6, wide=0.35):
    """Bright parts of the frame bleed light, like a studio compositing pass."""
    img = surf.makeImageSnapshot()
    for (w, h, sig, amt) in ((480, 270, 5, strength), (240, 135, 7, wide)):
        if amt <= 0:
            continue
        small = img.resize(w, h, LIN)
        s = _small_surface(w, h)
        sc = s.getCanvas()
        sc.clear(skia.ColorBLACK)
        p = _threshold_paint(threshold, 1.0 / max(1e-3, 1 - threshold))
        p.setImageFilter(skia.ImageFilters.Blur(sig, sig))
        sc.drawImage(small, 0, 0, LIN, p)
        b = s.makeImageSnapshot()
        bp = skia.Paint()
        bp.setBlendMode(ADD)
        bp.setAlphaf(clamp(amt) * 0.8)
        c.drawImageRect(b, skia.Rect.MakeWH(W, H), LIN, bp)


_GRAIN = []


def grain(c, t, alpha=0.06):
    """Film grain: premultiplied black/white speckle drawn with plain src-over (fast)."""
    if not _GRAIN:
        rng = np.random.default_rng(5)
        for _ in range(4):
            v = rng.random((540, 960))
            white = v > 0.5
            a = (np.abs(v - 0.5) * 2 * 255).astype(np.uint8)
            col = np.where(white, a, 0).astype(np.uint8)  # premultiplied
            rgba = np.dstack([col, col, col, a])
            _GRAIN.append(skia.Image.fromarray(rgba, colorType=skia.kRGBA_8888_ColorType,
                                               alphaType=skia.kPremul_AlphaType))
    img = _GRAIN[int(t * 24) % 4]
    p = skia.Paint()
    p.setAlphaf(alpha)
    c.drawImageRect(img, skia.Rect.MakeWH(W, H), skia.SamplingOptions(), p)


def chromatic(c, surf, amount=6.0):
    """Split RGB channels outward - used on impacts."""
    if amount < 0.5:
        return
    img = surf.makeImageSnapshot()
    c.clear(skia.ColorBLACK)
    for i, dx in enumerate((-amount, 0.0, amount)):
        m = [0.0] * 20
        m[i * 5 + i] = 1.0
        m[18] = 1.0
        p = skia.Paint()
        p.setColorFilter(skia.ColorFilters.Matrix(m))
        p.setBlendMode(ADD)
        sx = 1 + abs(dx) / W * 2
        c.save()
        c.translate(W / 2, H / 2)
        c.scale(sx if i != 1 else 1, sx if i != 1 else 1)
        c.translate(-W / 2, -H / 2)
        c.drawImage(img, 0, 0, LIN, p)
        c.restore()


def impact_frame(c, surf, mode="ink", tint="#ff2040"):
    """Classic anime impact frame: crushed high-contrast black/white (+tint)."""
    img = surf.makeImageSnapshot()
    lr, lg, lb = 0.299, 0.587, 0.114
    k = 4.0
    if mode == "invert":
        m = [-lr * k, -lg * k, -lb * k, 0, 0.5 * k,
             -lr * k, -lg * k, -lb * k, 0, 0.5 * k,
             -lr * k, -lg * k, -lb * k, 0, 0.5 * k,
             0, 0, 0, 1, 0]
    else:
        m = [lr * k, lg * k, lb * k, 0, -0.4 * k,
             lr * k, lg * k, lb * k, 0, -0.4 * k,
             lr * k, lg * k, lb * k, 0, -0.4 * k,
             0, 0, 0, 1, 0]
    p = skia.Paint()
    p.setColorFilter(skia.ColorFilters.Matrix(m))
    c.drawImage(img, 0, 0, LIN, p)
    if tint:
        c.drawRect(skia.Rect.MakeWH(W, H), fill(rgb(tint), 0.35, blend=skia.BlendMode.kMultiply))


_VIG = {}


def vignette(c, strength=0.6, color="#000000"):
    key = (round(strength, 2), color)
    if key not in _VIG:
        s = _small_surface(480, 270)
        sc = s.getCanvas()
        sc.clear(skia.ColorTRANSPARENT)
        sh = radial((240, 135), 480 * 0.72, [rgb(color, 0), rgb(color, 0), rgb(color, strength)], [0, 0.5, 1])
        sc.drawRect(skia.Rect.MakeWH(480, 270), fill(0, shader=sh))
        _VIG[key] = s.makeImageSnapshot()
    c.drawImageRect(_VIG[key], skia.Rect.MakeWH(W, H), LIN, skia.Paint())


def grade_paint(r=1.0, g=1.0, b=1.0, contrast=1.0, sat=1.0, lift=(0, 0, 0)):
    """Colour grade as a layer paint (contrast around mid grey, saturation, tint, lift)."""
    lr, lg, lb = 0.2126, 0.7152, 0.0722
    s = sat
    base = [[lr * (1 - s) + s, lg * (1 - s), lb * (1 - s)],
            [lr * (1 - s), lg * (1 - s) + s, lb * (1 - s)],
            [lr * (1 - s), lg * (1 - s), lb * (1 - s) + s]]
    gains = (r, g, b)
    m = []
    for i in range(3):
        row = [base[i][j] * contrast * gains[i] for j in range(3)]
        off = (0.5 - 0.5 * contrast) * gains[i] + lift[i] / 255.0
        m += row + [0, off]
    m += [0, 0, 0, 1, 0]
    p = skia.Paint()
    p.setColorFilter(skia.ColorFilters.Matrix(m))
    return p


# ======================================================================
#  particles
# ======================================================================
def dust(c, t, n=70, color="#bcd8ff", alpha=0.5, seed=1, rect=(0, 0, W, H), speed=1.0):
    x0, y0, x1, y1 = rect
    for i in range(n):
        depth = 0.3 + 0.7 * hash01(i, seed, 1)
        x = x0 + ((hash01(i, seed, 2) * (x1 - x0) + t * 12 * speed * (hash01(i, 4) - 0.3)) % (x1 - x0))
        y = y0 + ((hash01(i, seed, 3) * (y1 - y0) - t * 9 * speed * depth) % (y1 - y0))
        r = 1.2 + 3.5 * depth
        a = alpha * (0.4 + 0.6 * math.sin(t * (1 + hash01(i, 5) * 2) + i) ** 2)
        c.drawCircle(x, y, r, fill(rgb(color), a, blur=r * (1.4 - depth)))


def embers(c, t, n=40, color="#ff7a3a", seed=2, rect=(0, 0, W, H), speed=1.0):
    x0, y0, x1, y1 = rect
    for i in range(n):
        life = 3 + hash01(i, seed) * 3
        ph = ((t * speed + hash01(i, seed, 1) * life) % life) / life
        x = x0 + hash01(i, seed, 2) * (x1 - x0) + math.sin(t * 2 + i) * 30 * ph
        y = y1 - ph * (y1 - y0) * (0.6 + 0.4 * hash01(i, 3))
        a = math.sin(ph * math.pi) * (0.6 + 0.4 * math.sin(t * 13 + i))
        r = 2 + 3 * hash01(i, 4)
        c.drawCircle(x, y, r * 3, fill(rgb(color), a * 0.35, blur=r * 2, blend=ADD))
        c.drawCircle(x, y, r, fill(rgb("#ffe0a0"), a, blend=ADD))


def sparks(c, x, y, age, n=30, seed=3, color="#ffd27a", speed=900, spread=math.pi, angle=-math.pi / 2,
           life=0.6, gravity=1400):
    """Burst of hot sparks from (x, y); age = seconds since the hit."""
    if age < 0 or age > life * 1.6:
        return
    for i in range(n):
        a = angle + (hash01(i, seed) - 0.5) * spread
        v = speed * (0.35 + 0.65 * hash01(i, seed, 1))
        lt = life * (0.5 + 0.5 * hash01(i, seed, 2))
        if age > lt:
            continue
        px = x + math.cos(a) * v * age
        py = y + math.sin(a) * v * age + 0.5 * gravity * age * age
        vx, vy = math.cos(a) * v, math.sin(a) * v + gravity * age
        k = 0.022
        fade = 1 - age / lt
        c.drawLine(px, py, px - vx * k, py - vy * k, stroke(rgb(color), 3.5 * fade + 1, alpha=fade, blend=ADD))
        c.drawCircle(px, py, 2.5, fill(rgb("#fff6dc"), fade, blend=ADD))


def god_rays(c, x, y, t, n=9, length=1600, color="#9fd0ff", alpha=0.18, spread=1.2, angle=math.pi / 2, width=80):
    for i in range(n):
        a = angle + (i / (n - 1) - 0.5) * spread + math.sin(t * 0.4 + i) * 0.03
        w = width * (0.5 + hash01(i, 7))
        ex, ey = x + math.cos(a) * length, y + math.sin(a) * length
        nx, ny = -math.sin(a), math.cos(a)
        p = poly_path([(x, y), (ex + nx * w, ey + ny * w), (ex - nx * w, ey - ny * w)])
        al = alpha * (0.6 + 0.4 * math.sin(t * 0.9 + i * 1.7))
        c.drawPath(p, fill(0, shader=linear((x, y), (ex, ey), [rgb(color, al), rgb(color, 0)]), blend=ADD))


# ======================================================================
#  cracks / fault lines
# ======================================================================
_CRACKS = {}


def make_cracks(seed, x, y, length=600, angle=0.0, branches=6, jag=0.5, step=18):
    """Branching lightning-like crack polylines from (x, y)."""
    key = (seed, x, y, length, angle, branches, jag, step)
    if key in _CRACKS:
        return _CRACKS[key]
    rng = np.random.default_rng(seed)
    lines = []

    def grow(px, py, a, L, depth):
        pts = [(px, py)]
        dist = 0.0
        while dist < L:
            a += rng.normal() * jag * 0.5
            s = step * (0.6 + rng.random() * 0.8)
            px, py = px + math.cos(a) * s, py + math.sin(a) * s
            dist += s
            pts.append((px, py))
            if depth < 2 and rng.random() < 0.08:
                grow(px, py, a + rng.choice([-1, 1]) * (0.5 + rng.random() * 0.7), L * 0.45, depth + 1)
        lines.append((pts, depth))

    for b in range(branches):
        grow(x, y, angle + (b / max(1, branches)) * math.tau if branches > 2 else angle + rng.normal() * 0.4,
             length * (0.6 + 0.4 * rng.random()), 0)
    _CRACKS[key] = lines
    return lines


def draw_cracks(c, lines, progress=1.0, color="#ffd86a", width=4.0, glow_amt=1.0, core="#fffbe8"):
    for pts, depth in lines:
        n = max(2, int(len(pts) * clamp(progress * (1.0 + depth * 0.4) - depth * 0.25)))
        if n < 2:
            continue
        p = skia.Path()
        p.moveTo(*pts[0])
        for q in pts[1:n]:
            p.lineTo(*q)
        w = width * (1.0 - depth * 0.3)
        if glow_amt > 0:
            c.drawPath(p, stroke(rgb(color), w * 5, alpha=0.35 * glow_amt, blur=w * 2.5, blend=ADD))
        c.drawPath(p, stroke(rgb(color), w * 1.6, alpha=0.9, blend=ADD))
        c.drawPath(p, stroke(rgb(core), w * 0.6, alpha=1.0))


# ======================================================================
#  shatter
# ======================================================================
class Shards:
    def __init__(self, bounds, n=140, seed=4, center=None, power=1.0):
        x0, y0, x1, y1 = bounds
        rng = np.random.default_rng(seed)
        cx, cy = center if center else ((x0 + x1) / 2, (y0 + y1) / 2)
        # denser near the impact point
        pts = []
        for _ in range(n):
            r = (rng.random() ** 1.6) * max(x1 - x0, y1 - y0) * 0.75
            a = rng.random() * math.tau
            pts.append((clamp(cx + math.cos(a) * r, x0, x1), clamp(cy + math.sin(a) * r, y0, y1)))
        pts += [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
        for k in range(1, 6):
            pts += [(lerp(x0, x1, k / 6), y0), (lerp(x0, x1, k / 6), y1), (x0, lerp(y0, y1, k / 6)),
                    (x1, lerp(y0, y1, k / 6))]
        pts = np.array(pts)
        tri = Delaunay(pts)
        self.items = []
        for simp in tri.simplices:
            poly = pts[simp]
            gx, gy = poly.mean(axis=0)
            dx, dy = gx - cx, gy - cy
            d = math.hypot(dx, dy) + 1e-3
            v = power * (500 + 700 * rng.random()) * (0.6 + 300 / (d + 300))
            self.items.append(dict(poly=[(float(a), float(b)) for a, b in poly], c=(float(gx), float(gy)),
                                   v=(dx / d * v, dy / d * v - 200 * rng.random()),
                                   rot=(rng.random() - 0.5) * 8, delay=d / 2500.0))


def draw_shatter(c, img, shards, u, edge="#ffd86a", gravity=900, fade=1.4):
    """img: full-frame image of the object; u: seconds since the break."""
    for it in shards.items:
        tt = max(0.0, u - it["delay"] * 0.5)
        a = clamp(1 - tt / fade)
        if a <= 0:
            continue
        gx, gy = it["c"]
        ox = it["v"][0] * tt
        oy = it["v"][1] * tt + 0.5 * gravity * tt * tt
        path = poly_path(it["poly"])
        with Saved(c):
            c.translate(gx + ox, gy + oy)
            c.rotate(math.degrees(it["rot"] * tt))
            c.translate(-gx, -gy)
            sc = 1 - 0.4 * clamp(tt / fade)
            c.translate(gx, gy)
            c.scale(sc, sc)
            c.translate(-gx, -gy)
            c.save()
            c.clipPath(path, doAntiAlias=True)
            p = skia.Paint()
            p.setAlphaf(a)
            c.drawImage(img, 0, 0, LIN, p)
            c.restore()
            c.drawPath(path, stroke(rgb(edge), 2.5, alpha=a, blend=ADD))
            if tt > 0.05:
                c.drawPath(path, fill(rgb(edge), 0.25 * a * clamp(tt * 3), blend=ADD))


# ======================================================================
#  the gate (portal)
# ======================================================================
def portal(c, x, y, r, t, color="#ff2a4a", core="#12020a", intensity=1.0, squash=0.55):
    with Saved(c):
        c.translate(x, y)
        c.scale(1, squash)
        glow(c, 0, 0, r * 2.6, color, 0.45 * intensity)
        c.drawCircle(0, 0, r * 1.05, fill(rgb(core)))
        for k in range(26):
            a0 = t * (0.6 + 0.25 * (k % 3)) + k * 0.73
            rr = r * (0.25 + 0.75 * hash01(k, 3))
            sweep = 0.9 + 0.8 * hash01(k, 4)
            p = skia.Path()
            p.addArc(skia.Rect.MakeXYWH(-rr, -rr, rr * 2, rr * 2), math.degrees(a0), math.degrees(sweep))
            col = color if k % 4 else "#ffb0c0"
            c.drawPath(p, stroke(rgb(col), 3 + 6 * hash01(k, 5), alpha=0.55 * intensity, blend=ADD))
        c.drawCircle(0, 0, r, stroke(rgb(color), 10, alpha=0.9 * intensity, blend=ADD))
        c.drawCircle(0, 0, r * 1.02, stroke(rgb("#ffd0d8"), 3, alpha=0.9 * intensity))
    # jagged cracks in the sky radiating from the gate's rim
    for k in range(8):
        ang = k / 8 * math.tau + 0.3
        sx, sy = x + math.cos(ang) * r * 1.02, y + math.sin(ang) * r * 1.02 * squash
        draw_cracks(c, make_cracks(70 + k, int(sx), int(sy), r * 0.9, ang, 1, 0.7, r / 14), 1.0, color, 3,
                    0.8 * intensity, "#ffd0d8")


# ======================================================================
#  action graphics
# ======================================================================
def slash_arc(c, cx, cy, r, a0, sweep, u, color="#ff2a4a", width=60):
    """Crescent blade trail. u in 0..1 = life of the slash."""
    if u <= 0 or u >= 1:
        return
    head = a0 + sweep * min(1, u * 2.2)
    tail = a0 + sweep * max(0, (u - 0.3) * 1.6)
    if head - tail == 0:
        return
    n = 24
    outer, inner = [], []
    for i in range(n + 1):
        a = lerp(tail, head, i / n)
        w = width * math.sin(i / n * math.pi) ** 0.8
        outer.append((cx + math.cos(a) * (r + w / 2), cy + math.sin(a) * (r + w / 2)))
        inner.append((cx + math.cos(a) * (r - w / 2), cy + math.sin(a) * (r - w / 2)))
    p = poly_path(outer + inner[::-1])
    al = 1 - u
    c.drawPath(p, fill(rgb(color), 0.5 * al, blur=14, blend=ADD))
    c.drawPath(p, fill(rgb(color), 0.9 * al, blend=ADD))
    core = poly_path(outer[::2] + [(cx + math.cos(a) * r, cy + math.sin(a) * r)
                                   for a in np.linspace(head, tail, n // 2 + 1)])
    c.drawPath(core, fill(rgb("#ffffff"), 0.85 * al))


def action_bg(c, t, top="#0a0f24", bottom="#1d0f2e", line="#ffffff", alpha=0.35, direction=0.0, n=70):
    """Parallel speed lines (direction in radians) over a gradient."""
    c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(0, shader=linear((0, 0), (0, H), [rgb(top), rgb(bottom)])))
    dx, dy = math.cos(direction), math.sin(direction)
    nx, ny = -dy, dx
    for i in range(n):
        off = (hash01(i, 3) - 0.5) * 2600
        ln = 300 + 900 * hash01(i, 4)
        pos = ((t * (2500 + 1500 * hash01(i, 5)) + hash01(i, 6) * 4000) % 4000) - 2000
        x0 = W / 2 + nx * off + dx * pos
        y0 = H / 2 + ny * off + dy * pos
        w = 2 + 6 * hash01(i, 7)
        c.drawLine(x0, y0, x0 - dx * ln, y0 - dy * ln, stroke(rgb(line), w, alpha=alpha * (0.4 + 0.6 * hash01(i, 8))))


def burst(c, x, y, r, n=18, color="#ffffff", alpha=1.0, seed=5, rot=0.0):
    pts = []
    for i in range(n * 2):
        a = rot + i / (n * 2) * math.tau
        rr = r * (1.0 if i % 2 == 0 else 0.35 + 0.2 * hash01(i, seed))
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    c.drawPath(poly_path(pts), fill(rgb(color), alpha))


def shockwave(c, x, y, u, r_max=900, color="#ffffff", width=40, squash=1.0):
    if u <= 0 or u >= 1:
        return
    r = r_max * (1 - (1 - u) ** 3)
    c.drawOval(skia.Rect.MakeXYWH(x - r, y - r * squash, 2 * r, 2 * r * squash),
               stroke(rgb(color), width * (1 - u), alpha=1 - u, blend=ADD))


def lens_flare(c, x, y, t, color="#ffd0a0", alpha=1.0):
    glow(c, x, y, 260, color, 0.6 * alpha)
    c.drawLine(x - 700, y, x + 700, y, stroke(rgb(color), 4, alpha=0.5 * alpha, blur=3, blend=ADD))
    vx, vy = W / 2 - x, H / 2 - y
    for k, (f, r) in enumerate(((0.6, 40), (1.1, 70), (1.5, 30), (1.9, 110))):
        c.drawCircle(x + vx * f, y + vy * f, r, fill(rgb(color), 0.12 * alpha, blend=ADD))


# ======================================================================
#  fast post-processing in NumPy / OpenCV
# ======================================================================
import cv2  # noqa: E402

_NP = {}


def _vig_mask(strength):
    key = ("vig", round(strength, 2))
    if key not in _NP:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W * 0.72)) ** 2 + ((yy - H / 2) / (W * 0.72)) ** 2)
        m = 1 - strength * np.clip((d - 0.5) / 0.5, 0, 1) ** 1.5
        _NP[key] = m[..., None].astype(np.float32)
    return _NP[key]


def _grain_np(i):
    key = ("grain", i)
    if key not in _NP:
        rng = np.random.default_rng(100 + i)
        g = rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32)
        g = cv2.resize(g, (W, H), interpolation=cv2.INTER_NEAREST)
        _NP[key] = g[..., None]
    return _NP[key]


def post_np(c, surf, t, bloom_amt=0.6, threshold=0.6, wide=0.35, vig=0.55, grain_amt=6.0, ca=0.0,
            impact=None, tint=None, contrast=1.0, lift=(0, 0, 0)):
    """Bloom + grade + vignette + grain (+ chromatic aberration / impact frame) in one pass."""
    arr = surf.makeImageSnapshot().toarray()
    rgbf = arr[..., :3].astype(np.float32)
    if impact:
        lum = rgbf @ np.array([0.299, 0.587, 0.114], np.float32)
        k = np.clip((lum - 90) * 4, 0, 255)
        if impact == "invert":
            k = 255 - k
        col = np.array(rgb_tuple(tint or "#ffffff"), np.float32) / 255.0
        rgbf = k[..., None] * col[None, None, :]
    else:
        if bloom_amt > 0 or wide > 0:
            small = cv2.resize(rgbf, (480, 270), interpolation=cv2.INTER_AREA)
            br = np.clip((small - threshold * 255) / (1 - threshold), 0, 255)
            b1 = cv2.GaussianBlur(br, (0, 0), 5)
            b2 = cv2.GaussianBlur(cv2.resize(br, (240, 135), interpolation=cv2.INTER_AREA), (0, 0), 6)
            b2 = cv2.resize(b2, (480, 270), interpolation=cv2.INTER_LINEAR)
            bl = b1 * bloom_amt + b2 * wide
            rgbf += cv2.resize(bl, (W, H), interpolation=cv2.INTER_LINEAR) * 0.8
        if contrast != 1.0 or any(lift):
            rgbf = (rgbf - 128) * contrast + 128 + np.array(lift, np.float32)
        if tint:
            rgbf *= np.array(tint, np.float32)[None, None, :]
        if ca > 0.5:
            sc = 1 + ca / W * 2
            for ch, f in ((0, sc), (2, 1 / sc)):
                M = np.float32([[f, 0, (1 - f) * W / 2], [0, f, (1 - f) * H / 2]])
                rgbf[..., ch] = cv2.warpAffine(rgbf[..., ch], M, (W, H), borderMode=cv2.BORDER_REPLICATE)
    if vig > 0:
        rgbf *= _vig_mask(vig)
    if grain_amt > 0:
        rgbf += _grain_np(int(t * 24) % 4) * grain_amt
    out = np.empty_like(arr)
    out[..., :3] = np.clip(rgbf, 0, 255)
    out[..., 3] = 255
    img = skia.Image.fromarray(out, colorType=skia.kRGBA_8888_ColorType)
    p = skia.Paint()
    p.setBlendMode(skia.BlendMode.kSrc)
    c.drawImage(img, 0, 0, skia.SamplingOptions(), p)


def rgb_tuple(hexstr):
    h = hexstr.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

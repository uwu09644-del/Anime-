"""Painted-background toolkit: gouache-like textures, a small 3D camera, light passes.

TV anime puts flat cel characters over hand-painted backgrounds. This module fakes the
painted part: blotchy posterized noise with brush streaks and cracks (numpy / OpenCV),
mapped onto walls and floors in true perspective (Skia perspective matrices), then lit
with warm/cool light maps and finished with a soft diffusion glow and grain.
"""
import math

import cv2
import numpy as np
import skia

W, H = 1920, 1080
LIN = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)


# ---------------------------------------------------------------- colour helpers
def hex3(h):
    h = h.lstrip("#")
    return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)], np.float32)


def ramp(v, stops):
    """v: float array 0..1 -> RGB float array using hex colour stops."""
    cols = np.stack([hex3(s) for s in stops])
    xs = np.linspace(0, 1, len(stops))
    return np.stack([np.interp(v, xs, cols[:, k]) for k in range(3)], axis=-1).astype(np.float32)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- noise
def fbm(h, w, cell, octaves=5, seed=0, aspect=1.0, gain=0.5):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for _ in range(octaves):
        gh = max(2, int(h / cell) + 2)
        gw = max(2, int(w / (cell * aspect)) + 2)
        g = rng.random((gh, gw)).astype(np.float32)
        out += cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC) * amp
        tot += amp
        amp *= gain
        cell = max(1.5, cell / 2)
    out /= tot
    lo, hi = np.percentile(out, 1), np.percentile(out, 99)
    return np.clip((out - lo) / (hi - lo + 1e-9), 0, 1)


def warp(img, amount, seed=0, cell=160):
    h, w = img.shape[:2]
    dx = (fbm(h, w, cell, 3, seed) - 0.5) * 2 * amount
    dy = (fbm(h, w, cell, 3, seed + 1) - 0.5) * 2 * amount
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return cv2.remap(img, xx + dx, yy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def posterize(v, levels, soft=0.18):
    x = v * levels
    f = x - np.floor(x)
    return (np.floor(x) + smoothstep(0.5 - soft, 0.5 + soft, f)) / levels


def streaks(h, w, seed, length=14.0, cell=10, angle=0.0):
    """Directional dry-brush streaks."""
    s = fbm(h, w, cell, 3, seed, aspect=length)
    if angle:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.3)
        s = cv2.warpAffine(s, M, (w, h), borderMode=cv2.BORDER_REFLECT)
    return s


# ---------------------------------------------------------------- painted materials
def paint_rock(h, w, stops, seed=1, blotch=260, crack=0.55, angle=-70, levels=6):
    big = warp(fbm(h, w, blotch, 4, seed), 90, seed + 7, 220)
    mid = fbm(h, w, blotch / 4, 4, seed + 2)
    st = streaks(h, w, seed + 3, 10, 9, angle)
    v = 0.56 * big + 0.30 * mid + 0.14 * st
    v = (v - v.min()) / (v.max() - v.min() + 1e-9)
    v = posterize(v, levels, 0.14)
    rgb = ramp(v, stops)
    # cracks and crevices: ridged noise drawn as dark brush lines
    r = 1 - np.abs(2 * warp(fbm(h, w, blotch * 0.7, 4, seed + 11), 60, seed + 5) - 1)
    gate = smoothstep(0.45, 0.7, fbm(h, w, blotch * 1.3, 2, seed + 17))     # break lines into strokes
    line = smoothstep(0.95, 0.99, r) * gate
    r2 = 1 - np.abs(2 * fbm(h, w, blotch * 0.22, 3, seed + 13) - 1)
    fine = smoothstep(0.97, 0.995, r2) * 0.35 * (1 - gate)
    dark = np.clip(line + fine, 0, 1) * crack
    rgb *= (1 - dark)[..., None]
    # sparse dry-brush flecks of light
    fl = smoothstep(0.80, 0.9, streaks(h, w, seed + 21, 6, 5, angle + 20)) * smoothstep(0.55, 0.8, big)
    rgb += fl[..., None] * 22
    return np.clip(rgb, 0, 255)


def paint_floor(h, w, stops, seed=3, levels=5):
    big = warp(fbm(h, w, 300, 4, seed, aspect=1.6), 70, seed + 3, 260)
    st = streaks(h, w, seed + 4, 18, 8, 0)
    v = posterize(0.6 * big + 0.4 * st, levels, 0.16)
    rgb = ramp(v, stops)
    r = 1 - np.abs(2 * fbm(h, w, 200, 4, seed + 9) - 1)
    rgb *= (1 - smoothstep(0.95, 0.99, r) * 0.45)[..., None]
    return np.clip(rgb, 0, 255)


def paint_panels(h, w, stops, seed=5, rows=3, cols=6, grout=5):
    """Concrete / tile panels with painted variation between panels."""
    base = paint_floor(h, w, stops, seed, 4)
    rng = np.random.default_rng(seed)
    ph, pw = h // rows, w // cols
    for r in range(rows):
        for c_ in range(cols):
            k = 0.86 + 0.26 * rng.random()
            base[r * ph:(r + 1) * ph, c_ * pw:(c_ + 1) * pw] *= k
    for r in range(1, rows):
        base[r * ph - grout // 2:r * ph + grout // 2 + 1] *= 0.45
    for c_ in range(1, cols):
        base[:, c_ * pw - grout // 2:c_ * pw + grout // 2 + 1] *= 0.45
    # stains running down
    st = streaks(h, w, seed + 8, 16, 7, 90)
    base *= (1 - smoothstep(0.62, 0.9, st) * 0.3)[..., None]
    return np.clip(base, 0, 255)


def paint_glow(h, w, seed=9, stops=("#3a1404", "#b84a0a", "#ff9a1e", "#ffd86a", "#fff6d8")):
    """Painterly fire/energy light: hot core fading out, with dark flecks."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w * 0.5)) ** 2 + ((yy - h / 2) / (h * 0.5)) ** 2)
    n = warp(fbm(h, w, 120, 5, seed), 60, seed + 2, 120)
    v = np.clip(1.15 - d * 1.05 + (n - 0.5) * 0.55, 0, 1)
    v = posterize(v, 7, 0.2)
    rgb = ramp(v, stops)
    fl = smoothstep(0.78, 0.86, fbm(h, w, 18, 3, seed + 4, aspect=0.6)) * smoothstep(0.25, 0.6, d)
    rgb *= (1 - 0.75 * fl)[..., None]
    alpha = smoothstep(0.02, 0.35, v)
    return rgb, alpha


# ---------------------------------------------------------------- numpy <-> skia
def to_image(rgb, alpha=None):
    h, w = rgb.shape[:2]
    out = np.empty((h, w, 4), np.uint8)
    if alpha is None:
        out[..., :3] = np.clip(rgb, 0, 255)
        out[..., 3] = 255
    else:
        a = np.clip(alpha, 0, 1)[..., None]
        out[..., :3] = np.clip(rgb * a, 0, 255)  # premultiplied
        out[..., 3] = (a[..., 0] * 255)
    img = skia.Image.fromarray(np.ascontiguousarray(out), colorType=skia.kRGBA_8888_ColorType,
                               alphaType=skia.kPremul_AlphaType)
    try:
        img = img.withDefaultMipmaps()
    except Exception:
        pass
    return img


def surface(w=W, h=H):
    info = skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    return skia.Surface.MakeRaster(info)


def to_array(surf):
    return surf.makeImageSnapshot().toarray().astype(np.float32)


# ---------------------------------------------------------------- 3D camera
class Cam:
    """Pinhole camera. World: x right, y up, z forward (metres)."""

    def __init__(self, pos, look, fov=50.0, w=W, h=H):
        self.pos = np.array(pos, np.float64)
        f = np.array(look, np.float64) - self.pos
        self.fwd = f / np.linalg.norm(f)
        r = np.cross([0, 1, 0], self.fwd)
        self.right = r / np.linalg.norm(r)
        self.up = np.cross(self.fwd, self.right)
        self.f = (w / 2) / math.tan(math.radians(fov) / 2)
        self.w, self.h = w, h

    def project(self, p):
        d = np.array(p, np.float64) - self.pos
        z = float(d @ self.fwd)
        zz = max(z, 0.05)
        return (self.w / 2 + self.f * float(d @ self.right) / zz, self.h / 2 - self.f * float(d @ self.up) / zz, z)

    def px_per_m(self, p):
        return self.f / max(self.project(p)[2], 0.05)


def quad(c, img, cam, p0, p1, p2, p3, paint=None, flip=False):
    """Map img onto the 3D quad p0(top-left) p1(top-right) p2(bottom-right) p3(bottom-left)."""
    pts = [cam.project(p) for p in (p0, p1, p2, p3)]
    if min(p[2] for p in pts) < 0.06:
        return
    iw, ih = img.width(), img.height()
    src = [skia.Point(0, 0), skia.Point(iw, 0), skia.Point(iw, ih), skia.Point(0, ih)]
    if flip:
        src = [src[1], src[0], src[3], src[2]]
    dst = [skia.Point(p[0], p[1]) for p in pts]
    m = skia.Matrix()
    if not m.setPolyToPoly(src, dst):
        return
    c.save()
    c.concat(m)
    c.drawImage(img, 0, 0, LIN, paint)
    c.restore()


def strip(c, img, cam, top_a, top_b, bot_a, bot_b, n, paint=None):
    """A long surface from edge a (near) to edge b (far), tiled n times (mirrored so seams match)."""
    ta, tb, ba, bb = (np.array(v, np.float64) for v in (top_a, top_b, bot_a, bot_b))
    for i in range(n):
        u0, u1 = i / n, (i + 1) / n
        quad(c, img, cam, ta + (tb - ta) * u0, ta + (tb - ta) * u1, ba + (bb - ba) * u1, ba + (bb - ba) * u0,
             paint, flip=bool(i % 2))


def line3(c, cam, a, b, paint):
    pa, pb = cam.project(a), cam.project(b)
    if pa[2] > 0.06 and pb[2] > 0.06:
        c.drawLine(pa[0], pa[1], pb[0], pb[1], paint)


def poly3(c, cam, pts, paint):
    pp = [cam.project(p) for p in pts]
    if min(p[2] for p in pp) < 0.06:
        return
    path = skia.Path()
    path.moveTo(pp[0][0], pp[0][1])
    for p in pp[1:]:
        path.lineTo(p[0], p[1])
    path.close()
    c.drawPath(path, paint)


# ---------------------------------------------------------------- light + finishing (numpy)
def light_map(h, w, lights, ambient):
    """lights: [(x, y, radius, hex colour, strength, squash_y)] -> per-pixel RGB multiplier."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    out = np.ones((h, w, 3), np.float32) * (hex3(ambient) / 255.0)
    for (lx, ly, rad, col, strength, sq) in lights:
        d2 = ((xx - lx) / rad) ** 2 + ((yy - ly) / (rad * sq)) ** 2
        fall = 1.0 / (1.0 + d2 * 3.0)
        out += fall[..., None] * (hex3(col) / 255.0) * strength
    return out


def blur(arr, sigma):
    return cv2.GaussianBlur(arr, (0, 0), sigma)


def finish(rgb, t=0.0, glow=0.22, glow_sigma=18, vig=0.4, grain=2.5, tint=(1.0, 1.0, 1.0), contrast=1.04,
           highlights=0.35):
    """Final composite pass: diffusion glow, soft highlight bloom, grade, vignette, fine grain."""
    h, w = rgb.shape[:2]
    small = cv2.resize(rgb, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
    soft = cv2.resize(cv2.GaussianBlur(small, (0, 0), glow_sigma / 4), (w, h), interpolation=cv2.INTER_LINEAR)
    out = 255 - (255 - rgb) * (255 - soft * glow) / 255          # screen a soft copy: "diffusion filter"
    hi = np.clip(small - 190, 0, 255) * (255.0 / 65.0)
    hi = cv2.resize(cv2.GaussianBlur(hi, (0, 0), 9), (w, h), interpolation=cv2.INTER_LINEAR)
    out += hi * highlights
    out = (out - 128) * contrast + 128
    out *= np.array(tint, np.float32)
    if vig > 0:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xx - w / 2) / (w * 0.75)) ** 2 + ((yy - h / 2) / (w * 0.75)) ** 2)
        out *= (1 - vig * np.clip((d - 0.45) / 0.55, 0, 1) ** 1.6)[..., None]
    if grain > 0:
        rng = np.random.default_rng(int(t * 24) + 3)
        g = rng.normal(0, 1, (h // 2, w // 2)).astype(np.float32)
        out += cv2.resize(g, (w, h), interpolation=cv2.INTER_LINEAR)[..., None] * grain
    return np.clip(out, 0, 255)


def save_png(rgb, path):
    cv2.imwrite(path, cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR))

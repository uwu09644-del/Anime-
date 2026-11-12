"""Look-development frames for the "painted background + cel character" style.

    python cel/lookdev.py            # writes cel/lookdev/*.png

Shot A: Kai and Hana from behind in the collapsed tunnel, lit by the fracture.
Shot B: Hana in three-quarter view, over Kai's out-of-focus shoulder.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "studio"))
sys.path.insert(0, ROOT)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import skia  # noqa: E402

from cel import figures as F  # noqa: E402
from cel import paint as P  # noqa: E402
from gfx import ADD, Saved, fill, hash01, linear, mix, poly_path, rgb, smooth_path, stroke  # noqa: E402

W, H = P.W, P.H
OUT = os.path.join(HERE, "lookdev")
_TEX = {}


def tex(name):
    if name not in _TEX:
        if name == "rock":
            _TEX[name] = P.to_image(P.paint_rock(1024, 1536, ["#231a14", "#4a3424", "#7a5634", "#a67844", "#cf9c58",
                                                              "#ecc078"], seed=4, crack=0.5, angle=-25))
        elif name == "rock2":
            _TEX[name] = P.to_image(P.paint_rock(1024, 1536, ["#1e1814", "#3e2e22", "#66492e", "#8e683c", "#b88a4e",
                                                              "#d8ac68"], seed=14, crack=0.6, angle=-80))
        elif name == "floor":
            _TEX[name] = P.to_image(P.paint_floor(1024, 1024, ["#241c16", "#48382a", "#6e553a", "#927148",
                                                               "#b48e5c"], seed=6))
        elif name == "glow":
            g, a = P.paint_glow(1000, 520, seed=9)
            _TEX[name] = P.to_image(g, a)
    return _TEX[name]


def rift_path(cx, cy, w, h, seed=1):
    pts_l, pts_r = [], []
    n = 9
    for i in range(n + 1):
        u = i / n
        y = cy - h / 2 + h * u
        half = w / 2 * math.sin(u * math.pi) ** 0.7 * (0.75 + 0.5 * hash01(i, seed))
        j = (hash01(i, seed, 2) - 0.5) * w * 0.5
        pts_l.append((cx - half + j, y))
        pts_r.append((cx + half + j, y))
    return poly_path(pts_l + pts_r[::-1])


# ======================================================================
#  the tunnel plate
# ======================================================================
def tunnel_plate(cam, rift_at=(1.6, 2.1, 32.0), far=32.0, half_w=4.4, height=5.4):
    """Painted background (walls, floor, rails, rubble) + light pass. Returns RGB float array and
    the rift's screen position."""
    s = P.surface()
    c = s.getCanvas()
    c.clear(skia.ColorBLACK)
    z0 = 0.6
    hw = half_w
    # end wall, ceiling, walls, floor
    P.quad(c, tex("rock2"), cam, (-hw, height, far), (hw, height, far), (hw, 0, far), (-hw, 0, far))
    P.strip(c, tex("rock2"), cam, (-hw, height, z0), (-hw, height, far), (hw, height, z0), (hw, height, far), 5)
    P.strip(c, tex("rock"), cam, (-hw, height, z0), (-hw, height, far), (-hw, 0, z0), (-hw, 0, far), 5)
    P.strip(c, tex("rock"), cam, (hw, height, far), (hw, height, z0), (hw, 0, far), (hw, 0, z0), 5)
    P.strip(c, tex("floor"), cam, (-hw, 0, far), (hw, 0, far), (-hw, 0, z0), (hw, 0, z0), 1)
    P.strip(c, tex("floor"), cam, (-hw, 0, z0 + 0.01), (-hw, 0, far), (hw, 0, z0 + 0.01), (hw, 0, far), 6)
    # concrete ribs along the tunnel (remains of the subway)
    for k, z in enumerate((5.5, 12.0, 20.0, 27.0)):
        col = rgb("#17120f")
        for sx in (-1, 1):
            if (k + (sx > 0)) % 3 == 0:
                continue                       # some ribs have collapsed
            P.poly3(c, cam, [(sx * hw, 0, z), (sx * hw, height, z), (sx * hw, height, z + 0.6), (sx * hw, 0, z + 0.6)],
                    fill(rgb("#2a211a")))
            P.poly3(c, cam, [(sx * hw, 0, z), (sx * hw, height, z), (sx * (hw - 0.35), height, z),
                             (sx * (hw - 0.35), 0, z)], fill(col))
    # fallen slabs and boulders silhouetted against the light
    rngb = np.random.default_rng(23)
    for k in range(9):
        z = 9 + rngb.random() * 20
        x = (-1 if k % 2 else 1) * (1.6 + rngb.random() * 2.4)
        r = 0.5 + rngb.random() * 0.9
        pts = [(x + math.cos(a) * r * (0.7 + 0.6 * rngb.random()), max(0, math.sin(a)) * r * (0.8 + 0.9 * rngb.random()), z)
               for a in np.linspace(0, math.pi, 7)]
        P.poly3(c, cam, pts, fill(rgb(mix("#241a14", "#4a3626", rngb.random()))))
        P.poly3(c, cam, pts, stroke(rgb("#0e0a08"), 2))
    # rails + sleepers
    for sx in (-0.72, 0.72):
        for off, colr, wd in ((0.0, "#141110", 9), (0.04, "#8a7458", 2.5)):
            pa, pb = cam.project((sx + off + 1.0, 0.02, z0)), cam.project((sx + off + 1.0, 0.02, far))
            c.drawLine(pa[0], pa[1], pb[0], pb[1], stroke(rgb(colr), wd))
    for k in range(40):
        z = 1.2 + k * 0.62
        if z > far - 0.5:
            break
        P.poly3(c, cam, [(-0.1, 0.01, z), (2.1, 0.01, z), (2.1, 0.01, z + 0.22), (-0.1, 0.01, z + 0.22)],
                fill(rgb("#1c1612"), 0.75))
    # rubble along the walls
    rng = np.random.default_rng(11)
    for k in range(90):
        z = 1.5 + rng.random() * (far - 2)
        sx = -1 if rng.random() < 0.5 else 1
        x = sx * (hw - 0.2 - rng.random() ** 2 * 1.6)
        r = 0.12 + rng.random() * 0.4
        pts = [(x + math.cos(a) * r * (0.7 + 0.5 * rng.random()), max(0, math.sin(a)) * r * (0.6 + 0.8 * rng.random()), z)
               for a in np.linspace(0, math.pi, 6)]
        shade = rng.random()
        P.poly3(c, cam, pts, fill(rgb(mix("#2c2219", "#6a4e34", shade))))
        P.poly3(c, cam, pts, stroke(rgb("#120e0b"), 1.6))
    plate = P.to_array(s)[..., :3]

    # ---- light pass: warm fracture light deep in the tunnel, cool darkness near the camera
    rx, ry, rz = cam.project(rift_at)
    fx_, fy_, _ = cam.project((rift_at[0], 0.0, rift_at[2] - 4))
    lm = P.light_map(H, W, [(rx, ry, 330, "#ffb866", 1.7, 1.0), (rx, ry, 1100, "#ff8a3c", 0.42, 0.8),
                            (fx_, fy_ + 160, 800, "#ffa850", 0.75, 0.2)], "#10162c")
    plate = plate * lm
    # cool bounce light from the left wall near camera so shadows are blue, not black
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    plate += (np.clip(1 - xx / 700, 0, 1) ** 2)[..., None] * np.array([6, 10, 22], np.float32)
    return np.clip(plate, 0, 255), (rx, ry)


def draw_rift(c, x, y, h, t=0.0):
    w = h * 0.52
    c.drawImageRect(tex("glow"), skia.Rect.MakeXYWH(x - w, y - h * 0.62, w * 2, h * 1.24), P.LIN)
    core = rift_path(x, y, h * 0.16, h * 0.8, seed=3)
    c.drawPath(core, fill(rgb("#fff8e0")))
    p = skia.Paint(AntiAlias=True)
    p.setColor(rgb("#ffd27a"))
    p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, h * 0.05))
    p.setBlendMode(ADD)
    c.drawPath(core, p)


def light_rays(c, x, y, n=9, length=1150, alpha=0.035, seed=2):
    for i in range(n):
        a = math.pi * (0.62 + 0.76 * i / (n - 1)) + (hash01(i, seed) - 0.5) * 0.1
        w = 24 + 60 * hash01(i, seed, 1)
        ex, ey = x + math.cos(a) * length, y + math.sin(a) * length
        nx, ny = -math.sin(a) * w, math.cos(a) * w
        c.drawPath(poly_path([(x, y), (ex + nx, ey + ny), (ex - nx, ey - ny)]),
                   fill(0, shader=linear((x, y), (ex, ey), [rgb("#ffcf8a", alpha * 2), rgb("#ffcf8a", 0)]), blend=ADD))


def dust(c, t, n, x0, y0, x1, y1, color="#ffd9a0", seed=5):
    for i in range(n):
        x = x0 + hash01(i, seed) * (x1 - x0) + math.sin(t * 0.6 + i) * 8
        y = y0 + ((hash01(i, seed, 2) * (y1 - y0) - t * 6 * (0.3 + hash01(i, 3))) % (y1 - y0))
        r = 1.0 + 2.2 * hash01(i, 4)
        c.drawCircle(x, y, r, fill(rgb(color), 0.25 + 0.5 * hash01(i, 6), blur=r * 0.6))


def shadow_on_floor(c, sil, x, y, s, kx, ky, alpha=0.6, blur=6):
    """Skew a figure silhouette (local units) down onto the floor from its feet at (x, y)."""
    m = skia.Matrix()
    m.setAll(s, -kx * s, x, 0, -ky * s, y, 0, 0, 1)
    sh = skia.Path(sil)
    sh.transform(m)
    c.drawPath(sh, fill(rgb("#06070e"), alpha, blur=blur))


def layer_to_rgb(base_rgb, layer_surface):
    """Composite a premultiplied Skia layer over an RGB float array."""
    a = P.to_array(layer_surface)
    al = a[..., 3:4] / 255.0
    return base_rgb * (1 - al) + a[..., :3]


# ======================================================================
#  SHOT A
# ======================================================================
def shot_a(t=0.0):
    cam = P.Cam((-0.5, 1.22, 0.0), (1.1, 1.55, 20.0), fov=50)
    plate, (rx, ry) = tunnel_plate(cam)
    s = P.surface()
    c = s.getCanvas()
    c.drawImage(P.to_image(plate), 0, 0)
    rift_h = cam.px_per_m((1.6, 2.1, 32.0)) * 4.6
    draw_rift(c, rx, ry + 10, rift_h, t)
    light_rays(c, rx, ry)
    # characters: Hana nearer on the left, Kai a few steps ahead on the right
    hana_w = (-0.95, 0.0, 2.75)
    kai_w = (1.0, 0.0, 4.4)
    hx, hy, _ = cam.project(hana_w)
    kx, ky, _ = cam.project(kai_w)
    hh = cam.px_per_m(hana_w) * 1.63
    kh = cam.px_per_m(kai_w) * 1.76
    amb = "#182040"
    # shadows first (light is ahead of them: shadows fall toward the camera)
    rec = skia.PictureRecorder()
    rc = rec.beginRecording(skia.Rect.MakeWH(W, H))
    celk = F.kai_back(rc, 0, 0, 1000, light=(-0.6, -0.4), ambient=amb)
    celh = F.hana_back(rc, 0, 0, 1000, light=(0.7, -0.4), ambient=amb)
    rec.finishRecordingAsPicture()
    shadow_on_floor(c, celk.silhouette(), kx, ky, kh / 1000, 0.25, 0.55, 0.7, 7)
    shadow_on_floor(c, celh.silhouette(), hx, hy, hh / 1000, -0.3, 0.55, 0.7, 9)
    # cel layer
    F.kai_back(c, kx, ky, kh, light=(-0.75, -0.35), ambient=amb, rim_col="#ffc070", head_turn=0.0)
    F.hana_back(c, hx, hy, hh, light=(0.8, -0.35), ambient=amb, rim_col="#ffc070", sway=0.25)
    # warm haze from the fracture washing over everything near it, then dust in the light
    p = skia.Paint(AntiAlias=True)
    p.setShader(skia.GradientShader.MakeRadial(skia.Point(rx, ry), 520, [rgb("#ffb86a", 0.22), rgb("#ff9a4a", 0.0)]))
    p.setBlendMode(ADD)
    c.drawCircle(rx, ry, 520, p)
    dust(c, t, 90, rx - 600, ry - 420, rx + 600, ry + 460)
    # dark out-of-focus rock in the near foreground for depth
    fg = P.surface()
    fc = fg.getCanvas()
    fc.clear(skia.ColorTRANSPARENT)
    fc.drawPath(smooth_path([(1760, -40), (1800, 200), (1790, 520), (1840, 800), (1800, 1120), (2000, 1120),
                             (2000, -40)], tension=0.8), fill(rgb("#0b0d1a")))
    fc.drawPath(smooth_path([(-40, 780), (120, 860), (300, 1010), (360, 1120), (-40, 1120)], tension=0.8),
                fill(rgb("#0a0c18")))
    out = P.to_array(s)[..., :3]
    fa = P.to_array(fg)
    fa = cv2.GaussianBlur(fa, (0, 0), 14)
    al = fa[..., 3:4] / 255.0
    out = out * (1 - al) + fa[..., :3]
    return P.finish(out, t, glow=0.20, vig=0.5, grain=2.2, tint=(1.0, 0.985, 0.97), contrast=1.05, highlights=0.4)


# ======================================================================
#  SHOT B
# ======================================================================
def shot_b(t=0.0, mouth=0.0):
    # the wall behind Hana: a side view of the tunnel, slightly out of focus
    cam = P.Cam((0.2, 1.5, 3.0), (5.0, 1.6, 8.5), fov=38)
    s = P.surface()
    c = s.getCanvas()
    c.clear(skia.ColorBLACK)
    hw, height = 4.4, 5.4
    P.strip(c, tex("rock"), cam, (hw, height, 20), (hw, height, 0.8), (hw, 0, 20), (hw, 0, 0.8), 3)
    P.strip(c, tex("floor"), cam, (-hw, 0, 20), (hw, 0, 20), (-hw, 0, 0.8), (hw, 0, 0.8), 3)
    for z in (5.2, 9.4, 14.0):
        P.poly3(c, cam, [(hw, 0, z), (hw, height, z), (hw, height, z + 0.8), (hw, 0, z + 0.8)], fill(rgb("#2a211a")))
        P.poly3(c, cam, [(hw, 0, z), (hw, height, z), (hw - 0.5, height, z), (hw - 0.5, 0, z)], fill(rgb("#17120f")))
    plate = P.to_array(s)[..., :3]
    lm = P.light_map(H, W, [(-200, 420, 900, "#ffb25e", 1.5, 1.0), (1700, 300, 700, "#3a5aa0", 0.35, 1.0)], "#1a2140")
    plate = cv2.GaussianBlur(plate * lm, (0, 0), 5.0)
    # cel layer
    cs = P.surface()
    cc = cs.getCanvas()
    cc.clear(skia.ColorTRANSPARENT)
    F.hana_34(cc, 1090, 430, 1.62, light=(-1.0, -0.25), rim_col="#ffc884", ambient="#1c2444", mouth=mouth,
              look=(-0.4, 0.0), brow=0.2, sway=0.2)
    cel = P.to_array(cs)
    al = cel[..., 3:4] / 255.0
    # scene light on the character: warm from the left, cool and darker to the right / below
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    grad = 1.02 - 0.30 * np.clip((xx - 900) / 900, 0, 1) - 0.22 * np.clip((yy - 600) / 500, 0, 1)
    tintc = np.stack([grad * 1.0, grad * 0.95, grad * 0.94 + 0.03], axis=-1)
    out = plate * (1 - al) + cel[..., :3] * tintc
    # foreground: Kai's shoulder and head, heavily out of focus
    fs = P.surface()
    fc = fs.getCanvas()
    fc.clear(skia.ColorTRANSPARENT)
    F.kai_ots(fc, 250, 620, 1.55, rim_col="#ffb870", ambient="#141a34")
    fa = cv2.GaussianBlur(P.to_array(fs), (0, 0), 17)
    al = fa[..., 3:4] / 255.0
    out = out * (1 - al) + fa[..., :3]
    return P.finish(out, t, glow=0.18, vig=0.45, grain=2.2, tint=(1.0, 0.985, 0.975), contrast=1.04, highlights=0.3)


def main():
    os.makedirs(OUT, exist_ok=True)
    P.save_png(shot_a(), os.path.join(OUT, "shot_a.png"))
    P.save_png(shot_b(), os.path.join(OUT, "shot_b.png"))
    print("wrote", OUT)


if __name__ == "__main__":
    main()

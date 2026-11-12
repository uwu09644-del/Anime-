"""A short moving test of the painted-background look -> cel/lookdev/look_test.mp4

    python cel/testclip.py

Shot A (5.5 s): slow multiplane push-in on Kai and Hana watching the fracture; the light flickers,
dust drifts, hair and coat move on twos.
Shot B (4.5 s): Hana, over Kai's shoulder: "You broke it. With a pipe." (lip-synced, with a blink).
"""
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "studio"))
sys.path.insert(0, ROOT)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import skia  # noqa: E402

import audio as A  # noqa: E402
from cel import figures as F  # noqa: E402
from cel import lookdev as L  # noqa: E402
from cel import paint as P  # noqa: E402
from faultline import sound as S  # noqa: E402
from gfx import ADD, draw_text, ease_in_out, font, rgb, smooth_path, fill  # noqa: E402

W, H, FPS = P.W, P.H, 24
DUR_A, DUR_B = 5.5, 4.5
LINE = "You broke it. With a pipe."
LINE_AT = 0.7
BUILD = os.path.join(ROOT, "build", "look_test")


def zoom(arr, z, cx, cy):
    M = np.float32([[z, 0, (1 - z) * cx], [0, z, (1 - z) * cy]])
    return cv2.warpAffine(arr, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def over(base, layer):
    al = layer[..., 3:4] / 255.0
    return base * (1 - al) + layer[..., :3]


def twos(t):
    return math.floor(t * 12) / 12


def flicker(t):
    return 1 + 0.05 * math.sin(t * 11) + 0.035 * math.sin(t * 17.3 + 1) + 0.02 * math.sin(t * 29 + 2)


# ---------------------------------------------------------------- shot A
def prep_a():
    cam = P.Cam((-0.5, 1.22, 0.0), (1.1, 1.55, 20.0), fov=50)
    plate, (rx, ry) = L.tunnel_plate(cam)
    s = P.surface()
    c = s.getCanvas()
    c.drawImage(P.to_image(plate), 0, 0)
    L.draw_rift(c, rx, ry + 10, cam.px_per_m((1.6, 2.1, 32.0)) * 4.6)
    L.light_rays(c, rx, ry)
    bg = P.to_array(s)[..., :3]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - rx) / 800) ** 2 + ((yy - ry) / 800) ** 2)
    mask = (np.clip(1 - d, 0, 1) ** 1.5)[..., None]
    fg = P.surface()
    fc = fg.getCanvas()
    fc.clear(skia.ColorTRANSPARENT)
    fc.drawPath(smooth_path([(1760, -40), (1800, 200), (1790, 520), (1840, 800), (1800, 1120), (2000, 1120),
                             (2000, -40)], tension=0.8), fill(rgb("#0b0d1a")))
    fc.drawPath(smooth_path([(-40, 780), (120, 860), (300, 1010), (360, 1120), (-40, 1120)], tension=0.8),
                fill(rgb("#0a0c18")))
    fga = cv2.GaussianBlur(P.to_array(fg), (0, 0), 14)
    rec = skia.PictureRecorder()
    rc = rec.beginRecording(skia.Rect.MakeWH(W, H))
    sil_k = F.kai_back(rc, 0, 0, 1000, light=(-0.6, -0.4)).silhouette()
    sil_h = F.hana_back(rc, 0, 0, 1000, light=(0.7, -0.4)).silhouette()
    rec.finishRecordingAsPicture()
    return dict(cam=cam, bg=bg, mask=mask, fg=fga, rx=rx, ry=ry, sil_k=sil_k, sil_h=sil_h, surf=P.surface())


def frame_a(st, t):
    u = ease_in_out(t / DUR_A)
    rx, ry, cam = st["rx"], st["ry"], st["cam"]
    fl = flicker(t)
    bg = zoom(st["bg"], 1 + 0.03 * u, rx, ry) * (1 + st["mask"] * (fl - 1) * 2.2)
    s = st["surf"]
    c = s.getCanvas()
    c.clear(skia.ColorTRANSPARENT)
    c.save()
    z = 1 + 0.07 * u
    c.translate(rx, ry)
    c.scale(z, z)
    c.translate(-rx, -ry)
    hana_w, kai_w = (-0.95, 0.0, 2.75), (1.0, 0.0, 4.4)
    hx, hy, _ = cam.project(hana_w)
    kx, ky, _ = cam.project(kai_w)
    hh, kh = cam.px_per_m(hana_w) * 1.63, cam.px_per_m(kai_w) * 1.76
    amb = "#182040"
    tq = twos(t)
    L.shadow_on_floor(c, st["sil_k"], kx, ky, kh / 1000, 0.25, 0.55, 0.7, 7)
    L.shadow_on_floor(c, st["sil_h"], hx, hy, hh / 1000, -0.3, 0.55, 0.7, 9)
    breathe = 1 + 0.004 * math.sin(tq * 1.9)
    F.kai_back(c, kx, ky, kh * breathe, light=(-0.75, -0.35), ambient=amb, rim_col="#ffc070")
    F.hana_back(c, hx, hy, hh, light=(0.8, -0.35), ambient=amb, rim_col="#ffc070",
                sway=0.2 + 0.22 * math.sin(tq * 1.4))
    p = skia.Paint(AntiAlias=True)
    p.setShader(skia.GradientShader.MakeRadial(skia.Point(rx, ry), 520,
                                               [rgb("#ffb86a", 0.22 * fl), rgb("#ff9a4a", 0.0)]))
    p.setBlendMode(ADD)
    c.drawCircle(rx, ry, 520, p)
    L.dust(c, t, 90, rx - 600, ry - 420, rx + 600, ry + 460)
    c.restore()
    out = over(bg, P.to_array(s))
    out = over(out, zoom(st["fg"], 1 + 0.14 * u, rx, ry))
    return P.finish(out, t, glow=0.20, vig=0.5, grain=2.2, tint=(1.0, 0.985, 0.97), contrast=1.05, highlights=0.4)


# ---------------------------------------------------------------- shot B
def prep_b():
    cam = P.Cam((0.2, 1.5, 3.0), (5.0, 1.6, 8.5), fov=38)
    s = P.surface()
    c = s.getCanvas()
    c.clear(skia.ColorBLACK)
    hw, height = 4.4, 5.4
    P.strip(c, L.tex("rock"), cam, (hw, height, 20), (hw, height, 0.8), (hw, 0, 20), (hw, 0, 0.8), 3)
    P.strip(c, L.tex("floor"), cam, (-hw, 0, 20), (hw, 0, 20), (-hw, 0, 0.8), (hw, 0, 0.8), 3)
    for z in (5.2, 9.4, 14.0):
        P.poly3(c, cam, [(hw, 0, z), (hw, height, z), (hw, height, z + 0.8), (hw, 0, z + 0.8)], fill(rgb("#2a211a")))
        P.poly3(c, cam, [(hw, 0, z), (hw, height, z), (hw - 0.5, height, z), (hw - 0.5, 0, z)], fill(rgb("#17120f")))
    plate = P.to_array(s)[..., :3]
    lm = P.light_map(H, W, [(-200, 420, 900, "#ffb25e", 1.5, 1.0), (1700, 300, 700, "#3a5aa0", 0.35, 1.0)], "#1a2140")
    plate = cv2.GaussianBlur(plate * lm, (0, 0), 5.0)
    fs = P.surface()
    fc = fs.getCanvas()
    fc.clear(skia.ColorTRANSPARENT)
    F.kai_ots(fc, 250, 620, 1.55, rim_col="#ffb870", ambient="#141a34")
    fga = cv2.GaussianBlur(P.to_array(fs), (0, 0), 17)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    grad = 1.02 - 0.30 * np.clip((xx - 900) / 900, 0, 1) - 0.22 * np.clip((yy - 600) / 500, 0, 1)
    tintc = np.stack([grad * 1.0, grad * 0.95, grad * 0.94 + 0.03], axis=-1)
    warm = np.clip(1 - xx / 1300, 0, 1)[..., None]
    return dict(plate=plate, fg=fga, tint=tintc, warm=warm, surf=P.surface())


def frame_b(st, t, env):
    u = ease_in_out(t / DUR_B)
    fl = flicker(t + 3)
    tq = twos(t)
    i = int((tq - LINE_AT) * FPS)
    m = env[i] if 0 <= i < len(env) else 0.0
    m = 0.0 if m < 0.15 else (0.5 if m < 0.55 else 1.0)          # three mouth shapes, like TV anime
    bl = 1.0 if (3.3 <= t < 3.42) or (0.25 <= t < 0.35) else 0.0
    s = st["surf"]
    c = s.getCanvas()
    c.clear(skia.ColorTRANSPARENT)
    c.save()
    z = 1 + 0.035 * u
    c.translate(1090, 430)
    c.scale(z, z)
    c.translate(-1090, -430)
    F.hana_34(c, 1090, 430 + math.sin(tq * 1.7) * 1.5, 1.62, light=(-1.0, -0.25), rim_col="#ffc884",
              ambient="#1c2444", mouth=m, blink=bl, look=(-0.4, 0.0), brow=0.25, smile=0.5 if t > 3.6 else 0.0,
              sway=0.15 + 0.12 * math.sin(tq * 1.3))
    c.restore()
    cel = P.to_array(s)
    al = cel[..., 3:4] / 255.0
    lit = st["tint"] * (1 + st["warm"] * (fl - 1) * 1.6)
    out = zoom(st["plate"], 1 + 0.015 * u, 1090, 430) * (1 + st["warm"] * (fl - 1) * 1.2)
    out = out * (1 - al) + cel[..., :3] * lit
    out = over(out, zoom(st["fg"], 1 + 0.07 * u, 1400, 500))
    return P.finish(out, t, glow=0.18, vig=0.45, grain=2.2, tint=(1.0, 0.985, 0.975), contrast=1.04, highlights=0.3)


# ---------------------------------------------------------------- sound + assembly
def build_audio(voice):
    L_ = DUR_A + DUR_B + 0.5
    n = A.secs(L_)
    bus = A.Bus(L_)
    bus.buf[:, :n] += S.amb_tunnel(L_)[:, :n] * 0.8
    tt = np.arange(n) / A.SR
    fire = A.lp(A.brown(n), 260) * (0.75 + 0.25 * np.sin(2 * math.pi * 0.9 * tt) ** 2) * 0.16
    bus.add(0, fire, 1.0)
    bus.add(0, S.sfx_crackle(L_) * 0.10, 1.0, 0.2)
    bus.add(0, S.cue_after(L_), 0.55)
    v = A.Bus(L_)
    v.add(DUR_A + LINE_AT, voice, 1.0)
    mix = bus.buf + A.add_reverb(v.buf, 0.2, 1.5, 6000)
    mix = A.master(mix)[:, :A.secs(DUR_A + DUR_B)]
    path = os.path.join(BUILD, "audio.wav")
    A.write_wav(path, mix)
    return path


def subtitle(surf, arr, text, a):
    c = surf.getCanvas()
    rgba = np.dstack([np.clip(arr, 0, 255).astype(np.uint8), np.full((H, W), 255, np.uint8)])
    c.drawImage(skia.Image.fromarray(np.ascontiguousarray(rgba)), 0, 0)
    if a > 0:
        draw_text(c, text, W / 2, H - 70, font("MPlusRounded1c-ExtraBold.ttf", 46), "#ffffff", a,
                  outline="#101018", outline_w=7)
    return surf.makeImageSnapshot().toarray()


def main():
    os.makedirs(BUILD, exist_ok=True)
    A.VOICES.update(S.VOICES)
    voice = A.synth_line("hana", LINE, os.path.join(ROOT, "build", "faultline_ep01", "voices"))
    env = A.lip_envelope(voice, FPS)
    vdur = len(voice) / A.SR
    wav = build_audio(voice)
    sa, sb = prep_a(), prep_b()
    out_dir = os.path.join(HERE, "lookdev")
    silent = os.path.join(BUILD, "video.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", silent]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    surf = P.surface()
    na, nb = int(DUR_A * FPS), int(DUR_B * FPS)
    for fi in range(na + nb):
        if fi < na:
            t = fi / FPS
            arr = frame_a(sa, t)
            fade = min(1.0, t / 0.6)
            arr = arr * fade
            frame = subtitle(surf, arr, "", 0)
        else:
            t = (fi - na) / FPS
            arr = frame_b(sb, t, env)
            a = 1.0 if LINE_AT - 0.05 <= t <= LINE_AT + vdur + 0.4 else 0.0
            arr = arr * min(1.0, (DUR_B - t) / 0.5)
            frame = subtitle(surf, arr, LINE, a)
        p.stdin.write(frame.tobytes())
        if fi % 24 == 0:
            print("frame", fi, flush=True)
    p.stdin.close()
    p.wait()
    out = os.path.join(out_dir, "look_test.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
    print("wrote", out)


if __name__ == "__main__":
    main()

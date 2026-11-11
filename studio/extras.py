"""Poster and cast sheet for Episode 1 -> episode01/poster.png, episode01/cast.png."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import skia  # noqa: E402

from backgrounds import balcony_bg, lighthouse, night_sky, railing  # noqa: E402
from characters import Expr, draw_collector, draw_genzo, draw_lumi, draw_mio  # noqa: E402
from ep01 import NIGHT, TITLE_JP  # noqa: E402
from gfx import H, W, Saved, draw_text, fill, font, glow, linear, new_surface, rgb, sparkle, vignette  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "episode01")


def poster(path):
    s = new_surface()
    c = s.getCanvas()
    t = 2.0
    balcony_bg(c, t)
    glow(c, 960, 420, 800, "#7a8aff", 0.25)
    with Saved(c, NIGHT()):
        draw_mio(c, 700, 560, 1.05, Expr(t=t, smile=0.8, look=(0.8, -0.3), blush=0.3, sway=0.4))
    draw_lumi(c, 1220, 560, 1.05, Expr(t=t, smile=0.5, look=(-0.8, -0.3), glow=0.8, blush=0.2))
    railing(c, 900)
    c.drawRect(skia.Rect.MakeLTRB(0, 0, W, 330), fill(0, shader=linear((0, 0), (0, 330),
               [rgb("#03051a", 0.85), rgb("#03051a", 0)])))
    draw_text(c, "STARFALL KEEPER", W / 2, 150, font("DelaGothicOne-Latin.ttf", 120), "#ffd25a",
              outline="#14102a", outline_w=18)
    draw_text(c, TITLE_JP, W / 2, 230, font("DelaGothicOne-JP.ttf", 50), "#e8ecff", outline="#14102a",
              outline_w=8)
    c.drawRect(skia.Rect.MakeLTRB(0, H - 200, W, H), fill(0, shader=linear((0, H - 200), (0, H),
               [rgb("#03051a", 0), rgb("#03051a", 0.9)])))
    draw_text(c, "EPISODE 1  ·  The Star in the Net", W / 2, H - 50, font("KaiseiDecol-Bold.ttf", 52),
              "#ffffff", outline="#14102a", outline_w=10)
    for i in range(12):
        a = i * 0.52
        sparkle(c, 960 + math.cos(a) * 820, 520 + math.sin(a) * 380, 12, "#fff3c0", 0.8)
    vignette(c, 0.45)
    s.makeImageSnapshot().save(path, skia.kPNG)


def cast(path):
    s = new_surface()
    c = s.getCanvas()
    t = 1.0
    night_sky(c, t, top="#0a0e30", mid="#1c2460", bottom="#4b3a78", horizon=H)
    lighthouse(c, 1820, 1160, 0.9, beam=0.6, beam_alpha=0.4)
    entries = [
        (300, "#f2a93b", "MIO", lambda: draw_mio(c, 300, 470, 0.95, Expr(t=t, smile=0.7, blush=0.3))),
        (760, "#8f8fe0", "LUMI", lambda: draw_lumi(c, 760, 470, 0.95, Expr(t=t, smile=0.4, glow=0.8))),
        (1220, "#2f4f8f", "GENZO", lambda: draw_genzo(c, 1220, 470, 0.95, Expr(t=t, smile=0.7))),
        (1640, "#6a1028", "COLLECTOR", lambda: draw_collector(c, 1640, 470, 0.72, Expr(t=t))),
    ]
    for x, col, name, fn in entries:
        glow(c, x, 470, 330, col, 0.35)
        fn()
        draw_text(c, name, x, 1010, font("DelaGothicOne-Latin.ttf", 44), "#ffffff", outline=col, outline_w=12)
    draw_text(c, "STARFALL KEEPER  ·  CAST", W / 2, 90, font("DelaGothicOne-Latin.ttf", 64), "#ffd25a",
              outline="#14102a", outline_w=12)
    s.makeImageSnapshot().save(path, skia.kPNG)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    poster(os.path.join(OUT, "poster.png"))
    cast(os.path.join(OUT, "cast.png"))
    print("ok")

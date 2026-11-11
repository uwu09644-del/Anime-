"""STARFALL KEEPER - Episode 1: "The Star in the Net".

The screenplay lives here as a list of Shots. Each shot has dialogue lines,
optional music / ambience / SFX cues and a draw function fn(c, t, d, ctx)
that paints one frame at local time t of a shot lasting d seconds.
"""
import math
from dataclasses import dataclass, field

import skia

from backgrounds import (balcony_bg, beach, clouds, cottage, crimson_sky, cliff, falling_star,
                         interior, lighthouse, moon, night_sky, railing, sea, ship_prow, table_fg)
from characters import (Expr, draw_collector, draw_figure, draw_genzo, draw_lumi, draw_mio)
from gfx import (ADD, H, W, Saved, clamp, draw_text, ease_in, ease_in_out, ease_out, fill, font,
                 glow, hash01, lerp, letterbox, linear, poly_path, radial, ramp, rgb, screen_fade,
                 smooth_path, sparkle, speed_lines, star_path, stroke, tint_paint, vignette, pulse)

TITLE = "STARFALL KEEPER"
TITLE_JP = "星降りの灯台守"
EP_TITLE = "The Star in the Net"


@dataclass
class Line:
    speaker: str
    text: str
    at: float = None      # explicit offset inside the shot (else sequential)
    gap: float = 0.35     # pause after the line
    sub: str = None       # subtitle override


@dataclass
class Shot:
    name: str
    fn: object
    lines: list = field(default_factory=list)
    pre: float = 0.5
    post: float = 0.7
    min_dur: float = 0.0
    music: str = None        # start a new cue here ("-" = silence)
    amb: dict = None         # ambience gains from here on
    sfx: list = field(default_factory=list)  # (offset, name, gain, pan)
    fade_in: float = 0.0
    fade_out: float = 0.0
    bars: float = 0.0        # letterbox


# ======================================================================
#  helpers
# ======================================================================
NIGHT = lambda: tint_paint(0.78, 0.84, 1.06)          # noqa: E731
WARM = lambda: tint_paint(1.05, 0.93, 0.82)           # noqa: E731
GLOWLIT = lambda: tint_paint(0.82, 0.9, 1.08, add=(4, 6, 14))  # noqa: E731


def blink(t, seed=0):
    period = 3.1 + hash01(seed, 3) * 2.2
    ph = (t + hash01(seed, 9) * period) % period
    if ph < 0.14:
        return math.sin(ph / 0.14 * math.pi)
    return 0.0


def shake(t, amp):
    return (math.sin(t * 47) * amp + math.sin(t * 31) * amp * 0.5,
            math.cos(t * 41) * amp + math.sin(t * 23) * amp * 0.5)


def cam(c, z, cx=W / 2, cy=H / 2):
    c.translate(W / 2, H / 2)
    c.scale(z, z)
    c.translate(-cx, -cy)


def sway(t, k=1.0):
    return math.sin(t * 1.4 * k) * 0.5 + math.sin(t * 0.63 * k) * 0.3


def sweat(c, x, y, s=1.0, a=1.0):
    p = smooth_path([(x, y - 30 * s), (x + 14 * s, y), (x, y + 12 * s), (x - 14 * s, y)])
    c.drawPath(p, fill(rgb("#bfe8ff"), a))
    c.drawPath(p, stroke(rgb("#4a7ab0"), 3, alpha=a))


def bokeh(c, t, n=18, color="#9fb6ff", seed=4):
    for i in range(n):
        x = (hash01(i, seed) * W + t * 10 * (hash01(i, 2) - 0.5)) % W
        y = (hash01(i, seed, 3) * H - t * 8 * hash01(i, 5)) % H
        r = 20 + hash01(i, 6) * 60
        c.drawCircle(x, y, r, fill(rgb(color), 0.08 + 0.08 * math.sin(t + i), blur=r * 0.3))


def speed_bg(c, t, top="#1b2050", bottom="#3a2a6a", lines="#ffffff", alpha=0.35):
    c.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=linear((0, 0), (0, H), [rgb(top), rgb(bottom)])))
    speed_lines(c, W / 2, H * 0.45, t, n=110, alpha=alpha, color=lines, r0=420)


def blanket(c, x, y, s):
    with Saved(c):
        c.translate(x, y)
        c.scale(s, s)
        p = smooth_path([(-210, 190), (-120, 160), (0, 200), (120, 160), (210, 190), (230, 560), (-230, 560)])
        c.drawPath(p, fill(rgb("#b24a3a")))
        with Saved(c):
            c.clipPath(p, doAntiAlias=True)
            for k in range(-240, 260, 60):
                c.drawLine(k, 150, k, 600, stroke(rgb("#e8c07a"), 6, alpha=0.6))
            for k in range(160, 600, 60):
                c.drawLine(-240, k, 240, k, stroke(rgb("#7a2a22"), 5, alpha=0.5))
        c.drawPath(p, stroke(rgb("#3a1a14"), 4))


def wide_scene(c, t, beam=None, py=0.0, impact=None, star_alpha=1.0, glow_cove=0.0):
    """Shared wide establishing composition (lighthouse on cliff above the sea)."""
    night_sky(c, t, pan=(t * 4, -py * 0.5), horizon=700 + py, stars=star_alpha)
    moon(c, 1500, 200 + py * 0.6, 70)
    with Saved(c):
        c.translate(0, py)
        clouds(c, t, 420, alpha=0.3)
        sea(c, t, 700, moon_x=1500)
        if glow_cove > 0:
            glow(c, 1050, 760, 260, "#cfe0ff", 0.7 * glow_cove)
        cliff(c, 120, 640, 640, t=t)
        lighthouse(c, 470, 650, 0.85, beam=t * 0.8 if beam is None else beam)
        cottage(c, 700, 650, 0.6)


# ======================================================================
#  shots
# ======================================================================
def s_open_sky(c, t, d, ctx):
    p = 1 - ease_in_out(t / (d * 0.75))
    wide_scene(c, t, py=p * 950)
    vignette(c, 0.55)


def s_balcony_mio(c, t, d, ctx):
    with Saved(c):
        cam(c, 1.0 + 0.05 * t / d, W / 2, H / 2)
        balcony_bg(c, t)
        look = (0.2, -1.0) if t < ctx.line_start(0) + 0.9 else (-1.0, -0.2)
        with Saved(c, NIGHT()):
            draw_mio(c, 820, 470, 1.3, Expr(t=t, look=look, mouth=ctx.mouth("mio"), smile=0.6,
                                             blink=blink(t, 1), sway=sway(t)))
        railing(c, 840)
    vignette(c, 0.4)


def s_genzo_door(c, t, d, ctx):
    with Saved(c):
        cam(c, 1.15, 900, 480)
        interior(c, t)
    c.drawRect(skia.Rect.MakeWH(W, H), fill(rgb("#000000"), 0.25))
    with Saved(c, WARM()):
        draw_genzo(c, 960, 480 + math.sin(t * 2) * 3, 1.3,
                   Expr(t=t, mouth=ctx.mouth("genzo"), smile=0.6, blink=blink(t, 2)))
    vignette(c, 0.45)


def s_mio_pout(c, t, d, ctx):
    with Saved(c):
        cam(c, 1.25, 960, 400)
        balcony_bg(c, t)
    after = t > ctx.line_end(0)
    with Saved(c, NIGHT()):
        draw_mio(c, 960, 520, 1.55, Expr(t=t, look=(0.0, -1.0) if after else (-0.8, 0.2),
                                         mouth=ctx.mouth("mio"), smile=0.0, brow=0.7, blush=0.5,
                                         blink=blink(t, 3), sway=sway(t)))
    vignette(c, 0.4)


def s_star_moves(c, t, d, ctx):
    with Saved(c):
        cam(c, 1.0 + 0.15 * ease_in_out(t / d), 1100, 300)
        night_sky(c, t, horizon=1200, stars=1.0)
        moon(c, 1500, 220, 64)
    sx, sy = 1100, 300
    if t < 1.8:
        s = 10 + 40 * ease_in(t / 1.8) + 8 * math.sin(t * 20)
        sparkle(c, sx, sy, s, "#ffffff", 1.0, rot=t * 0.5)
        glow(c, sx, sy, s * 4, "#cfe0ff", 0.6)
    else:
        u = (t - 1.8) / (d - 1.8)
        x = lerp(sx, -300, ease_in(u))
        y = lerp(sy, 1200, ease_in(u))
        falling_star(c, x, y, math.atan2(1200 - sy, -300 - sx), length=300 + 900 * u, width=8 + 8 * u)
    vignette(c, 0.5)


def s_mio_shock(c, t, d, ctx):
    speed_bg(c, t, "#0d1240", "#2a1f5e", alpha=0.25)
    dx, dy = shake(t, 4 if t < 0.5 else 0)
    with Saved(c, NIGHT()):
        draw_mio(c, 960 + dx, 540 + dy, 1.6, Expr(t=t, look=(0.6, -0.9), mouth=ctx.mouth("mio"), smile=0.0,
                                                  surprise=1.0, blink=0.0, sway=sway(t) + 0.6))
    # light of the passing star sweeping across her
    u = clamp(t / d)
    bx = lerp(W + 300, -600, u)
    c.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=linear((bx - 300, 0), (bx + 300, H),
               [rgb("#ffffff", 0), rgb("#dfe8ff", 0.35), rgb("#ffffff", 0)]), blend=ADD))
    vignette(c, 0.4)


def s_impact_wide(c, t, d, ctx):
    hit = 1.0
    dx, dy = shake(t, 10 * pulse(t, hit, hit + 0.6, 0.4))
    with Saved(c):
        c.translate(dx, dy)
        wide_scene(c, t, glow_cove=ramp(t, hit, hit + 0.3) * (0.7 + 0.3 * math.sin(t * 5)))
        if t < hit:
            u = t / hit
            x, y = lerp(2000, 1050, ease_in(u)), lerp(-150, 760, ease_in(u))
            falling_star(c, x, y, math.atan2(760 + 150, 1050 - 2000), length=500, width=12)
        else:
            u = t - hit
            # splash column
            hgt = 420 * math.sin(min(u / 1.6, 1) * math.pi)
            if hgt > 2:
                col = smooth_path([(1050 - 60, 760), (1050 - 25, 760 - hgt), (1050, 760 - hgt * 1.08),
                                   (1050 + 25, 760 - hgt), (1050 + 60, 760)])
                c.drawPath(col, fill(rgb("#dfe8ff"), 0.85))
                for i in range(14):
                    a = -math.pi / 2 + (hash01(i, 1) - 0.5) * 1.6
                    r = u * (300 + 200 * hash01(i, 2))
                    yy = 760 - hgt * 0.6 + math.sin(a) * r * -0.6 + 300 * u * u
                    c.drawCircle(1050 + math.cos(a) * r, yy, 6 + 6 * hash01(i, 3), fill(rgb("#e8f0ff"), 0.8))
            # shockwave ring on the water
            rr = u * 700
            c.drawOval(skia.Rect.MakeXYWH(1050 - rr, 760 - rr * 0.12, rr * 2, rr * 0.24),
                       stroke(rgb("#dfe8ff"), 6, alpha=clamp(1 - u / 1.8)))
    screen_fade(c, clamp(1 - (t - hit) / 0.6) if t >= hit else 0, "#ffffff")
    vignette(c, 0.5)
    letterbox(c, 1.0)


def s_mio_fell(c, t, d, ctx):
    with Saved(c):
        cam(c, 1.3, 960, 600)
        balcony_bg(c, t)
    glow(c, 1300, 1150, 900, "#bcd2ff", 0.35)
    run = ease_in(clamp((t - (d - 0.7)) / 0.7))
    with Saved(c, NIGHT()):
        draw_mio(c, 960 - run * 1600, 520, 1.5, Expr(t=t, look=(0.7, 0.9), mouth=ctx.mouth("mio"), smile=0.1,
                                                     brow=-0.4, blink=blink(t, 4), sway=sway(t) + run * 2))
    if run > 0:
        for i in range(12):
            y = 200 + i * 60
            c.drawLine(960 - run * 1600 + 300, y, 960 - run * 1600 + 300 + 400 * run, y,
                       stroke(rgb("#ffffff"), 4, alpha=0.4))
    vignette(c, 0.4)


# ---------------------------------------------------------------- OP
OP_BAR = 1.6


def name_card(c, t, color, name, sub, draw_fn, side=1):
    u = ease_out(clamp(t / 0.35))
    # diagonal panel
    with Saved(c):
        off = (1 - u) * 1400 * side
        c.translate(off, 0)
        p = poly_path([(-200, 0), (1350, 0), (950, H), (-200, H)]) if side > 0 else \
            poly_path([(570, 0), (W + 200, 0), (W + 200, H), (970, H)])
        c.drawPath(p, fill(rgb(color)))
        for i in range(8):
            yy = (i * 160 + t * 300) % (H + 200) - 100
            c.drawLine(-200, yy, W + 200, yy - 300, stroke(rgb("#ffffff"), 18, alpha=0.08))
        draw_fn(c, t)
    a = ramp(t, 0.25, 0.5)
    x = 1500 if side > 0 else 420
    size = 92
    while size > 40 and font("DelaGothicOne-Latin.ttf", size).measureText(name) > 760:
        size -= 4
    draw_text(c, name, x, 520, font("DelaGothicOne-Latin.ttf", size), "#ffffff", a, outline="#14102a",
              outline_w=12)
    draw_text(c, sub, x, 600, font("MPlusRounded1c-ExtraBold.ttf", 40), "#ffffff", a, outline="#14102a",
              outline_w=8)


def s_title(c, t, d, ctx):
    b = t / OP_BAR
    if b < 2:
        with Saved(c):
            cam(c, 1.0 + 0.1 * b, W / 2, H / 2)
            night_sky(c, t, horizon=1200)
        u = clamp((t - 0.3) / 2.6)
        falling_star(c, lerp(-200, W + 300, u), lerp(100, 800, u), math.atan2(700, W + 500), 700, 1.0, 12)
        draw_text(c, "~ OPENING ~", W / 2, H / 2 + 20, font("KaiseiDecol-Bold.ttf", 54), "#e8ecff",
                  ramp(t, 0.6, 1.2) * (1 - ramp(t, 2.6, 3.1)))
    elif b < 6:
        night_sky(c, t, horizon=1200, stars=0.6)
        k = int(b - 2)
        lt = t - (2 + k) * OP_BAR
        if k == 0:
            name_card(c, lt, "#f2a93b", "MIO", "the lighthouse keeper's granddaughter",
                      lambda cc, tt: draw_mio(cc, 520, 520, 1.45, Expr(t=t, smile=0.9, mouth=0.35, blink=0,
                                                                        sway=0.5)), 1)
        elif k == 1:
            name_card(c, lt, "#8f8fe0", "LUMI", "a star who fell from the sky",
                      lambda cc, tt: draw_lumi(cc, 1400, 540, 1.4, Expr(t=t, smile=0.4, glow=1.0)), -1)
        elif k == 2:
            name_card(c, lt, "#2f4f8f", "GRANDPA GENZO", "keeper of the Kasumi light",
                      lambda cc, tt: draw_genzo(cc, 520, 520, 1.4, Expr(t=t, smile=0.7)), 1)
        else:
            name_card(c, lt, "#6a1028", "???", "the Collector",
                      lambda cc, tt: draw_collector(cc, 1380, 560, 1.15, Expr(t=t)), -1)
        flash = clamp(1 - (t - (2 + k) * OP_BAR) / 0.15)
        screen_fade(c, flash * 0.7, "#ffffff")
    elif b < 8:
        # build-up: the lighthouse turns its beam to the sky, stars converge
        u = (t - 6 * OP_BAR) / (2 * OP_BAR)
        with Saved(c):
            cam(c, 1.0 + 0.25 * ease_in(u), 470, 300)
            wide_scene(c, t, beam=math.pi * 0.5 + u * 3.0)
        for i in range(30):
            a = hash01(i, 2) * math.tau
            r = (1 - ease_in(u)) * (500 + 400 * hash01(i, 3))
            sparkle(c, W / 2 + math.cos(a) * r, H / 2 + math.sin(a) * r, 10, "#ffffff", 0.8)
        screen_fade(c, ease_in(clamp((u - 0.8) / 0.2)), "#ffffff")
    else:
        lt = t - 8 * OP_BAR
        night_sky(c, t, top="#04061a", mid="#141a4a", bottom="#3a2a6a", horizon=1100)
        # lighthouse silhouette + beam at the bottom
        lighthouse(c, 1650, 1150, 1.0, beam=t * 0.9, lit=1.0, beam_alpha=0.6)
        rise = ease_out(clamp(lt / 0.5))
        y0 = 440 - 40 * ease_in_out(clamp((lt - 2.0) / 1.0))
        sc = 1.25 - 0.25 * rise
        glow(c, W / 2, y0 - 40, 700, "#7a8aff", 0.35 * rise)
        with Saved(c):
            c.translate(W / 2, y0)
            c.scale(sc, sc)
            draw_text(c, "STARFALL", 0, -40, font("DelaGothicOne-Latin.ttf", 170), "#fff6d6", rise,
                      outline="#1a1240", outline_w=22)
            draw_text(c, "KEEPER", 0, 130, font("DelaGothicOne-Latin.ttf", 170), "#ffd25a", rise,
                      outline="#1a1240", outline_w=22)
        draw_text(c, TITLE_JP, W / 2, y0 + 250, font("DelaGothicOne-JP.ttf", 64), "#e8ecff",
                  ramp(lt, 0.4, 0.9), outline="#1a1240", outline_w=10)
        for i in range(16):
            a = t * 0.8 + i * 0.4
            sparkle(c, W / 2 + math.cos(a) * (560 + 40 * math.sin(t + i)), y0 + math.sin(a) * 220,
                    8 + 8 * hash01(i, 1), "#fff3c0", 0.5 + 0.5 * math.sin(t * 3 + i))
        ep_a = ramp(lt, 2.2, 2.8)
        draw_text(c, "EPISODE 1", W / 2, y0 + 360, font("MPlusRounded1c-ExtraBold.ttf", 44), "#ffd25a", ep_a,
                  outline="#1a1240", outline_w=8)
        draw_text(c, EP_TITLE, W / 2, y0 + 430, font("KaiseiDecol-Bold.ttf", 64), "#ffffff", ep_a,
                  outline="#1a1240", outline_w=10)
        screen_fade(c, clamp(1 - lt / 0.5), "#ffffff")
        screen_fade(c, ramp(t, d - 0.9, d), "#000000")


# ---------------------------------------------------------------- beach
def beach_sky(c, t):
    night_sky(c, t, horizon=430, bottom="#3a3a7a", seed=2)
    moon(c, 300, 160, 56)


def s_beach_run(c, t, d, ctx):
    x = lerp(-150, 820, t / d)
    with Saved(c):
        cam(c, 1.0, 960 + (x - 700) * 0.15, 540)
        beach_sky(c, t)
        beach(c, t, glow_amt=0.18 + 0.08 * math.sin(t * 2))
        with Saved(c, NIGHT()):
            draw_figure(c, "mio", x, 920, 380, Expr(t=t, mouth=ctx.mouth("mio"), smile=0.0, brow=0.4,
                                                     blink=blink(t, 5), sway=0.8),
                        walk=t * 1.6, holding_lantern=True)
    vignette(c, 0.5)


def s_net_glow(c, t, d, ctx):
    g = 0.45 + 0.25 * math.sin(t * 2.4)
    with Saved(c):
        cam(c, 1.05 + 0.08 * t / d, 1000, 700)
        beach_sky(c, t)
        beach(c, t, glow_amt=g)
        with Saved(c, NIGHT()):
            draw_figure(c, "mio", 820, 920, 380, Expr(t=t, mouth=ctx.mouth("mio"), smile=0.0, surprise=0.6,
                                                       look=(1, 0.4), blink=blink(t, 6)), holding_lantern=True)
    vignette(c, 0.5)


def s_mio_warm(c, t, d, ctx):
    c.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=linear((0, 0), (0, H), [rgb("#0a0d2a"), rgb("#2a3470")])))
    bokeh(c, t, color="#cfe0ff")
    with Saved(c, GLOWLIT()):
        draw_mio(c, 960, 500, 1.6, Expr(t=t, mouth=ctx.mouth("mio"), smile=0.2, surprise=0.4, look=(0.2, 0.9),
                                        blink=blink(t, 7), blush=0.3, sway=sway(t)))
    c.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=linear((0, H), (0, H * 0.45),
               [rgb("#bcd0ff", 0.28), rgb("#bcd0ff", 0)]), blend=ADD))
    vignette(c, 0.5)


def s_lumi_rise(c, t, d, ctx):
    with Saved(c):
        cam(c, 1.0 + 0.06 * t / d, 960, 540)
        beach_sky(c, t)
        beach(c, t, glow_amt=1.0, glow_x=960, glow_y=860)
    c.drawRect(skia.Rect.MakeWH(W, H), fill(rgb("#000020"), 0.35))
    # light column
    bw = 260 + 40 * math.sin(t * 3)
    c.drawRect(skia.Rect.MakeLTRB(960 - bw, 0, 960 + bw, 900), fill(0, shader=linear(
        (960 - bw, 0), (960 + bw, 0), [rgb("#cfe0ff", 0), rgb("#eaf0ff", 0.55), rgb("#cfe0ff", 0)]), blend=ADD))
    rise = ease_out(clamp(t / 4.0))
    y = lerp(1400, 520, rise)
    eye_open = ramp(t, d - 1.6, d - 1.3)
    draw_lumi(c, 960, y, 1.3, Expr(t=t, glow=1.0, blink=1 - eye_open, smile=0.1, look=(0, 0.2)))
    for i in range(40):
        px = 960 + (hash01(i, 1) - 0.5) * 900
        py = (900 - ((t * (80 + 120 * hash01(i, 2)) + hash01(i, 3) * 900) % 900))
        sparkle(c, px, py, 4 + 6 * hash01(i, 4), "#ffffff", 0.7)
    if eye_open > 0:
        sparkle(c, 960 - 56 * 1.3, y + 10, 40 * pulse(t, d - 1.3, d - 1.0, 0.2), "#ffffff", 1.0)
    screen_fade(c, clamp(1 - t / 0.4), "#ffffff")
    vignette(c, 0.55)


def lumi_closeup(c, t, ctx, ex_kw, bg="beach", scale=1.5, y=530, glow_amt=1.0, blanket_on=False):
    if bg == "beach":
        c.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=linear((0, 0), (0, H), [rgb("#070a26"), rgb("#1c2460")])))
        bokeh(c, t, color="#cfe0ff")
    else:
        with Saved(c):
            cam(c, 1.4, 1300, 420)
            interior(c, t)
        c.drawRect(skia.Rect.MakeWH(W, H), fill(rgb("#000000"), 0.3))
    ex = Expr(t=t, glow=glow_amt, mouth=ctx.mouth("lumi"), blink=blink(t, 11), **ex_kw)
    if bg == "interior":
        with Saved(c, WARM()):
            draw_lumi(c, 960, y, scale, ex)
            if blanket_on:
                blanket(c, 960, y, scale)
    else:
        draw_lumi(c, 960, y, scale, ex)
    vignette(c, 0.45)


def s_lumi_speaks(c, t, d, ctx):
    lumi_closeup(c, t, ctx, dict(smile=0.15, look=(0.1, -0.4)))


def s_mio_fluster(c, t, d, ctx):
    c.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=linear((0, 0), (0, H), [rgb("#0e1235"), rgb("#2a2a62")])))
    bokeh(c, t, color="#ffcf8a", seed=9)
    bob = math.sin(t * 9) * 4 if t < 2.5 else 0
    with Saved(c, NIGHT()):
        draw_mio(c, 960, 520 + bob, 1.55, Expr(t=t, mouth=ctx.mouth("mio"), smile=0.3, brow=0.8, blush=0.9,
                                               look=(0.3, 0), blink=blink(t, 12), sway=sway(t) + bob * 0.05))
    sweat(c, 1180, 300, 1.4, 0.9)
    glow(c, 1500, 1100, 700, "#ffb050", 0.3)
    vignette(c, 0.45)


def s_lumi_everything(c, t, d, ctx):
    g = lerp(1.0, 0.45, ramp(t, 1.0, d))
    lumi_closeup(c, t, ctx, dict(smile=0.25, sad=0.5, look=(-0.2, 0.5)), glow_amt=g)


def s_lumi_collapse(c, t, d, ctx):
    fall = ease_in_out(clamp((t - 0.3) / 1.6))
    zoom = lerp(1.15, 1.0, ease_in_out(clamp((t - 2.2) / (d - 2.2))))
    dx, dy = shake(t, 6 * pulse(t, ctx.line_start(1), ctx.line_end(1), 0.2))
    with Saved(c):
        c.translate(dx, dy)
        cam(c, zoom, 960, 640)
        beach_sky(c, t)
        beach(c, t, glow_amt=lerp(0.9, 0.2, fall), glow_x=1150, glow_y=880)
        mx = lerp(500, 1000, ease_out(clamp((t - 0.6) / 1.4)))
        with Saved(c, NIGHT()):
            draw_figure(c, "mio", mx, 930, 380, Expr(t=t, mouth=ctx.mouth("mio"), brow=0.8, surprise=0.5,
                                                      blink=0, look=(1, 0)),
                        walk=t * 1.8 if t < 2.0 else 0, holding_lantern=True, arm_up=0.0)
        with Saved(c):
            ly = lerp(820, 930, fall)
            c.rotate(fall * 70, 1150, ly)
            glow(c, 1150, ly - 200, 380, "#cfe0ff", lerp(0.9, 0.3, fall))
            draw_figure(c, "lumi", 1150, ly, 370, Expr(t=t, blink=lerp(0, 1, fall), glow=0.3))
    vignette(c, 0.5)
    screen_fade(c, ramp(t, d - 1.0, d), "#000000")


# ---------------------------------------------------------------- interior
def s_interior_two(c, t, d, ctx):
    lightning = pulse(t, 0.4, 0.5, 0.15)
    with Saved(c):
        cam(c, 1.0 + 0.03 * t / d, 960, 540)
        interior(c, t, lightning=lightning)
        with Saved(c, WARM()):
            draw_genzo(c, 520, 470, 1.15, Expr(t=t, mouth=ctx.mouth("genzo"), smile=0.2, brow=0.3,
                                               blink=blink(t, 13)))
            draw_lumi(c, 1350, 520, 1.0, Expr(t=t, glow=0.5, smile=0.0, look=(-0.6, 0.4), blink=blink(t, 14)))
            blanket(c, 1350, 520, 1.0)
        table_fg(c)
    vignette(c, 0.45)
    screen_fade(c, clamp(1 - t / 0.8), "#000000")


def mio_interior(c, t, ctx, ex_kw, zoom_from=1.0):
    with Saved(c):
        cam(c, 1.4, 700, 380)
        interior(c, t)
    c.drawRect(skia.Rect.MakeWH(W, H), fill(rgb("#000000"), 0.3))
    with Saved(c, WARM()):
        draw_mio(c, 960, 520, 1.5, Expr(t=t, mouth=ctx.mouth("mio"), blink=blink(t, 15), sway=sway(t, 0.4),
                                        **ex_kw))
    vignette(c, 0.45)


def s_mio_stories(c, t, d, ctx):
    mio_interior(c, t, ctx, dict(smile=0.3, brow=0.3, look=(-0.7, 0.1)))


def genzo_close(c, t, ctx, ex_kw, push=0.05):
    with Saved(c):
        cam(c, 1.3, 520, 400)
        interior(c, t)
    c.drawRect(skia.Rect.MakeWH(W, H), fill(rgb("#000000"), 0.3))
    with Saved(c):
        cam(c, 1.0 + push * t / 6, 960, 540)
        with Saved(c, WARM()):
            draw_genzo(c, 960, 500, 1.45, Expr(t=t, mouth=ctx.mouth("genzo"), blink=blink(t, 16), **ex_kw))
    glow(c, 1500, 0, 900, "#ffb056", 0.25)
    vignette(c, 0.5)


def s_genzo_starfolk(c, t, d, ctx):
    genzo_close(c, t, ctx, dict(smile=0.0, brow=0.3), push=0.25)


def s_lumi_heard(c, t, d, ctx):
    lumi_closeup(c, t, ctx, dict(smile=0.3, look=(0, 0.6 if t < 2 else -0.3)), bg="interior", glow_amt=0.6,
                 blanket_on=True)


def s_mio_determined(c, t, d, ctx):
    c.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=linear((0, 0), (W, H), [rgb("#ff8a5a"), rgb("#ffcf6a")])))
    speed_lines(c, 960, 480, t, n=80, alpha=0.25, color="#ffffff", r0=500)
    for i in range(14):
        sparkle(c, hash01(i, 1) * W, hash01(i, 2) * H, 10 + 14 * hash01(i, 3), "#ffffff",
                0.5 + 0.5 * math.sin(t * 4 + i))
    look = (0.0, 0.0) if t < ctx.line_start(0) + 1.6 else (1.0, 0.1)
    draw_mio(c, 960, 520, 1.55, Expr(t=t, mouth=ctx.mouth("mio"), smile=0.9, brow=-0.6, look=look,
                                     blink=blink(t, 17), sway=sway(t) + 0.4))


def s_genzo_hesitant(c, t, d, ctx):
    genzo_close(c, t, ctx, dict(smile=0.0, brow=0.8), push=0.1)


def s_lumi_stone(c, t, d, ctx):
    flick = 0.55 + 0.25 * math.sin(t * 9) * math.sin(t * 2.3)
    if hash01(int(t * 8), 3) < 0.15:
        flick = 0.15
    lumi_closeup(c, t, ctx, dict(smile=0.0, sad=0.8, look=(0, 0.7)), bg="interior", glow_amt=flick,
                 blanket_on=True)


def s_mio_stone(c, t, d, ctx):
    flash = pulse(t, 0.25, 0.35, 0.12)
    speed_bg(c, t, "#0a0a20", "#2a1a40", alpha=0.3)
    dx, dy = shake(t, 8 * pulse(t, 0.2, 0.9, 0.2))
    draw_mio(c, 960 + dx, 520 + dy, 1.65, Expr(t=t, mouth=ctx.mouth("mio"), smile=0.0, surprise=1.0,
                                               brow=0.6, blink=0, sway=0.8))
    screen_fade(c, flash * 0.85, "#e8ecff")


# ---------------------------------------------------------------- balcony (later)
def s_balcony_two(c, t, d, ctx):
    with Saved(c):
        cam(c, 1.0 + 0.04 * t / d, 960, 500)
        balcony_bg(c, t)
        who = ctx.current_speaker()
        lm = (0.9, -0.1) if who == "mio" else (0.2, -1.0)
        ll = (-0.9, -0.1) if who in ("mio",) or t > ctx.line_end(2) else (0.1, -0.9)
        if who == "lumi":
            ll, lm = (-0.2, -0.8), (0.9, 0.0)
        with Saved(c, NIGHT()):
            draw_mio(c, 600, 500, 1.0, Expr(t=t, mouth=ctx.mouth("mio"), smile=0.55, look=lm,
                                            blink=blink(t, 18), sway=sway(t)))
        draw_lumi(c, 1320, 500, 1.0, Expr(t=t, mouth=ctx.mouth("lumi"), smile=0.35, look=ll, glow=0.6,
                                          blink=blink(t, 19)))
        railing(c, 860)
    vignette(c, 0.45)
    screen_fade(c, clamp(1 - t / 1.0), "#000000")


def hand(c, x, y, s, side, sleeve, skin, line, glow_amt=0.0):
    with Saved(c):
        c.translate(x, y)
        c.scale(s * side, s)
        c.drawRect(skia.Rect.MakeLTRB(-1200, -70, -120, 70), fill(rgb(sleeve)))
        c.drawRect(skia.Rect.MakeLTRB(-1200, -70, -120, 70), stroke(rgb(line), 5))
        c.drawRoundRect(skia.Rect.MakeLTRB(-150, -78, -100, 78), 14, 14, fill(rgb(sleeve)))
        c.drawRoundRect(skia.Rect.MakeLTRB(-150, -78, -100, 78), 14, 14, stroke(rgb(line), 5))
        palm = smooth_path([(-110, -50), (-20, -56), (30, -30), (30, 30), (-20, 50), (-110, 44)])
        c.drawPath(palm, fill(rgb(skin)))
        c.drawPath(palm, stroke(rgb(line), 5))
        for i, (fy, ln) in enumerate(((-36, 110), (-12, 128), (12, 120), (34, 96))):
            r = skia.Rect.MakeLTRB(10, fy - 11, 10 + ln, fy + 11)
            c.drawRoundRect(r, 11, 11, fill(rgb(skin)))
            c.drawRoundRect(r, 11, 11, stroke(rgb(line), 4))
        if glow_amt > 0:
            glow(c, 60, 0, 260, "#dfe8ff", glow_amt)


def s_hands(c, t, d, ctx):
    c.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=linear((0, 0), (0, H), [rgb("#050820"), rgb("#1a1f55")])))
    night_sky(c, t, top="#050820", mid="#0f1440", bottom="#1a1f55", horizon=H, stars=0.6)
    u = ease_out(clamp(t / 1.6))
    gap = lerp(500, 128, u)
    touch = ramp(t, 1.5, 1.8)
    with Saved(c, NIGHT()):
        hand(c, 960 - gap, 560, 1.2, 1, "#f6c445", "#fde4d6", "#2b1d2e")
    hand(c, 960 + gap, 540, 1.2, -1, "#f6f4ff", "#fff1ec", "#6b6fa8", glow_amt=0.6)
    if touch > 0:
        glow(c, 960, 550, 600 * touch, "#fff3c8", 0.8 * touch)
        for i in range(24):
            a = i / 24 * math.tau + t
            r = 120 + (t - 1.5) * 260
            sparkle(c, 960 + math.cos(a) * r, 550 + math.sin(a) * r * 0.7, 10, "#fff7d6",
                    clamp(1 - (t - 1.5) / 2.2))
    vignette(c, 0.5)


def s_lumi_wish(c, t, d, ctx):
    c.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=linear((0, 0), (0, H), [rgb("#0a0e30"), rgb("#2a2a6a")])))
    bokeh(c, t, color="#ffe6a8", seed=12)
    draw_lumi(c, 960, 530, 1.5, Expr(t=t, mouth=ctx.mouth("lumi"), smile=0.6, blush=0.6,
                                     tear=clamp(t / (d * 0.8)), glow=0.8, blink=blink(t, 20), look=(-0.2, 0)))
    vignette(c, 0.45)


def s_mio_promise(c, t, d, ctx):
    with Saved(c):
        cam(c, 1.3, 1200, 380)
        balcony_bg(c, t)
    bokeh(c, t, color="#ffe6a8", seed=13)
    with Saved(c, NIGHT()):
        draw_mio(c, 960, 520, 1.55, Expr(t=t, mouth=ctx.mouth("mio"), smile=1.0, blush=0.45,
                                         happy_eyes=1.0 if t > 0.5 else 0.0, blink=blink(t, 21), sway=sway(t)))
    vignette(c, 0.45)


def s_lighthouse_night(c, t, d, ctx):
    z = lerp(1.6, 1.0, ease_in_out(t / d))
    with Saved(c):
        cam(c, z, 470, 330)
        wide_scene(c, t)
        # the two girls on the gallery
        glow(c, 445, 289, 30, "#ffd25a", 0.9)
        glow(c, 495, 289, 34, "#dfe8ff", 1.0)
        sparkle(c, 495, 284, 10, "#ffffff", 0.6 + 0.4 * math.sin(t * 3))
    vignette(c, 0.5)
    letterbox(c, 1.0)
    screen_fade(c, ramp(t, d - 1.2, d), "#000000")


# ---------------------------------------------------------------- villain
def s_collector(c, t, d, ctx):
    flare = ramp(t, d - 1.4, d - 0.9)
    flash = pulse(t, 2.0, 2.1, 0.2)
    with Saved(c):
        cam(c, 1.0 + 0.12 * t / d, 960, 420)
        crimson_sky(c, t, flash=flash)
        ship_prow(c, t)
        draw_collector(c, 960, 520, 1.0, Expr(t=t))
        if flare > 0:
            for s in (-1, 1):
                glow(c, 960 + s * 26, 516, 200 * flare, "#ff3050", flare)
                sparkle(c, 960 + s * 26, 516, 60 * flare, "#ffd0d6", flare)
    vignette(c, 0.6)
    letterbox(c, 1.0)
    screen_fade(c, clamp(1 - t / 0.3), "#000000")
    if t > d - 0.5:
        screen_fade(c, 1.0, "#000000")


# ---------------------------------------------------------------- ED + preview
CREDITS = [
    ("big", "STARFALL KEEPER"),
    ("small", "Episode 1  -  The Star in the Net"),
    ("gap", ""),
    ("head", "CAST"),
    ("row", "Mio Tsukishima  ....  Kokoro voice 'af_heart'"),
    ("row", "Lumi  ....  Kokoro voice 'af_nicole'"),
    ("row", "Grandpa Genzo  ....  Kokoro voice 'bm_george'"),
    ("row", "The Collector  ....  Kokoro voice 'bm_lewis'"),
    ("gap", ""),
    ("head", "STORY  /  SCRIPT"),
    ("row", "Claude"),
    ("head", "CHARACTER DESIGN  /  ANIMATION"),
    ("row", "Every frame drawn in Python code with Skia"),
    ("head", "MUSIC  /  SOUND"),
    ("row", "Synthesized from scratch with NumPy + SciPy"),
    ("head", "VOICES"),
    ("row", "Kokoro-82M text-to-speech (Apache-2.0)"),
    ("head", "FONTS (SIL OFL)"),
    ("row", "Dela Gothic One  /  M PLUS Rounded 1c  /  Kaisei Decol"),
    ("head", "TOOLS"),
    ("row", "skia-python  /  NumPy  /  SciPy  /  FFmpeg"),
    ("gap", ""),
    ("head", "THANK YOU FOR WATCHING"),
]


def s_ed(c, t, d, ctx):
    night_sky(c, t, top="#03051a", mid="#0f1440", bottom="#2a2060", horizon=H)
    lighthouse(c, 330, 1180, 0.9, beam=t * 0.6, beam_alpha=0.5)
    # ED illustration: the girls side by side, eyes closed, at peace
    with Saved(c):
        c.translate(0, math.sin(t * 0.6) * 6)
        glow(c, 520, 520, 520, "#7a8aff", 0.25)
        with Saved(c, NIGHT()):
            draw_mio(c, 400, 560, 0.8, Expr(t=t, smile=0.7, happy_eyes=1.0, blush=0.3, sway=sway(t, 0.5)))
        draw_lumi(c, 680, 560, 0.8, Expr(t=t, smile=0.6, happy_eyes=1.0, blush=0.3, glow=0.6))
    if hash01(int(t / 3), 5) < 0.6:
        u = (t % 3) / 1.2
        if u < 1:
            x0 = 1100 + hash01(int(t / 3), 6) * 700
            falling_star(c, x0 - u * 500, 80 + u * 300, math.atan2(300, -500), 260, 1 - u, 5)
    # scrolling credits on the right
    total_h = 0
    items = []
    for kind, txt in CREDITS:
        h = {"big": 110, "small": 70, "head": 80, "row": 58, "gap": 70}[kind]
        items.append((kind, txt, total_h))
        total_h += h
    scroll = lerp(H + 40, -total_h + 380, clamp(t / (d - 4)))
    x = 1380
    for kind, txt, yy in items:
        y = scroll + yy
        if -80 < y < H + 80:
            a = clamp(min(y / 160, (H - y) / 160))
            if kind == "big":
                draw_text(c, txt, x, y, font("DelaGothicOne-Latin.ttf", 72), "#ffd25a", a, outline="#14102a",
                          outline_w=10)
            elif kind == "small":
                draw_text(c, txt, x, y, font("KaiseiDecol-Bold.ttf", 40), "#ffffff", a)
            elif kind == "head":
                draw_text(c, txt, x, y, font("MPlusRounded1c-ExtraBold.ttf", 36), "#9fb6ff", a)
            elif kind == "row":
                draw_text(c, txt, x, y, font("MPlusRounded1c-Bold.ttf", 34), "#ffffff", a)
    screen_fade(c, clamp(1 - t / 1.0), "#000000")
    screen_fade(c, ramp(t, d - 1.2, d), "#000000")


def s_preview(c, t, d, ctx):
    c.drawRect(skia.Rect.MakeWH(W, H), fill(0, shader=linear((0, 0), (W, H), [rgb("#1a2a6a"), rgb("#5a2a8a")])))
    for i in range(10):
        x = (i * 260 + t * 120) % (W + 600) - 300
        c.drawPath(poly_path([(x, 0), (x + 120, 0), (x - 380, H), (x - 500, H)]), fill(rgb("#ffffff"), 0.05))
    # a lighthouse beam pointing UP at the sky (the episode-2 idea)
    with Saved(c):
        lighthouse(c, 1500, 1160, 1.1, beam=math.pi / 2, lit=1.0, beam_alpha=0.0)
        bw = 120 + 20 * math.sin(t * 3)
        c.drawPath(poly_path([(1500 - 20, 1160 - 490), (1500 + 20, 1160 - 490), (1500 + bw * 3, -50),
                              (1500 - bw * 3, -50)]),
                   fill(0, shader=linear((0, 700), (0, 0), [rgb("#fff3c0", 0.7), rgb("#fff3c0", 0)]), blend=ADD))
    draw_mio(c, 520, 560, 1.25, Expr(t=t, mouth=ctx.mouth("mio"), smile=0.9, brow=-0.3, blink=blink(t, 22),
                                     sway=sway(t)))
    a = ramp(t, 0.2, 0.6)
    draw_text(c, "NEXT EPISODE", 1300, 200, font("DelaGothicOne-Latin.ttf", 96), "#ffd25a", a,
              outline="#14102a", outline_w=14)
    draw_text(c, "EPISODE 2", 1300, 330, font("MPlusRounded1c-ExtraBold.ttf", 48), "#ffffff", a,
              outline="#14102a", outline_w=8)
    draw_text(c, "The Lighthouse That", 1300, 420, font("KaiseiDecol-Bold.ttf", 66), "#ffffff", a,
              outline="#14102a", outline_w=10)
    draw_text(c, "Faces the Sky", 1300, 500, font("KaiseiDecol-Bold.ttf", 66), "#ffffff", a,
              outline="#14102a", outline_w=10)
    screen_fade(c, clamp(1 - t / 0.3), "#ffffff")


def s_end(c, t, d, ctx):
    c.clear(rgb("#000000"))
    a = ramp(t, 0.3, 1.0) * (1 - ramp(t, d - 0.8, d))
    draw_text(c, "To be continued...", W / 2, H / 2, font("KaiseiDecol-Bold.ttf", 80), "#ffffff", a)
    draw_text(c, TITLE + "  ·  " + TITLE_JP, W / 2, H / 2 + 90, font("MPlusRounded1c-JP-Bold.ttf", 36),
              "#9fb6ff", a)
    sparkle(c, W / 2 + 340, H / 2 - 50, 16, "#fff3c0", a * (0.6 + 0.4 * math.sin(t * 4)))


# ======================================================================
#  THE SCREENPLAY
# ======================================================================
SHOTS = [
    # --- COLD OPEN --------------------------------------------------------
    Shot("open_sky", s_open_sky, [
        Line("mio", "On Kasumi Island, the old fishermen say that every falling star is a wish somebody gave up on."),
        Line("mio", "I never believed them. Not until the night one fell into my net.", gap=0.6),
    ], pre=2.5, post=1.2, music="night", amb={"waves": 0.7, "wind": 0.35}, fade_in=2.0, bars=1.0),
    Shot("balcony_mio", s_balcony_mio, [
        Line("mio", "Grandpa! The stars are so bright tonight. Do you think they ever get lonely up there?"),
    ], pre=0.8, post=0.6),
    Shot("genzo_door", s_genzo_door, [
        Line("genzo", "Lonely? Ha! They've got each other. Now come inside, Mio. There's a storm coming in from the east."),
    ], pre=0.4, post=0.5, amb={"waves": 0.35, "wind": 0.2}),
    Shot("mio_pout", s_mio_pout, [
        Line("mio", "Just one more minute..."),
    ], pre=0.3, post=1.4, amb={"waves": 0.7, "wind": 0.35}),
    Shot("star_moves", s_star_moves, [], min_dur=3.6, music="sting",
         sfx=[(0.1, "sparkle", 0.6, 0.3), (1.7, "whoosh", 0.8, -0.3)]),
    Shot("mio_shock", s_mio_shock, [
        Line("mio", "Huh? That star... It's moving!"),
    ], pre=0.2, post=0.4),
    Shot("impact_wide", s_impact_wide, [], min_dur=3.8,
         sfx=[(0.0, "whoosh_down", 0.8, 0.4), (1.0, "boom", 0.9, 0.0), (1.05, "splash", 0.6, 0.1)]),
    Shot("mio_fell", s_mio_fell, [
        Line("mio", "It fell... It fell right into the cove!"),
    ], pre=0.3, post=1.0, sfx=[(-0.8, "whoosh_down", 0.5, -0.6)]),
    # --- OPENING ----------------------------------------------------------
    Shot("title", s_title, [], min_dur=OP_BAR * 10 + 1.4, music="op", amb={"waves": 0.0, "wind": 0.0},
         sfx=[(OP_BAR * 8, "hit", 0.8, 0.0)]),
    # --- PART A: THE BEACH ------------------------------------------------
    Shot("beach_run", s_beach_run, [
        Line("mio", "Hah... hah... It should be right around here...", sub="Haah... haah... It should be right around here..."),
    ], pre=1.0, post=0.6, music="mystery", amb={"waves": 1.0, "wind": 0.25}, fade_in=0.6,
         sfx=[(0.0, "steps", 1.0, 0.0)]),
    Shot("net_glow", s_net_glow, [
        Line("mio", "Grandpa's old fishing net... Is it glowing?"),
    ], pre=0.6, post=0.8),
    Shot("mio_warm", s_mio_warm, [
        Line("mio", "It's... warm."),
    ], pre=0.5, post=0.7),
    Shot("lumi_rise", s_lumi_rise, [], min_dur=6.4, music="reveal",
         sfx=[(0.0, "shimmer", 0.8, 0.0), (6.4 - 1.35, "ting", 0.7, 0.0)]),
    Shot("lumi_speaks", s_lumi_speaks, [
        Line("lumi", "Is this... the bottom of the sky?"),
    ], pre=0.6, post=0.8),
    Shot("mio_fluster", s_mio_fluster, [
        Line("mio", "The bottom of the... what? This is Kasumi Beach! Are you okay? Did you fall off a boat?"),
    ], pre=0.2, post=0.5),
    Shot("lumi_everything", s_lumi_everything, [
        Line("lumi", "A boat? No... I fell off of everything."),
    ], pre=0.6, post=1.0),
    Shot("lumi_collapse", s_lumi_collapse, [
        Line("mio", "Hey! Hey, hang on!", at=0.9),
        Line("mio", "Grandpa!", gap=0.2, sub="GRANDPAAA!"),
    ], pre=0.6, post=1.5, music="-", sfx=[(0.3, "whoosh_down", 0.4, 0.3)]),
    # --- PART B: THE LIGHTHOUSE -------------------------------------------
    Shot("interior_two", s_interior_two, [
        Line("genzo", "Silver hair... eyes like starlight. In fifty years of tending this light, I've only ever heard of them in stories."),
    ], pre=1.6, post=0.6, music="warm", amb={"waves": 0.0, "wind": 0.0, "rain": 0.8},
         sfx=[(0.35, "thunder", 0.5, -0.4)]),
    Shot("mio_stories", s_mio_stories, [
        Line("mio", "Stories? What stories?"),
    ], pre=0.3, post=0.5),
    Shot("genzo_starfolk", s_genzo_starfolk, [
        Line("genzo", "The Starfolk. When a star loses its way, it falls to the earth, searching for a light that can guide it home."),
    ], pre=0.4, post=0.8),
    Shot("lumi_heard", s_lumi_heard, [
        Line("lumi", "Your light... I heard it, all the way from up there. It was the only warm thing in the dark."),
    ], pre=0.5, post=0.8),
    Shot("mio_determined", s_mio_determined, [
        Line("mio", "Then we'll help you get back! Right, Grandpa?"),
    ], pre=0.2, post=0.6, sfx=[(0.0, "sparkle", 0.5, 0.0)]),
    Shot("genzo_hesitant", s_genzo_hesitant, [
        Line("genzo", "Hmm... The lighthouse only shines across the sea, Mio. To turn it toward the sky, you would need..."),
    ], pre=0.5, post=0.8),
    Shot("lumi_stone", s_lumi_stone, [
        Line("lumi", "I don't have much time. If my light goes out before I return... I'll turn into an ordinary stone."),
    ], pre=0.6, post=0.4, music="tension"),
    Shot("mio_stone", s_mio_stone, [
        Line("mio", "A stone?!"),
    ], pre=0.25, post=1.2, music="-", sfx=[(0.2, "thunder", 0.9, 0.0), (0.15, "hit", 0.4, 0.0)]),
    # --- PART C: THE PROMISE ----------------------------------------------
    Shot("balcony_two", s_balcony_two, [
        Line("mio", "Hey, Lumi... What's it like? Being a star?", gap=0.8),
        Line("lumi", "Quiet. Beautiful. And very, very far away from everyone.", gap=0.9),
        Line("mio", "Well... You're not far away now."),
    ], pre=1.6, post=0.6, music="tender", amb={"rain": 0.0, "waves": 0.5, "wind": 0.25}),
    Shot("hands", s_hands, [], min_dur=4.0, sfx=[(1.45, "sparkle", 0.7, 0.0)]),
    Shot("lumi_wish", s_lumi_wish, [
        Line("lumi", "Mio... your hand is so warm. Is this what a wish feels like?"),
    ], pre=0.8, post=0.8),
    Shot("mio_promise", s_mio_promise, [
        Line("mio", "I promise, Lumi. I'll get you home."),
    ], pre=0.6, post=1.0),
    Shot("lighthouse_night", s_lighthouse_night, [], min_dur=6.0),
    # --- TAG: THE COLLECTOR -----------------------------------------------
    Shot("collector", s_collector, [
        Line("collector", "One of my stars has slipped out of its cage...", gap=0.9),
        Line("collector", "Find her. Before the seventh night is over, her light will be mine."),
    ], pre=1.2, post=1.6, music="villain", amb={"waves": 0.0, "wind": 0.9},
         sfx=[(2.0, "thunder", 0.6, 0.3)]),
    # --- ENDING -----------------------------------------------------------
    Shot("ed", s_ed, [], min_dur=34.0, music="ed", amb={"wind": 0.0}),
    Shot("preview", s_preview, [
        Line("mio", "Next time on Starfall Keeper: The Lighthouse That Faces the Sky! Seven nights to turn the light around... We can do this, Lumi!"),
    ], pre=0.8, post=1.2, music="op", sfx=[(0.0, "hit", 0.5, 0.0)]),
    Shot("end", s_end, [], min_dur=3.5, music="-"),
]

SUB_COLORS = {"mio": "#ffffff", "lumi": "#fff1b0", "genzo": "#cfe6ff", "collector": "#ff9fb0"}

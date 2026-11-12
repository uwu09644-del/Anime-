"""FAULTLINE - Episode 1: "Rank F".  An original action anime.

Kai Arisawa, a Rank-F salvager who cleans up cleared Gates, is trapped when a
new fracture tears open in a subway dungeon. When an armoured Warden flattens
the A-rank swordswoman Hana Kirishima, Kai's eyes crack with gold light and he
sees the fault lines running through everything - including the monster.
"""
import math

import skia

from ep01 import Line, Shot  # reuse the screenplay dataclasses from the Starfall episode
from gfx import (ADD, H, W, Saved, clamp, draw_text, ease_in, ease_in_out, ease_out, fill, font, glow, hash01,
                 lerp, letterbox, linear, new_surface, poly_path, pulse, ramp, rgb, screen_fade, sparkle, stroke,
                 wrap_text)
from faultline import fx
from faultline.bg import city_dusk, control_room, id_screen, rank_crest, rooftop_night, subway, wall_crack
from faultline.chars import (POSES, Pose, blend_pose, draw_director, draw_figure, draw_hana, draw_kai, warden,
                             warden_claw)
from faultline.sound import AMBIENCE, CUE_GAINS, CUES, SFX, VOICE_FX, VOICE_REVERB, VOICES  # noqa: F401

NAME = "faultline_ep01"
OUT = "faultline/episode01/FAULTLINE_EP01.mp4"
TITLE = "FAULTLINE - Episode 1: Rank F"
SUB_FONT = "MPlusRounded1c-ExtraBold.ttf"
SUB_OUTLINE = "#05040a"
SUB_COLORS = {"kai": "#ffffff", "kai_inner": "#ffe7a8", "hana": "#ffc4cc", "narrator": "#cfe2ff",
              "operator": "#a8f0d0", "director": "#d6d6e6", "analyst": "#a8d8ff"}

# per-frame post settings a shot can tweak while drawing
FX = {}
DEFAULT_POST = dict(bloom_amt=0.6, threshold=0.8, wide=0.4, vig=0.55, grain_amt=6.0)


def POST(c, surf, tg, t, shot):
    kw = dict(DEFAULT_POST)
    kw.update(FX)
    FX.clear()
    fx.post_np(c, surf, tg, **kw)


# ======================================================================
#  helpers
# ======================================================================
def twos(t):
    """Characters animate on twos (12 drawings per second), like TV anime."""
    return math.floor(t * 12) / 12


def blink(t, seed=0):
    period = 2.8 + hash01(seed, 3) * 2.4
    ph = (t + hash01(seed, 9) * period) % period
    return math.sin(ph / 0.12 * math.pi) if ph < 0.12 else 0.0


def shake(t, amp):
    return (math.sin(t * 53) * amp + math.sin(t * 29) * amp * 0.6,
            math.cos(t * 47) * amp + math.sin(t * 19) * amp * 0.6)


def cam(c, z, cx=W / 2, cy=H / 2, rot=0.0):
    c.translate(W / 2, H / 2)
    if rot:
        c.rotate(rot)
    c.scale(z, z)
    c.translate(-cx, -cy)


def headlamp(c, x, y, ang, t, length=1300, spread=0.32, alpha=0.22):
    a0, a1 = ang - spread, ang + spread
    p = poly_path([(x, y), (x + math.cos(a0) * length, y + math.sin(a0) * length),
                   (x + math.cos(a1) * length, y + math.sin(a1) * length)])
    c.drawPath(p, fill(0, shader=linear((x, y), (x + math.cos(ang) * length, y + math.sin(ang) * length),
                                        [rgb("#fff2d0", alpha), rgb("#fff2d0", 0)]), blend=ADD))
    glow(c, x, y, 40, "#fff2d0", 0.8)


def core_item(c, x, y, t, s=1.0):
    glow(c, x, y, 120 * s, "#5ad1ff", 0.8)
    c.drawPath(poly_path([(x, y - 40 * s), (x + 24 * s, y), (x, y + 40 * s), (x - 24 * s, y)]), fill(rgb("#bff0ff")))
    c.drawPath(poly_path([(x, y - 40 * s), (x + 24 * s, y), (x, y + 40 * s), (x - 24 * s, y)]),
               stroke(rgb("#ffffff"), 3))


def thought_frame(c, a=1.0):
    """Soft inner-monologue vignette (dark blue edges)."""
    fx.vignette(c, 0.6 * a, "#030616")


_OFF = None
_SHARDS = None


def offscreen():
    global _OFF
    if _OFF is None:
        _OFF = new_surface()
    return _OFF


# ======================================================================
#  COLD OPEN
# ======================================================================
def s_co_city(c, t, d, ctx):
    with Saved(c):
        cam(c, 1.0 + 0.06 * t / d, 960, 470 - 20 * t / d)
        city_dusk(c, t, pan=t * 10)
        # hunters' light trails shooting toward the gate and tiny monsters around it
        for i in range(6):
            u = ((t * 0.35 + hash01(i, 2)) % 1.0)
            x0, y0 = 200 + hash01(i, 3) * 1400, 900
            x1, y1 = 1240, 260
            x, y = lerp(x0, x1, u), lerp(y0, y1, u)
            c.drawLine(x, y, lerp(x0, x1, max(0, u - 0.08)), lerp(y0, y1, max(0, u - 0.08)),
                       stroke(rgb("#9fe0ff"), 4, alpha=0.8 * (1 - u), blend=ADD))
        for i in range(9):
            a = t * (0.6 + 0.2 * hash01(i, 5)) + i
            mx, my = 1240 + math.cos(a) * (260 + 60 * hash01(i, 6)), 260 + math.sin(a) * 90
            flap = math.sin(t * 12 + i) * 10
            c.drawPath(poly_path([(mx - 22, my + flap), (mx, my), (mx + 22, my + flap), (mx, my + 8)]),
                       fill(rgb("#0a0610")))
    FX.update(vig=0.6)


def s_co_ranks(c, t, d, ctx):
    c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(0, shader=linear((0, 0), (0, H),
               [rgb("#04050c"), rgb("#0c1022")])))
    fx.dust(c, t, n=40, alpha=0.3)
    letters = "SABCDEF"
    f_time = ctx.line_start(1) if len(ctx.lines) > 1 else d * 0.6
    for i, L in enumerate(letters):
        appear = 0.25 + i * 0.32
        a = ease_out(clamp((t - appear) / 0.25))
        x = 180 + i * 260
        dim = 1.0
        if t > f_time and L != "F":
            dim = 1 - 0.8 * ramp(t, f_time, f_time + 0.4)
        sc = 0.7 + 0.1 * (1 - a)
        if L == "F" and t > f_time:
            u = ramp(t, f_time, f_time + 0.5)
            x = lerp(x, 960, u)
            sc = lerp(0.7, 1.6, u)
        if a > 0:
            rank_crest(c, x, 540, sc, L, a * dim, t)
    FX.update(bloom_amt=0.8)


def s_co_kai(c, t, d, ctx):
    tq = twos(t)
    with Saved(c):
        cam(c, 1.0 + 0.05 * t / d, 960, 540)
        subway(c, t)
        headlamp(c, 1180, 300, math.pi * 0.85, t, alpha=0.18)
    draw_kai(c, 1180, 520, 1.25, Pose(yaw=-0.35, t=tq, mouth=0.0, look=(-0.4, 0.2), blink=blink(t, 1),
                                      rim="#5ad1ff", rim_side=1, light=-1, sway=math.sin(tq) * 0.3))
    thought_frame(c)


# ======================================================================
#  OPENING
# ======================================================================
OPB = 60 / 160 * 4  # one bar


def s_op(c, t, d, ctx):
    b = t / OPB
    if b < 2:
        c.clear(rgb("#000000"))
        u = clamp(t / (2 * OPB))
        lines = fx.make_cracks(5, 960, 540, 1100, 0, 9, 0.55, 22)
        fx.draw_cracks(c, lines, ease_in(u), "#ffd86a", 4, 1.0)
        FX.update(bloom_amt=0.9)
    elif b < 3:
        lt = t - 2 * OPB
        with Saved(c):
            cam(c, 1.1, 960 + lt * 60, 500)
            city_dusk(c, t, pan=200 + lt * 120, sky_low="#ff5a5a")
        c.drawRect(skia.Rect.MakeLTRB(-W, 900, 2 * W, 2 * H), fill(rgb("#05040a")))
        draw_figure(c, "kai", 760, 700, 380, POSES["idle"], t=twos(t), rim="#ff9a6a", rim_side=-1, silhouette=1.0,
                    weapon_glow=-1)
    elif b < 4:
        lt = t - 3 * OPB
        fx.action_bg(c, t, "#1a0410", "#3a0a1a", "#ff4a60", 0.3, direction=0.2)
        draw_hana(c, 1100, 520, 1.35, Pose(yaw=-0.5, t=twos(t), brow=-0.8, rim="#ff4a60", rim_side=-1, light=-1))
        fx.slash_arc(c, 900, 600, 700, -2.6, 2.4, clamp(lt / 1.0), "#ff2a4a", 90)
    elif b < 5:
        lt = t - 4 * OPB
        c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(rgb("#0a0206")))
        warden(c, 960, 540 + 440 * 3.2, 3.2, t, eye=ramp(lt, 0, 0.3))
        FX.update(bloom_amt=0.9)
    elif b < 6:
        lt = t - 5 * OPB
        draw_kai(c, 960, 540 - 13 * 5.5, 5.5, Pose(t=twos(t), awaken=ramp(lt, 0.1, 0.8), brow=-0.6, rim_w=0,
                                                    light=1), body=False)
        FX.update(bloom_amt=0.9)
    elif b < 8:
        lt = t - 6 * OPB
        k = int(lt / (OPB / 2)) % 4
        fx.action_bg(c, t, "#0a0a20" if k % 2 == 0 else "#1a0410", "#1a0f2e", "#ffffff", 0.35,
                     direction=0.0 if k % 2 == 0 else math.pi)
        if k % 2 == 0:
            draw_figure(c, "kai", 700 + (lt % (OPB / 2)) * 600, 650, 520, POSES["run_a" if int(lt * 8) % 2 else "run_b"],
                        t=twos(t), rim="#ffcf4a", rim_side=-1, eye_glow=1.0, blur=10, weapon_glow=0.6)
        else:
            draw_figure(c, "hana", 1200 - (lt % (OPB / 2)) * 600, 650, 520, POSES["slash"], t=twos(t), facing=-1,
                        rim="#ff4a60", rim_side=1, weapon_glow=1.0, blur=10)
        if (lt % (OPB / 2)) < 0.07:
            FX.update(impact="ink", tint="#ffd86a" if k % 2 == 0 else "#ff4a60")
    elif b < 9:
        lt = t - 8 * OPB
        control_room(c, t)
        c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(rgb("#000000"), 0.5))
        draw_director(c, 960, 560, 1.3, Pose(yaw=0.1, t=t, rim="#3aa0ff", rim_side=1), glare=1.0)
    else:
        lt = t - 9 * OPB
        c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(0, shader=linear((0, 0), (0, H),
                   [rgb("#04050c"), rgb("#140a1e")])))
        fx.embers(c, t, n=40, color="#ffb84a")
        a = ease_out(clamp(lt / 0.35))
        sc = 1.4 - 0.4 * a
        with Saved(c):
            c.translate(W / 2, 470)
            c.scale(sc, sc)
            draw_text(c, "FAULTLINE", 0, 60, font("DelaGothicOne-Latin.ttf", 210), "#f4f6ff", a,
                      outline="#05040a", outline_w=24)
            lines = fx.make_cracks(9, 0, 0, 700, 0, 6, 0.5, 20)
            fx.draw_cracks(c, lines, clamp(lt / 0.6), "#ffd86a", 5, 1.0)
        draw_text(c, "断層の狩人", W / 2, 680, font("DelaGothicOne-JP.ttf", 60), "#ffd86a", ramp(lt, 0.3, 0.7),
                  outline="#05040a", outline_w=8)
        draw_text(c, "EPISODE 1   RANK F", W / 2, 800, font("MPlusRounded1c-ExtraBold.ttf", 52), "#ffffff",
                  ramp(lt, 1.2, 1.7), outline="#05040a", outline_w=8)
        screen_fade(c, clamp(1 - lt / 0.25), "#ffffff")
        screen_fade(c, ramp(t, d - 0.6, d), "#000000")
        FX.update(bloom_amt=0.8)
    # hard cut flashes on each bar
    if 2 <= b < 9 and (t % OPB) < 0.05:
        screen_fade(c, 0.6, "#ffffff")


# ======================================================================
#  PART A - THE DUNGEON
# ======================================================================
def s_tun_wide(c, t, d, ctx):
    walk = t * 0.9
    x = lerp(600, 1100, t / d)
    with Saved(c):
        cam(c, 1.0, 960 + (x - 900) * 0.1, 540)
        subway(c, t)
        headlamp(c, x + 30, 420, math.pi * 0.1 + math.sin(t) * 0.1, t)
        draw_figure(c, "kai", x, 760, 360, blend_pose("run_a", "run_b", 0.5 + 0.5 * math.sin(walk * math.tau)),
                    t=twos(t), rim="#5ad1ff", rim_side=-1, weapon_glow=-1)


def s_kai_radio(c, t, d, ctx):
    tq = twos(t)
    with Saved(c):
        cam(c, 1.3, 760, 420)
        subway(c, t)
    draw_kai(c, 900, 540, 1.35, Pose(yaw=0.25, t=tq, mouth=ctx.mouth("kai", True), look=(0.6, 0.6),
                                     blink=blink(t, 2), rim="#5ad1ff", rim_side=-1, light=1, smile=0.1))
    core_item(c, 1330, 960 - 40 * ease_out(clamp(t / 1.0)), t, 1.3)


def s_kai_notice(c, t, d, ctx):
    tq = twos(t)
    turn = ease_in_out(clamp((t - 0.3) / 0.5))
    with Saved(c):
        cam(c, 1.25, 900, 440)
        subway(c, t)
        wall_crack(c, t, 330, 470, 0.25 + 0.05 * math.sin(t * 6))
    draw_kai(c, 1150, 540, 1.35, Pose(yaw=lerp(0.25, -0.55, turn), t=tq, mouth=ctx.mouth("kai", True),
                                      look=(-0.8, 0.0), brow=0.4, blink=blink(t, 3), rim="#ff4a60", rim_side=-1,
                                      light=1))


def s_crack_open(c, t, d, ctx):
    u = ease_in(clamp(t / (d * 0.8)))
    dx, dy = shake(t, 4 + 14 * u)
    with Saved(c):
        c.translate(dx, dy)
        cam(c, 1.0 + 0.1 * u, 760, 480)
        subway(c, t, red=u)
        wall_crack(c, t, 560, 470, 0.25 + 0.85 * u)
        draw_figure(c, "kai", 1350, 780, 380, blend_pose("idle", "hurt", 0.4 * u), t=twos(t), facing=-1,
                    rim="#ff4a60", rim_side=1, weapon_glow=-1)
        for i in range(14):  # falling debris
            yy = ((t * 600 + hash01(i, 1) * 900) % 1200) - 100
            xx = 200 + hash01(i, 2) * 1500
            c.drawRect(skia.Rect.MakeXYWH(xx, yy, 14 + 20 * hash01(i, 3), 10 + 14 * hash01(i, 4)),
                       fill(rgb("#05060c")))
    FX.update(ca=6 * u)


def s_warden_reveal(c, t, d, ctx):
    rise = ease_out(clamp(t / 2.2))
    roar = pulse(t, 2.4, d - 0.3, 0.2)
    dx, dy = shake(t, 3 + 16 * roar)
    with Saved(c):
        c.translate(dx, dy)
        cam(c, 1.0, 960, 540, rot=-4)
        subway(c, t, red=1.0)
        wall_crack(c, t, 960, 420, 1.0, 1.4)
        warden(c, 960, lerp(1500, 760, rise), 0.95, twos(t), eye=ramp(t, 1.6, 2.0), jaw=roar)
    FX.update(ca=5 * roar, bloom_amt=0.75)


def s_kai_terror(c, t, d, ctx):
    tq = twos(t)
    dx, dy = shake(t, 3)
    with Saved(c):
        cam(c, 1.4, 960, 420)
        subway(c, t, red=1.0)
    draw_kai(c, 960 + dx, 540 + dy, 1.5, Pose(yaw=0.1, t=tq, mouth=ctx.mouth("kai", True), surprise=1.0, brow=0.8,
                                              sweat=1.0, rim="#ff3040", rim_side=-1, rim_w=12, light=-1))
    FX.update(vig=0.7)


def s_hana_arrive(c, t, d, ctx):
    land = ease_out(clamp(t / 0.5))
    with Saved(c):
        cam(c, 1.0, 960, 540)
        subway(c, t, red=1.0)
        fx.action_bg(c, t, "#1a0410", "#3a0a1a", "#ff4a60", 0.18 * (1 - land), direction=math.pi / 2)
        x = lerp(-300, 760, land)
        pose = blend_pose("dash", "ready", ramp(t, 0.4, 0.8))
        draw_figure(c, "hana", x, 700, 460, pose, t=twos(t), rim="#ff4a60", rim_side=-1, weapon_glow=1.0,
                    blur=12 * (1 - land))
        draw_figure(c, "kai", 1400, 780, 360, POSES["crouch"], t=twos(t), facing=-1, rim="#ff4a60", rim_side=1,
                    weapon_glow=-1)
        if t > 0.45:
            fx.shockwave(c, 760, 960, clamp((t - 0.45) / 0.6), 700, "#ff8090", 30, 0.2)
            fx.sparks(c, 760, 950, t - 0.45, n=24, color="#ff9aa8", spread=2.6)
    if 0.45 < t < 0.52:
        FX.update(impact="ink", tint="#ff4060")


def s_hana_close(c, t, d, ctx):
    tq = twos(t)
    with Saved(c):
        cam(c, 1.3, 1100, 420)
        subway(c, t, red=1.0)
    draw_hana(c, 960, 530, 1.45, Pose(yaw=-0.45, t=tq, mouth=ctx.mouth("hana", True), brow=-0.8, look=(-0.6, 0),
                                      blink=blink(t, 4), rim="#ff4a60", rim_side=-1, light=-1, sway=0.3))
    # sword glint passing
    gx = lerp(400, 1600, clamp((t - 0.4) / 0.6))
    if 0.4 < t < 1.0:
        sparkle(c, gx, 980, 60, "#ffffff", 1.0)


def s_hana_dash(c, t, d, ctx):
    u = clamp(t / d)
    fx.action_bg(c, t, "#14030c", "#3a0a1a", "#ff6a7a", 0.4, direction=0.0)
    draw_figure(c, "hana", lerp(-200, 1500, ease_in(u)), 640, 560, POSES["dash"], t=twos(t), rim="#ff4a60",
                rim_side=-1, weapon_glow=1.0, blur=16)
    fx.slash_arc(c, lerp(-200, 1500, ease_in(u)) + 200, 560, 380, -2.0, 2.2, u, "#ff2a4a", 80)


def s_clang(c, t, d, ctx):
    dx, dy = shake(t, 18 * clamp(1 - t / 0.6))
    with Saved(c):
        c.translate(dx, dy)
        c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(rgb("#14030a")))
        warden(c, 1100, 900, 1.7, t, eye=1.0)
        fx.slash_arc(c, 700, 700, 500, -1.2, 1.2, 0.35 + 0.5 * clamp(t / 0.4), "#ff2a4a", 90)
        fx.sparks(c, 980, 560, t, n=50, color="#ffd27a", speed=1400, spread=2.2, angle=math.pi * 1.1)
        fx.burst(c, 980, 560, 260 * clamp(1 - t / 0.25), 16, "#ffffff", 0.9 * clamp(1 - t / 0.25))
    if t < 0.08:
        FX.update(impact="ink", tint="#ffffff")
    else:
        FX.update(ca=10 * clamp(1 - t / 0.5))


def s_hana_shock(c, t, d, ctx):
    tq = twos(t)
    with Saved(c):
        cam(c, 1.4, 900, 420)
        subway(c, t, red=1.0)
    draw_hana(c, 960, 540, 1.5, Pose(yaw=0.2, t=tq, mouth=ctx.mouth("hana", True), surprise=1.0, brow=0.5,
                                     rim="#ff4a60", rim_side=1, light=1, sweat=0.0))
    fx.vignette(c, 0.3, "#3a0010")


def s_claw_swipe(c, t, d, ctx):
    u = clamp(t / 0.55)
    dx, dy = shake(t, 22 * pulse(t, 0.35, 0.7, 0.1))
    with Saved(c):
        c.translate(dx, dy)
        subway(c, t, red=1.0)
        hx = lerp(900, 2100, ease_out(clamp((t - 0.4) / 0.7)))
        hy = lerp(620, 380, ease_out(clamp((t - 0.4) / 0.7)))
        pose = blend_pose("ready", "hurt", clamp((t - 0.35) / 0.15))
        draw_figure(c, "hana", hx, hy, 460, pose, t=twos(t), rim="#ff4a60", rim_side=-1, weapon_glow=0.3,
                    blur=10 * clamp((t - 0.35) / 0.2))
        lay = skia.Paint()
        lay.setImageFilter(skia.ImageFilters.Blur(30 * (1 - abs(u - 0.5) * 2) + 2, 4))
        c.saveLayer(None, lay)
        warden_claw(c, lerp(-500, 1500, ease_in_out(u)), lerp(200, 700, ease_in_out(u)), 1.0,
                    angle=lerp(-30, 25, u))
        c.restore()
    if 0.35 < t < 0.42:
        FX.update(impact="invert", tint="#ff4060")
    else:
        FX.update(ca=8 * pulse(t, 0.35, 0.8, 0.2))


def s_hana_down(c, t, d, ctx):
    tq = twos(t)
    with Saved(c):
        cam(c, 1.15, 760, 560)
        subway(c, t, red=1.0)
    draw_hana(c, 960, 640, 1.45, Pose(yaw=-0.3, t=tq, mouth=ctx.mouth("hana", True), hurt=1.0, brow=0.9,
                                      blink=blink(t, 5), rim="#ff4a60", rim_side=-1, light=-1, tilt=10))
    fx.dust(c, t, n=50, color="#ffb0b8", alpha=0.6, seed=8)


def s_kai_freeze(c, t, d, ctx):
    tq = twos(t)
    dx, dy = shake(t, 2.5)
    c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(0, shader=linear((0, 0), (0, H),
               [rgb("#120208"), rgb("#2a0812")])))
    fx.dust(c, t, n=60, color="#ff8a9a", alpha=0.4, seed=9)
    draw_kai(c, 960 + dx, 540 + dy, 1.55, Pose(yaw=-0.1, t=tq, mouth=0.0, surprise=0.4, brow=0.9, sweat=1.0,
                                                look=(0, 0.5), blink=blink(t, 6), rim="#ff3040", rim_side=1,
                                                light=1))
    thought_frame(c)
    FX.update(vig=0.75)


def s_warden_raise(c, t, d, ctx):
    u = ease_in_out(clamp(t / d))
    with Saved(c):
        cam(c, 1.05, 960, 520, rot=5)
        subway(c, t, red=1.0)
        warden(c, 1180, 820, 0.85, twos(t) * 0.4, eye=1.0, jaw=0.2)
        warden_claw(c, 1500, lerp(500, 120, u), 0.7, angle=-110 + 20 * u)
        draw_figure(c, "hana", 560, 860, 360, POSES["down"], t=twos(t), rim="#ff4a60", rim_side=1, coat_wave=0.0)
    FX.update(grain_amt=9, contrast=1.1)


def s_kai_step(c, t, d, ctx):
    step = ease_in_out(clamp(t / 1.2))
    with Saved(c):
        cam(c, 1.1, 960, 560)
        subway(c, t, red=1.0)
        draw_figure(c, "kai", lerp(900, 980, step), 780, 520, blend_pose("crouch", "idle", step), t=twos(t),
                    facing=1, rim="#ff4a60", rim_side=-1, silhouette=0.85, weapon_glow=-1)
    FX.update(contrast=1.15, grain_amt=8)


def s_eye_awaken(c, t, d, ctx):
    aw = ease_in(clamp((t - 0.4) / 1.6))
    c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(rgb("#0a0206")))
    with Saved(c):
        cam(c, 1.0 + 0.15 * t / d, 960, 540)
        draw_kai(c, 960, 540 - 13 * 6, 6.0, Pose(t=twos(t), awaken=aw, brow=-0.6 * aw, rim_w=0, light=1,
                                                 blink=0), body=False)
    if aw > 0.2:
        for k, (x, y) in enumerate(((960 + 264, 540), (960 - 264, 540))):
            lines = fx.make_cracks(40 + k, x, y, 900, 0, 7, 0.5, 24)
            fx.draw_cracks(c, lines, (aw - 0.2) / 0.8, "#ffd86a", 5, 1.0)
    FX.update(bloom_amt=0.35 + 0.35 * aw, threshold=0.85)


def s_fault_sight(c, t, d, ctx):
    lay = fx.grade_paint(0.55, 0.65, 0.95, contrast=1.15, sat=0.0, lift=(0, 4, 18))
    with Saved(c):
        cam(c, 1.0 + 0.04 * t / d, 960, 540)
        c.saveLayer(None, lay)
        subway(c, t * 0.15, red=1.0)
        warden(c, 1180, 820, 0.85, t * 0.1, eye=1.0, jaw=0.2)
        draw_figure(c, "hana", 560, 860, 360, POSES["down"], t=0, rim="#ffffff", rim_side=1, coat_wave=0.0)
        c.restore()
        # gold fault lines over everything; the brightest one through the Warden's core
        prog = ease_out(clamp(t / 2.5))
        for k, (x, y, L) in enumerate(((300, 900, 700), (1600, 200, 600), (900, 300, 500), (200, 300, 500),
                                       (1500, 1000, 600))):
            fx.draw_cracks(c, fx.make_cracks(60 + k, x, y, L, k * 1.3, 2, 0.6, 22), prog, "#ffd86a", 2.5, 0.6)
        fx.draw_cracks(c, fx.make_cracks(31, 1180, 820, 500, 0, 9, 0.55, 22), prog, "#ffd86a", 3.5, 0.9)
        core = 0.6 + 0.4 * math.sin(t * 5)
        glow(c, 1180, 820, 160, "#ffe48a", core * prog)
        sparkle(c, 1180, 820, 50 * core * prog, "#fffbe8", prog)
    FX.update(bloom_amt=0.8, vig=0.7)


def s_kai_grab(c, t, d, ctx):
    tq = twos(t)
    with Saved(c):
        cam(c, 1.3, 900, 440)
        lay = fx.grade_paint(0.55, 0.65, 0.95, contrast=1.15, sat=0.0, lift=(0, 4, 18))
        c.saveLayer(None, lay)
        subway(c, 0.0, red=1.0)
        c.restore()
    draw_kai(c, 960, 540, 1.5, Pose(yaw=0.35, t=tq, mouth=ctx.mouth("kai", True), awaken=1.0, brow=-0.9, grit=0.0,
                                    smile=0.25, rim="#ffcf4a", rim_side=1, rim_w=12, light=1))
    fx.dust(c, t, n=40, color="#ffe48a", alpha=0.5, seed=12)
    FX.update(bloom_amt=0.8)


def s_kai_dash(c, t, d, ctx):
    u = clamp(t / d)
    fx.action_bg(c, t, "#0a0a14", "#1a1408", "#ffd86a", 0.45, direction=0.0)
    if u < 0.5:
        pose = POSES["run_a"] if int(t * 12) % 2 else POSES["run_b"]
        x = lerp(-200, 900, u * 2)
        draw_figure(c, "kai", x, 640, 560, pose, t=twos(t), rim="#ffcf4a", rim_side=-1, eye_glow=1.0, blur=10,
                    weapon_glow=0.8)
    else:
        uu = (u - 0.5) * 2
        warden_claw(c, lerp(1900, 400, uu), 360, 0.9, angle=lerp(-10, 10, uu))
        draw_figure(c, "kai", lerp(700, 1500, uu), 820, 560, POSES["slide"], t=twos(t), rim="#ffcf4a", rim_side=-1,
                    eye_glow=1.0, blur=12, weapon_glow=0.8)
        fx.sparks(c, lerp(700, 1500, uu) - 200, 960, (uu % 0.3), n=20, color="#ffd27a", angle=math.pi, spread=0.8)
    FX.update(bloom_amt=0.7)


def s_kai_strike(c, t, d, ctx):
    u = clamp(t / 0.6)
    c.drawRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, 2 * H), fill(rgb("#0a0408")))
    warden(c, 1250, 760, 1.15, 0.0, eye=1.0, jaw=0.3)
    pose = blend_pose("strike", "strike2", ease_in(u))
    draw_figure(c, "kai", lerp(300, 900, ease_out(u)), lerp(800, 700, u), 620, pose, t=twos(t), rim="#ffcf4a",
                rim_side=-1, eye_glow=1.0, weapon_glow=1.0, blur=8 * (1 - u))
    if u >= 1:
        fx.burst(c, 1250, 760, 600 * ease_out(clamp((t - 0.6) / 0.3)), 22, "#fff3c0",
                 clamp(1 - (t - 0.6) / 0.5), rot=t)
        fx.shockwave(c, 1250, 760, clamp((t - 0.6) / 0.8), 1100, "#ffd86a", 60)
    if 0.6 <= t < 0.72:
        FX.update(impact="invert", tint="#ffd86a")
    else:
        FX.update(ca=12 * pulse(t, 0.6, 1.0, 0.2), bloom_amt=0.9)


def s_crack_spread(c, t, d, ctx):
    u = clamp(t / (d * 0.9))
    with Saved(c):
        cam(c, 1.0 + 0.08 * u, 960, 600)
        subway(c, 0.0, red=1.0)
        warden(c, 960, 640, 0.75, 0.0, eye=1.0 - 0.6 * u, crack=u, breathe=0.0)
    FX.update(bloom_amt=0.7 + 0.3 * u, contrast=1.1)


def s_shatter(c, t, d, ctx):
    global _SHARDS
    off = offscreen()
    oc = off.getCanvas()
    oc.clear(skia.ColorTRANSPARENT)
    warden(oc, 960, 640, 0.75, 0.0, eye=0.4, crack=1.0, breathe=0.0)
    img = off.makeImageSnapshot()
    if _SHARDS is None:
        _SHARDS = fx.Shards((380, 0, 1540, 1080), n=170, seed=21, center=(960, 640), power=1.1)
    with Saved(c):
        dx, dy = shake(t, 20 * clamp(1 - t / 0.8))
        c.translate(dx, dy)
        subway(c, t, red=lerp(1.0, 0.2, clamp(t / 2.5)))
        fx.draw_shatter(c, img, _SHARDS, t * 0.75, gravity=500, fade=2.6)
        glow(c, 960, 640, 900 * clamp(1 - t / 1.5), "#fff3c0", clamp(1 - t / 1.2))
        fx.shockwave(c, 960, 640, clamp(t / 1.0), 1400, "#ffd86a", 70)
        for i in range(40):  # glittering motes
            a = hash01(i, 1) * math.tau
            r = t * (300 + 600 * hash01(i, 2))
            sparkle(c, 960 + math.cos(a) * r, 640 + math.sin(a) * r + 100 * t * t, 8 + 8 * hash01(i, 3), "#fff3c0",
                    clamp(1 - t / 2.5))
    screen_fade(c, clamp(1 - t / 0.25), "#ffffff")
    FX.update(bloom_amt=0.9, ca=8 * clamp(1 - t / 0.6))


def s_kai_after(c, t, d, ctx):
    with Saved(c):
        cam(c, 1.0 + 0.04 * t / d, 960, 560)
        subway(c, t, red=0.15)
        for i in range(50):  # glowing shards drifting down
            x = hash01(i, 1) * W
            y = ((t * (40 + 80 * hash01(i, 2)) + hash01(i, 3) * H) % (H + 100)) - 50
            r = 6 + 10 * hash01(i, 4)
            c.drawPath(poly_path([(x, y - r), (x + r * 0.6, y), (x, y + r), (x - r * 0.6, y)]),
                       fill(rgb("#ffe7a0"), 0.8, blend=ADD))
        crumble = ramp(t, 1.0, 2.0)
        draw_figure(c, "kai", 960, 760, 520, POSES["idle"], t=twos(t), rim="#ffcf4a", rim_side=-1,
                    eye_glow=1 - ramp(t, 2.0, 3.0), weapon_glow=-1 if crumble > 0.5 else 0.3)
        if 0 < crumble < 1:
            for i in range(20):
                c.drawCircle(1080 + hash01(i, 5) * 60, 760 + crumble * 300 * hash01(i, 6), 4,
                             fill(rgb("#8a8f9a"), 1 - crumble))
    FX.update(bloom_amt=0.7)


def s_hana_amazed(c, t, d, ctx):
    tq = twos(t)
    with Saved(c):
        cam(c, 1.4, 800, 420)
        subway(c, t, red=0.15)
    draw_hana(c, 960, 540, 1.45, Pose(yaw=0.3, t=tq, mouth=ctx.mouth("hana", True), surprise=0.6, hurt=0.6,
                                      brow=0.4, blink=blink(t, 7), rim="#ffcf4a", rim_side=1, light=1, tilt=-3))


def s_kai_confused(c, t, d, ctx):
    tq = twos(t)
    with Saved(c):
        cam(c, 1.4, 1100, 420)
        subway(c, t, red=0.15)
    draw_kai(c, 960, 540, 1.45, Pose(yaw=-0.3, t=tq, mouth=ctx.mouth("kai", True), look=(0, 1.0), brow=0.7,
                                     sweat=0.8, awaken=0.15, blink=blink(t, 8), rim="#ffcf4a", rim_side=-1, light=-1))


def s_hana_rank(c, t, d, ctx):
    tq = twos(t)
    with Saved(c):
        cam(c, 1.4, 800, 420)
        subway(c, t, red=0.15)
    smirk = t > ctx.line_start(2) - 0.3 if len(ctx.lines) > 2 else False
    draw_hana(c, 960, 540, 1.45, Pose(yaw=0.3, t=tq, mouth=ctx.mouth("hana", True), smile=0.7 if smirk else 0.0,
                                      brow=-0.3 if smirk else 0.3, hurt=0.4, blink=blink(t, 9), rim="#ffcf4a",
                                      rim_side=1, light=1))


def s_kai_collapse(c, t, d, ctx):
    tq = twos(t)
    b = ease_in(clamp(t / d))
    lay = skia.Paint()
    lay.setImageFilter(skia.ImageFilters.Blur(1 + 20 * b, 1 + 20 * b))
    c.saveLayer(None, lay)
    with Saved(c):
        cam(c, 1.3 + 0.2 * b, 1000, 440, rot=8 * b)
        subway(c, t, red=0.15)
    draw_kai(c, 960, 560 + 80 * b, 1.4, Pose(yaw=-0.1, t=tq, blink=clamp(b * 1.6), awaken=0.4 * (1 - b), hurt=0.6,
                                             rim="#ffcf4a", rim_side=-1, tilt=10 * b))
    c.restore()
    screen_fade(c, ramp(t, d * 0.55, d), "#000000")


# ======================================================================
#  TAG - THE BUREAU
# ======================================================================
def s_bureau(c, t, d, ctx):
    tq = twos(t)
    with Saved(c):
        cam(c, 1.0 + 0.03 * t / d, 960, 540)
        control_room(c, t, alert=1.0)
    c.drawRect(skia.Rect.MakeWH(W, H), fill(rgb("#000000"), 0.35))
    with Saved(c, fx.grade_paint(0.55, 0.6, 0.8, contrast=1.1)):
        draw_director(c, 960, 600, 1.3, Pose(yaw=0.12, t=tq, mouth=ctx.mouth("director", True), rim="#3aa0ff",
                                             rim_side=1, rim_w=10, light=1), glare=1.0)
    screen_fade(c, clamp(1 - t / 0.6), "#000000")


def s_id_glitch(c, t, d, ctx):
    gl = ramp(t, 1.2, 1.4)
    id_screen(c, t, glitch=gl)
    if 1.2 < t < 1.3:
        FX.update(ca=14)
    if t > d - 0.4:
        screen_fade(c, 1.0, "#000000")


# ======================================================================
#  ED + PREVIEW
# ======================================================================
CREDITS = [
    ("big", "FAULTLINE"), ("small", "Episode 1  -  Rank F"), ("gap", ""),
    ("head", "CAST"),
    ("row", "Kai Arisawa  ....  Kokoro 'am_puck'"),
    ("row", "Hana Kirishima  ....  Kokoro 'af_bella'"),
    ("row", "Director Odaka  ....  Kokoro 'am_fenrir'"),
    ("row", "Narrator  ....  Kokoro 'am_michael'"),
    ("row", "Gate Control  ....  Kokoro 'af_sarah'"),
    ("row", "Bureau Analyst  ....  Kokoro 'af_kore'"), ("gap", ""),
    ("head", "ORIGINAL STORY / SCRIPT"), ("row", "Claude"),
    ("head", "CHARACTER DESIGN / ANIMATION / COMPOSITING"), ("row", "Drawn frame by frame in Python with Skia"),
    ("head", "MUSIC / SOUND"), ("row", "Synthesized with NumPy + SciPy"),
    ("head", "VOICES"), ("row", "Kokoro-82M (Apache-2.0)"),
    ("head", "FONTS"), ("row", "Dela Gothic One / M PLUS Rounded 1c (SIL OFL)"), ("gap", ""),
    ("head", "THANK YOU FOR WATCHING"),
]


def s_ed(c, t, d, ctx):
    with Saved(c):
        rooftop_night(c, t)
        draw_figure(c, "kai", 520, 860, 300, POSES["down"], t=twos(t), rim="#7fd4ff", rim_side=-1, weapon_glow=-1,
                    silhouette=0.6)
    items, y = [], 0
    for kind, txt in CREDITS:
        items.append((kind, txt, y))
        y += {"big": 110, "small": 70, "head": 76, "row": 56, "gap": 60}[kind]
    scroll = lerp(H + 40, -y + 360, clamp(t / (d - 4)))
    c.drawRect(skia.Rect.MakeLTRB(1000, 0, W, H), fill(0, shader=linear((1000, 0), (1300, 0),
               [rgb("#000000", 0), rgb("#000000", 0.55)])))
    for kind, txt, yy in items:
        sy = scroll + yy
        if -80 < sy < H + 80:
            a = clamp(min(sy / 150, (H - sy) / 150))
            if kind == "big":
                draw_text(c, txt, 1450, sy, font("DelaGothicOne-Latin.ttf", 76), "#f4f6ff", a, outline="#05040a",
                          outline_w=10)
            elif kind == "small":
                draw_text(c, txt, 1450, sy, font("MPlusRounded1c-Bold.ttf", 38), "#ffd86a", a)
            elif kind == "head":
                draw_text(c, txt, 1450, sy, font("MPlusRounded1c-ExtraBold.ttf", 32), "#7fd4ff", a)
            elif kind == "row":
                draw_text(c, txt, 1450, sy, font("MPlusRounded1c-Bold.ttf", 32), "#ffffff", a)
    screen_fade(c, clamp(1 - t / 1.0), "#000000")
    screen_fade(c, ramp(t, d - 1.2, d), "#000000")


def s_preview(c, t, d, ctx):
    tq = twos(t)
    fx.action_bg(c, t, "#0a0a20", "#2a0a1a", "#ffd86a", 0.25, direction=-0.3)
    draw_kai(c, 560, 560, 1.3, Pose(yaw=0.35, t=tq, mouth=ctx.mouth("kai", True), brow=-0.5, smile=0.3,
                                    awaken=0.6, rim="#ffcf4a", rim_side=1, light=1))
    a = ramp(t, 0.2, 0.6)
    draw_text(c, "NEXT EPISODE", 1360, 220, font("DelaGothicOne-Latin.ttf", 100), "#ffd86a", a, outline="#05040a",
              outline_w=14)
    draw_text(c, "EPISODE 2", 1360, 350, font("MPlusRounded1c-ExtraBold.ttf", 50), "#ffffff", a, outline="#05040a",
              outline_w=8)
    draw_text(c, "THE UNRANKED", 1360, 470, font("DelaGothicOne-Latin.ttf", 96), "#ffffff", a, outline="#05040a",
              outline_w=12)
    fx.draw_cracks(c, fx.make_cracks(88, 1360, 430, 500, 0, 5, 0.5, 20), ramp(t, 0.5, 1.2), "#ffd86a", 3, 0.8)
    screen_fade(c, clamp(1 - t / 0.3), "#ffffff")


def s_end(c, t, d, ctx):
    c.clear(rgb("#000000"))
    a = ramp(t, 0.2, 0.8) * (1 - ramp(t, d - 0.7, d))
    draw_text(c, "TO BE CONTINUED", W / 2, H / 2 + 30, font("DelaGothicOne-Latin.ttf", 96), "#f4f6ff", a)
    fx.draw_cracks(c, fx.make_cracks(99, W / 2, H / 2, 600, 0, 6, 0.5, 20), ramp(t, 0.4, 1.4) * a, "#ffd86a", 3, a)


# ======================================================================
#  SCREENPLAY
# ======================================================================
SHOTS = [
    # --- COLD OPEN ---------------------------------------------------------
    Shot("co_city", s_co_city, [
        Line("narrator", "Twelve years ago, the sky cracked open over Tokyo."),
        Line("narrator", "The Gates brought monsters with them. And in a few of us, they woke something up."),
    ], pre=1.5, post=0.8, music="fl_dread", amb={"city": 0.8}, fade_in=1.5, bars=1.0),
    Shot("co_ranks", s_co_ranks, [
        Line("narrator", "We call them Hunters. Ranked by power, from S at the top..."),
        Line("narrator", "all the way down to F.", gap=0.4),
    ], pre=0.6, post=1.0, sfx=[(0.2, "swish", 0.5, 0.0), (-1.6, "impact", 0.5, 0.0)]),
    Shot("co_kai", s_co_kai, [
        Line("kai_inner", "And then there's me. Kai Arisawa. Rank F.", gap=0.5),
        Line("kai_inner", "I don't fight monsters. I clean up after the people who do."),
    ], pre=0.6, post=1.0, amb={"city": 0.0, "tunnel": 0.8}),
    # --- OPENING -----------------------------------------------------------
    Shot("op", s_op, [], min_dur=OPB * 11 + 0.8, music="fl_op", amb={"tunnel": 0.0},
         sfx=[(OPB * 9, "shatter", 0.5, 0.0)]),
    # --- PART A: THE DUNGEON ------------------------------------------------
    Shot("tun_wide", s_tun_wide, [
        Line("operator", "Salvage team, Gate 7-C closes in ten minutes. Grab the cores and get out."),
    ], pre=1.2, post=0.6, music="fl_dungeon", amb={"tunnel": 1.0}, fade_in=0.5,
         sfx=[(0.9, "radio", 0.6, 0.3), (0.0, "steps", 0.8, 0.0)]),
    Shot("kai_radio", s_kai_radio, [
        Line("kai", "Copy that. Ten minutes."),
    ], pre=0.6, post=0.8),
    Shot("kai_notice", s_kai_notice, [
        Line("kai", "Huh. That crack isn't on the map."),
    ], pre=0.9, post=0.6, sfx=[(0.2, "crackle", 0.35, -0.5)]),
    Shot("crack_open", s_crack_open, [], min_dur=3.6, music="-",
         sfx=[(0.0, "rumble", 0.9, 0.0), (1.4, "crackle", 0.6, -0.3), (2.6, "debris", 0.7, 0.2),
              (2.9, "braam", 0.7, 0.0)]),
    Shot("warden_reveal", s_warden_reveal, [], min_dur=4.6,
         sfx=[(0.3, "rumble", 0.7, 0.0), (1.6, "riser", 0.4, 0.0), (2.4, "roar", 1.0, 0.0)]),
    Shot("kai_terror", s_kai_terror, [
        Line("kai", "No, no, no... that thing's coming through the wall!"),
    ], pre=0.2, post=0.4),
    Shot("hana_arrive", s_hana_arrive, [
        Line("hana", "Civilian! Get behind me!", at=0.9),
    ], pre=0.9, post=0.5, music="fl_battle",
         sfx=[(0.0, "swish", 0.8, -0.4), (0.45, "impact", 0.6, 0.0), (0.6, "shing", 0.6, 0.2)]),
    Shot("hana_close", s_hana_close, [
        Line("hana", "Stay down. I'll handle this."),
    ], pre=0.4, post=0.5, sfx=[(0.4, "shing", 0.4, 0.4)]),
    Shot("hana_dash", s_hana_dash, [], min_dur=0.9, sfx=[(0.0, "swish", 0.9, 0.0)]),
    Shot("clang", s_clang, [], min_dur=1.4, sfx=[(0.0, "clang", 1.0, 0.1), (0.0, "impact", 0.5, 0.0)]),
    Shot("hana_shock", s_hana_shock, [
        Line("hana", "It didn't even scratch it?!"),
    ], pre=0.2, post=0.3),
    Shot("claw_swipe", s_claw_swipe, [], min_dur=1.6,
         sfx=[(0.0, "roar", 0.6, 0.0), (0.1, "swish", 0.9, 0.0), (0.35, "impact", 1.0, 0.0),
              (0.6, "debris", 0.6, 0.3)]),
    Shot("hana_down", s_hana_down, [
        Line("hana", "Get... out of here. Run!"),
    ], pre=0.8, post=0.6),
    Shot("kai_freeze", s_kai_freeze, [
        Line("kai_inner", "Run. That's what Rank Fs do. We run.", gap=0.6),
        Line("kai_inner", "But if I run... she dies."),
    ], pre=0.6, post=0.6, music="fl_awaken", sfx=[(0.0, "ring", 0.6, 0.0)]),
    Shot("warden_raise", s_warden_raise, [], min_dur=2.4, sfx=[(0.2, "roar", 0.5, 0.0)]),
    Shot("kai_step", s_kai_step, [
        Line("kai", "...No.", at=1.2),
    ], pre=0.8, post=0.8),
    Shot("eye_awaken", s_eye_awaken, [
        Line("kai_inner", "And then I saw them.", at=2.0),
    ], pre=2.0, post=0.4, sfx=[(0.4, "crackle", 0.8, 0.0), (0.3, "riser", 0.5, 0.0)]),
    Shot("fault_sight", s_fault_sight, [
        Line("kai_inner", "Lines. Cracks running through everything...", gap=0.5),
        Line("kai_inner", "like the whole world was made of glass."),
    ], pre=0.8, post=0.8, music="-", sfx=[(0.0, "crackle", 0.5, 0.0), (0.0, "ring", 0.5, 0.0)]),
    Shot("kai_grab", s_kai_grab, [
        Line("kai", "There you are."),
    ], pre=0.6, post=0.5),
    Shot("kai_dash", s_kai_dash, [], min_dur=1.6, music="fl_battle",
         sfx=[(0.0, "braam", 0.8, 0.0), (0.0, "swish", 0.9, -0.3), (0.8, "swish", 0.9, 0.3),
              (0.8, "roar", 0.4, 0.0)]),
    Shot("kai_strike", s_kai_strike, [
        Line("kai", "THERE!", at=0.15),
    ], pre=0.1, post=1.2, sfx=[(0.6, "impact", 1.0, 0.0), (0.6, "clang", 0.6, 0.0)]),
    Shot("crack_spread", s_crack_spread, [], min_dur=2.4, music="-",
         sfx=[(0.0, "crackle", 1.0, 0.0), (0.0, "ring", 0.6, 0.0)]),
    Shot("shatter", s_shatter, [], min_dur=3.6, sfx=[(0.0, "shatter", 1.0, 0.0), (0.0, "impact", 0.7, 0.0)]),
    Shot("kai_after", s_kai_after, [], min_dur=4.2, music="fl_after", sfx=[(1.0, "debris", 0.3, 0.2)]),
    Shot("hana_amazed", s_hana_amazed, [
        Line("hana", "That was an A-rank monster.", gap=0.4),
        Line("hana", "You broke it. With a pipe."),
    ], pre=0.6, post=0.6),
    Shot("kai_confused", s_kai_confused, [
        Line("kai", "I... don't know what I just did."),
    ], pre=0.4, post=0.6),
    Shot("hana_rank", s_hana_rank, [
        Line("hana", "What's your rank?", gap=0.5),
        Line("kai", "...F.", gap=0.8),
        Line("hana", "Not anymore."),
    ], pre=0.5, post=0.9),
    Shot("kai_collapse", s_kai_collapse, [], min_dur=3.0, sfx=[(0.3, "ring", 0.5, 0.0)]),
    # --- TAG: THE BUREAU ----------------------------------------------------
    Shot("bureau", s_bureau, [
        Line("analyst", "Director, the reading from Gate 7-C broke the scale.", gap=0.5),
        Line("director", "And the source?", gap=0.4),
        Line("analyst", "A salvager. Rank F."),
    ], pre=0.9, post=0.6, music="fl_bureau", amb={"tunnel": 0.0, "room": 0.8}),
    Shot("id_glitch", s_id_glitch, [
        Line("director", "Find him. Before anyone else does.", at=1.6),
    ], pre=1.6, post=1.2, sfx=[(1.2, "glitch", 0.8, 0.0)]),
    # --- ENDING --------------------------------------------------------------
    Shot("ed", s_ed, [], min_dur=30.0, music="fl_ed", amb={"room": 0.0, "city": 0.35}),
    Shot("preview", s_preview, [
        Line("kai", "Next time on Faultline: The Unranked. Everyone wants to know what I am. Yeah... me too."),
    ], pre=0.8, post=1.0, music="fl_op", amb={"city": 0.0}, sfx=[(0.0, "impact", 0.5, 0.0)]),
    Shot("end", s_end, [], min_dur=3.2, music="-"),
]

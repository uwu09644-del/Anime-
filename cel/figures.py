"""Cel characters with natural (about 7.5-head) proportions for the painted-background look.

Kai and Hana from FAULTLINE, redrawn the way TV anime frames people: thin colour-traced
line art, flat fills, one hard shadow tone, a rim light from the scene's light source.

Units for full figures: 1000 = full height, origin at the feet, y negative = up.
"""
import math

import skia

from gfx import (Saved, difference, draw_text, fill, font, intersect, linear, lock, mix, oval, poly_path, rgb,
                 smooth_path, stroke, union)

SKIN = "#f1d2bd"
SKIN_SH = "#c4927f"
SKIN_LINE = "#7a4438"


def shifted(path, dx, dy):
    p = skia.Path(path)
    m = skia.Matrix()
    m.setTranslate(dx, dy)
    p.transform(m)
    return p


class Cel:
    """Draws parts as flat cel paint with a hard shadow, optional rim light and thin line."""

    def __init__(self, c, light=(1.0, -0.25), lw=2.0, backlit=False, ambient="#1a2036", amb_k=0.5,
                 rim_col="#ffc27a", rim_w=6.0, shade_w=18.0, scale=1.0):
        n = math.hypot(*light) or 1.0
        self.c, self.lx, self.ly = c, light[0] / n, light[1] / n
        self.lw = lw / scale            # line width in local units
        self.backlit, self.ambient, self.amb_k = backlit, ambient, amb_k
        self.rim_col, self.rim_w, self.shade_w = rim_col, rim_w / scale, shade_w / scale
        self.sil = []

    def tones(self, base, shade=None):
        sh = shade or mix(mix(base, "#000000", 0.38), self.ambient, 0.22)
        if self.backlit:
            lit = mix(base, self.ambient, self.amb_k * 0.55)
            lit = mix(lit, "#000000", 0.22)
            sh = mix(mix(base, "#000000", 0.62), self.ambient, self.amb_k * 0.7)
            return lit, sh
        return base, sh

    def part(self, path, base, shade=None, line=None, rim=True, band=True, extra=None, inner=None, sil=True,
             shade_w=None, lw=None):
        c = self.c
        lit, sh = self.tones(base, shade)
        if self.backlit:
            # mostly in shadow; a strip of half-light on the light side
            c.drawPath(path, fill(rgb(sh)))
            if band:
                w = (shade_w or self.shade_w) * 1.3
                c.drawPath(difference(path, shifted(path, -self.lx * w, -self.ly * w)), fill(rgb(lit)))
        else:
            c.drawPath(path, fill(rgb(lit)))
            if band:
                w = shade_w or self.shade_w
                c.drawPath(difference(path, shifted(path, self.lx * w, self.ly * w)), fill(rgb(sh)))
        if extra:
            with Saved(c):
                c.clipPath(path, doAntiAlias=True)
                for e in extra:
                    c.drawPath(e, fill(rgb(sh)))
        lc = line or mix(sh, "#000000", 0.55)
        if inner:
            with Saved(c):
                c.clipPath(path, doAntiAlias=True)
                for ln in inner:
                    c.drawPath(ln, stroke(rgb(lc), (lw or self.lw) * 0.8))
        c.drawPath(path, stroke(rgb(lc), lw or self.lw))
        if sil:
            self.sil.append(path)

    def silhouette(self):
        return union(*self.sil) if self.sil else skia.Path()

    def rim(self, alpha=0.9, w=None):
        """Thin rim light on the outer contour only, on the side facing the light."""
        sil = self.silhouette()
        w = w or self.rim_w
        band = difference(sil, shifted(sil, -self.lx * w, -self.ly * w))
        self.c.drawPath(band, fill(rgb(self.rim_col), alpha))
        self.c.drawPath(sil, stroke(rgb("#0a0810"), self.lw * 0.9))


def curve(pts):
    return smooth_path(pts, closed=False)


def mirror(pts):
    return [(-x, y) for x, y in reversed(pts)]


# ======================================================================
#  KAI - back view, standing
# ======================================================================
def kai_back(c, x, y, px_height, light=(1.0, -0.25), backlit=True, rim_col="#ffc27a", ambient="#1a2036",
             head_turn=0.0):
    s = px_height / 1000.0
    cel = Cel(c, light, 2.0, backlit, ambient, rim_col=rim_col, scale=s)
    with Saved(c):
        c.translate(x, y)
        c.scale(s, s)
        pants, boots, hood, vest, band_c, hair = "#2b3350", "#3a2c26", "#6f7482", "#f08a24", "#dfe3ea", "#4a2c1e"
        # legs
        legL = [(-88, -520), (-86, -400), (-76, -270), (-72, -150), (-64, -36), (-18, -36), (-22, -150), (-20, -270),
                (-8, -440), (-2, -505)]
        legR = [(2, -505), (8, -440), (22, -270), (26, -150), (24, -36), (70, -36), (76, -150), (78, -270),
                (88, -400), (90, -520)]
        for pts, sgn in ((legL, -1), (legR, 1)):
            p = smooth_path(pts, tension=0.6)
            folds = [curve([(sgn * 70, -280), (sgn * 48, -268), (sgn * 26, -278)]),
                     curve([(sgn * 66, -70), (sgn * 44, -58), (sgn * 24, -66)]),
                     curve([(sgn * 62, -96), (sgn * 46, -88)])]
            cel.part(p, pants, inner=folds)
            b = smooth_path([(sgn * 20, -42), (sgn * 70, -42), (sgn * 76, -12), (sgn * 70, 0), (sgn * 16, 0),
                             (sgn * 12, -14)], tension=0.6)
            cel.part(b, boots)
        # arms (behind the torso edge)
        armL = [(-122, -806), (-146, -724), (-158, -640), (-150, -560), (-134, -494), (-104, -500), (-116, -566),
                (-120, -640), (-106, -730), (-98, -790)]
        armR = [(122, -806), (142, -722), (148, -640), (152, -560), (150, -486), (120, -486), (120, -560),
                (112, -640), (104, -730), (98, -790)]
        for pts, sgn, hx_ in ((armL, -1, -119), (armR, 1, 135)):
            p = smooth_path(pts, tension=0.6)
            folds = [curve([(sgn * 152, -640), (sgn * 134, -630), (sgn * 116, -640)]),
                     curve([(sgn * 146, -612), (sgn * 128, -604)])]
            cel.part(p, hood, inner=folds)
            g = smooth_path([(hx_ - 15, -496), (hx_ - 19, -458), (hx_ - 10, -428), (hx_ + 8, -424), (hx_ + 17, -446),
                             (hx_ + 15, -496)], tension=0.7)
            cel.part(g, "#b08a58", inner=[curve([(hx_ + 4, -432), (hx_ + 2, -454)])])
        # hoodie body
        torso = smooth_path([(-36, -852), (-82, -838), (-120, -806), (-112, -700), (-96, -600), (-96, -498),
                             (96, -498), (96, -600), (112, -700), (120, -806), (82, -838), (36, -852)], tension=0.6)
        cel.part(torso, hood, inner=[curve([(-94, -520), (0, -512), (94, -520)])])
        # hi-vis vest with reflective tape
        vestp = smooth_path([(-30, -850), (-70, -842), (-102, -812), (-100, -720), (-93, -600), (-93, -530),
                             (93, -530), (93, -600), (100, -720), (102, -812), (70, -842), (30, -850)], tension=0.5)
        cel.part(vestp, vest, band=True)
        with Saved(c):
            c.clipPath(vestp, doAntiAlias=True)
            lit, sh = cel.tones(band_c)
            tape = [skia.Rect.MakeLTRB(-110, -642, 110, -614), skia.Rect.MakeLTRB(-64, -860, -42, -530),
                    skia.Rect.MakeLTRB(42, -860, 64, -530)]
            for r in tape:
                c.drawRect(r, fill(rgb(lit)))
                c.drawRect(r, stroke(rgb(mix(sh, "#000000", 0.5)), cel.lw * 0.6))
            draw_text(c, "SALVAGE", 0, -700, font("DelaGothicOne-Latin.ttf", 27), "#141824", 0.85)
        c.drawPath(vestp, stroke(rgb(mix(vest, "#000000", 0.72)), cel.lw))
        # hood bunched at the neck
        hoodp = smooth_path([(-30, -864), (-58, -854), (-66, -818), (-44, -782), (0, -764), (44, -782), (66, -818),
                             (58, -854), (30, -864)], tension=0.7)
        cel.part(hoodp, mix(hood, "#000000", 0.08), inner=[curve([(0, -862), (-4, -810), (0, -768)]),
                                                           curve([(-40, -846), (-30, -806)]),
                                                           curve([(40, -846), (30, -806)])])
        # neck, ears
        tx = head_turn * 10
        c.save()
        c.translate(0, -860)
        c.scale(1.13, 1.13)
        c.translate(0, 860)
        neck = poly_path([(-23, -900), (23, -900), (26, -846), (-26, -846)])
        c.drawPath(neck, fill(rgb(cel.tones(SKIN, SKIN_SH)[1])))
        for sgn in (-1, 1):
            ear = oval(sgn * 60 + tx, -926, 9, 17)
            cel.part(ear, SKIN, SKIN_SH, SKIN_LINE)
        if head_turn > 0:  # sliver of cheek and jaw on the right
            cheek = smooth_path([(52, -948), (70, -940), (76, -912), (66, -888), (48, -878), (40, -900)], tension=0.7)
            cel.part(cheek, SKIN, SKIN_SH, SKIN_LINE)
        # hair: spiky back view
        hp = [(-64, -906), (-57, -884), (-47, -898), (-37, -870), (-23, -890), (-9, -866), (4, -888), (18, -868),
              (30, -892), (42, -874), (52, -898), (62, -882), (66, -916), (71, -950), (64, -984), (76, -1002),
              (53, -1003), (49, -1024), (25, -1011), (11, -1032), (-8, -1013), (-28, -1028), (-40, -1006),
              (-63, -1012), (-60, -984), (-73, -962), (-66, -930)]
        hairp = smooth_path(hp, tension=0.35)
        strands = [curve([(0, -996), (-14, -940), (-23, -892)]), curve([(4, -996), (8, -936), (4, -890)]),
                   curve([(10, -994), (30, -940), (30, -894)]), curve([(-8, -994), (-38, -946), (-46, -900)]),
                   curve([(16, -990), (50, -948), (52, -900)]), curve([(-30, -1010), (-52, -970), (-62, -932)])]
        lowshade = poly_path([(-80, -925), (-50, -938), (-20, -922), (10, -940), (40, -924), (80, -936), (80, -860),
                              (-80, -860)])
        cel.part(hairp, hair, line="#160c08", inner=strands, extra=[lowshade], shade_w=10 / 1.0)
        c.restore()
        cel.sil.append(shifted(hairp, 0, -14))
        cel.rim()
    return cel


# ======================================================================
#  HANA - back view, standing, hand near her sword
# ======================================================================
def hana_back(c, x, y, px_height, light=(1.0, -0.25), backlit=True, rim_col="#ffc27a", ambient="#1a2036", sway=0.0):
    s = px_height / 1000.0
    cel = Cel(c, light, 2.0, backlit, ambient, rim_col=rim_col, scale=s)
    with Saved(c):
        c.translate(x, y)
        c.scale(s, s)
        coat, boot, hair, crim, silver = "#2c2836", "#1c1820", "#1c1a24", "#b01c34", "#c9cedb"
        # scabbard behind the left hip
        scab = poly_path([(-70, -566), (-84, -548), (-214, -446), (-204, -432)])
        cel.part(scab, "#5a1420", band=False)
        cel.part(poly_path([(-70, -566), (-84, -548), (-98, -560), (-84, -578)]), "#c9a040", band=False)
        # legs / boots under the coat hem
        for sgn in (-1, 1):
            leg = smooth_path([(sgn * 12, -340), (sgn * 56, -340), (sgn * 52, -200), (sgn * 48, -46), (sgn * 16, -46),
                               (sgn * 14, -200)], tension=0.6)
            cel.part(leg, boot, inner=[curve([(sgn * 54, -262), (sgn * 34, -254), (sgn * 12, -262)])])
            ft = smooth_path([(sgn * 14, -50), (sgn * 50, -50), (sgn * 56, -14), (sgn * 50, 0), (sgn * 12, 0),
                              (sgn * 10, -14)], tension=0.6)
            cel.part(ft, boot)
        # arms
        armL = [(-98, -818), (-118, -736), (-132, -654), (-118, -590), (-92, -556), (-76, -574), (-98, -606),
                (-104, -660), (-90, -740), (-82, -790)]        # left hand resting on the hilt
        armR = [(98, -818), (114, -730), (122, -650), (124, -570), (120, -504), (96, -504), (98, -570),
                (92, -650), (86, -740), (82, -790)]
        for pts, sgn, hand in ((armL, -1, [(-92, -558), (-80, -540), (-66, -548), (-66, -566), (-78, -576)]),
                               (armR, 1, [(120, -505), (123, -474), (115, -450), (103, -449), (95, -470), (96, -505)])):
            p = smooth_path(pts, tension=0.6)
            cel.part(p, coat, inner=[curve([(sgn * 128, -654), (sgn * 112, -644), (sgn * 96, -654)])])
            cel.part(smooth_path(hand, tension=0.7), "#d8b09a", "#8a6458", SKIN_LINE)
        # coat: fitted waist, flared hem with a centre vent
        sw = sway * 14
        coatp = smooth_path([(-30, -868), (-70, -846), (-99, -818), (-90, -740), (-63, -622), (-84, -520),
                             (-120 + sw, -326), (-78 + sw, -306), (-38 + sw, -318), (-6 + sw * 0.5, -300),
                             (6 + sw * 0.5, -300), (38 + sw, -318), (78 + sw, -306), (120 + sw, -326), (84, -520),
                             (63, -622), (90, -740), (99, -818), (70, -846), (30, -868)], tension=0.55)
        vent = poly_path([(0, -480), (-12 + sw * 0.5, -296), (12 + sw * 0.5, -296)])
        folds = [curve([(-60, -610), (-40, -500), (-60 + sw, -330)]), curve([(60, -610), (40, -500), (60 + sw, -330)]),
                 curve([(-20, -600), (-24, -480)]), curve([(22, -600), (26, -480)])]
        cel.part(coatp, coat, inner=folds)
        with Saved(c):
            c.clipPath(coatp, doAntiAlias=True)
            c.drawPath(vent, fill(rgb(mix(crim, "#000000", 0.45 if backlit else 0.1))))
            c.drawRect(skia.Rect.MakeLTRB(-110, -642, 110, -618), fill(rgb(mix(coat, "#000000", 0.45))))
            c.drawLine(-110, -642, 110, -642, stroke(rgb("#0a0810"), cel.lw * 0.7))
            c.drawLine(-110, -618, 110, -618, stroke(rgb("#0a0810"), cel.lw * 0.7))
        # shoulder plate (her right shoulder = screen right from behind)
        plate = smooth_path([(58, -852), (100, -840), (126, -802), (114, -770), (84, -792), (56, -814)], tension=0.6)
        cel.part(plate, silver, inner=[curve([(66, -836), (96, -818), (112, -790)])])
        # stand collar with crimson piping
        col = smooth_path([(-36, -846), (-40, -886), (-20, -896), (20, -896), (40, -886), (36, -846)], tension=0.6)
        cel.part(col, coat)
        c.drawPath(curve([(-40, -886), (-20, -896), (20, -896), (40, -886)]),
                   stroke(rgb(mix(crim, "#000000", 0.3 if backlit else 0)), cel.lw * 1.6))
        # head
        for sgn in (-1, 1):
            cel.part(oval(sgn * 59, -928, 8, 16), SKIN, SKIN_SH, SKIN_LINE)
        cap = smooth_path([(-58, -900), (-64, -940), (-56, -980), (-30, -1004), (0, -1010), (30, -1004), (56, -980),
                           (64, -940), (58, -900), (40, -880), (14, -872), (-14, -872), (-40, -880)], tension=0.8)
        pulls = [curve([(-56, -912), (-34, -960), (-6, -992)]), curve([(56, -912), (34, -960), (6, -992)]),
                 curve([(-36, -884), (-20, -940), (-2, -990)]), curve([(36, -884), (20, -940), (2, -990)]),
                 curve([(0, -874), (0, -990)])]
        cel.part(cap, hair, line="#07060a", inner=pulls)
        # ponytail
        ps = sway * 20
        tail = smooth_path([(-14, -976), (-19, -998), (-4, -1010), (13, -1007), (22, -990), (20, -950),
                            (27 + ps * 0.3, -890), (23 + ps * 0.6, -820), (29 + ps, -752), (19 + ps, -704),
                            (7 + ps, -672), (-4 + ps, -708), (-12 + ps * 0.8, -770), (-8 + ps * 0.5, -838),
                            (-16 + ps * 0.2, -898), (-13, -950)], tension=0.8)
        cel.part(tail, hair, line="#07060a", inner=[curve([(4, -1020), (8, -900), (2 + ps * 0.5, -780), (14 + ps, -640)]),
                                                    curve([(16, -1010), (22, -900), (18 + ps * 0.5, -760),
                                                           (28 + ps, -660)])])
        with Saved(c):
            c.clipPath(tail, doAntiAlias=True)
            c.drawRect(skia.Rect.MakeLTRB(-60, -770, 90, -640), fill(0, shader=linear(
                (0, -770), (0, -680), [rgb(crim, 0), rgb(mix(crim, "#000000", 0.35 if backlit else 0.0), 0.95)])))
        c.drawPath(tail, stroke(rgb("#07060a"), cel.lw))
        tie = smooth_path([(-16, -976), (-5, -985), (13, -982), (22, -972), (8, -966), (-12, -968)], tension=0.7)
        cel.part(tie, crim, band=False)
        cel.rim()
    return cel


def cast_shadow(c, cel_fn, x, y, kx=-0.45, ky=0.42, alpha=0.55, blur=5.0, color="#05060c"):
    """Project a figure's silhouette onto the floor. cel_fn(canvas) must draw the figure at (0,0)
    and return its Cel; we only use the silhouette."""
    rec = skia.PictureRecorder()
    rc = rec.beginRecording(skia.Rect.MakeWH(10, 10))
    cel = cel_fn(rc)
    rec.finishRecordingAsPicture()
    sil = cel.silhouette()
    return sil


# ======================================================================
#  HANA - three-quarter view bust (facing screen-left)
# ======================================================================
def hana_34(c, x, y, scale, light=(-1.0, -0.3), rim_col="#ffc27a", ambient="#1a2036", mouth=0.0, blink=0.0,
            look=(0.0, 0.0), brow=0.0, smile=0.0, sway=0.0):
    """Origin = between the eyes. Head is ~270 units tall."""
    cel = Cel(c, light, 2.1, False, ambient, rim_col=rim_col, rim_w=0, shade_w=14, scale=scale)
    lw = cel.lw
    coat, hair, crim, silver = "#2c2836", "#1c1a24", "#b01c34", "#c9cedb"
    with Saved(c):
        c.translate(x, y)
        c.scale(scale, scale)
        # ---- ponytail behind everything
        ps = sway * 16
        tail = smooth_path([(70, -150), (120, -176), (170, -150), (200, -90), (214 + ps * 0.3, 0), (206 + ps * 0.6, 100),
                            (186 + ps, 200), (150 + ps, 270), (136 + ps, 216), (150 + ps * 0.6, 120),
                            (150 + ps * 0.3, 30), (132, -50), (100, -100)], tension=0.8)
        cel.part(tail, hair, line="#07060a", rim=False,
                 inner=[curve([(110, -150), (170, -80), (180 + ps * 0.4, 40), (160 + ps, 200)]),
                        curve([(100, -120), (150, -60), (164 + ps * 0.4, 60), (150 + ps, 180)])])
        with Saved(c):
            c.clipPath(tail, doAntiAlias=True)
            c.drawRect(skia.Rect.MakeLTRB(60, 90, 280, 290), fill(0, shader=linear(
                (0, 100), (0, 250), [rgb(crim, 0), rgb(crim, 0.95)])))
        c.drawPath(tail, stroke(rgb("#07060a"), lw))
        # back hair mass behind the neck
        back = smooth_path([(40, -120), (118, -70), (122, 20), (108, 90), (84, 130), (44, 120), (30, 40)], tension=0.8)
        cel.part(back, mix(hair, "#000000", 0.25), line="#07060a", rim=False, band=False)

        # ---- body: coat, collar, shoulder plate
        body = smooth_path([(-40, 170), (-104, 200), (-150, 244), (-172, 330), (-178, 640), (236, 640), (226, 350),
                            (200, 262), (142, 212), (78, 178)], tension=0.7)
        cel.part(body, coat, inner=[curve([(150, 230), (170, 330), (168, 460)]), curve([(-150, 250), (-160, 360)]),
                                    curve([(20, 250), (24, 640)])])
        lining = poly_path([(-22, 150), (26, 140), (36, 246), (-28, 240)])
        c.drawPath(lining, fill(rgb(mix(crim, "#000000", 0.25))))
        # neck
        neck = poly_path([(-6, 100), (58, 62), (74, 206), (-14, 206)])
        cel.part(neck, SKIN, SKIN_SH, SKIN_LINE, rim=False, band=False, sil=False,
                 extra=[smooth_path([(-10, 96), (60, 56), (76, 130), (30, 150), (0, 136)], tension=0.6)])
        colN = smooth_path([(22, 118), (86, 150), (100, 226), (42, 240), (10, 184)], tension=0.5)
        colF = smooth_path([(-26, 126), (-58, 150), (-66, 222), (-30, 234), (-12, 182)], tension=0.5)
        cel.part(colF, coat)
        cel.part(colN, coat)
        for pth in (curve([(22, 118), (86, 150), (100, 226)]), curve([(-26, 126), (-58, 150), (-66, 222)])):
            c.drawPath(pth, stroke(rgb(crim), lw * 1.5))
        clasp = skia.Rect.MakeXYWH(-4, 236, 34, 14)
        c.drawRoundRect(clasp, 4, 4, fill(rgb(silver)))
        c.drawRoundRect(clasp, 4, 4, stroke(rgb("#3a3c48"), lw * 0.8))
        plate = smooth_path([(-84, 194), (-140, 212), (-178, 262), (-166, 298), (-120, 262), (-80, 232)], tension=0.6)
        cel.part(plate, silver, inner=[curve([(-96, 210), (-136, 232), (-164, 276)])])

        # ---- face
        face = smooth_path([(-70, -70), (-81, -30), (-75, -4), (-79, 26), (-71, 58), (-51, 92), (-31, 113),
                            (-10, 119), (20, 105), (52, 77), (68, 40), (76, 0), (72, -60), (20, -112), (-40, -102)],
                           tension=0.8)
        side_plane = smooth_path([(86, -90), (52, -44), (40, 20), (34, 60), (10, 112), (40, 110), (90, 60)],
                                 tension=0.7)
        bang_sh = poly_path([(-90, -120), (90, -120), (90, -26), (62, -18), (40, -34), (20, -14), (-6, -30),
                             (-30, -12), (-52, -28), (-70, -14), (-90, -24)])
        nose_sh = smooth_path([(-43, 40), (-37, 46), (-40, 53), (-46, 51)], tension=0.6)
        cel.part(face, SKIN, SKIN_SH, SKIN_LINE, rim=False, band=False, extra=[side_plane, bang_sh, nose_sh])
        ear = smooth_path([(70, -16), (90, -20), (99, 2), (94, 32), (80, 44), (70, 30)], tension=0.8)
        cel.part(ear, SKIN, SKIN_SH, SKIN_LINE, rim=False, band=False,
                 extra=[smooth_path([(76, -8), (90, -6), (92, 24), (80, 34)], tension=0.7)])
        c.drawCircle(84, 50, 5, fill(rgb("#e03048")))
        # eyes
        op = max(0.0, 1 - blink)

        def eye(cx, cy, w, h, iw, ih, far):
            # upper lid / lower lid as curves relative to centre
            k = -1 if far else 1
            up = [(cx - w * (0.5 if not far else 0.5), cy + 2), (cx - w * 0.2, cy - h * 0.5 * op),
                  (cx + w * 0.2, cy - h * 0.55 * op), (cx + w * 0.5, cy - h * 0.05)]
            lo = [(cx + w * 0.46, cy + 3), (cx + w * 0.15, cy + h * 0.45 * op), (cx - w * 0.2, cy + h * 0.42 * op),
                  (cx - w * 0.5, cy + 3)]
            if op < 0.2:
                c.drawPath(curve([(cx - w * 0.5, cy + 2), (cx, cy + 5), (cx + w * 0.5, cy + 1)]),
                           stroke(rgb("#0c0a10"), lw * 1.7))
                return
            white = smooth_path(up + lo, tension=0.8)
            c.drawPath(white, fill(rgb("#f6f1ee")))
            with Saved(c):
                c.clipPath(white, doAntiAlias=True)
                ix, iy = cx + look[0] * w * 0.12 - (2 if far else 0), cy + 1 + look[1] * 3
                c.drawPath(oval(ix, iy, iw, ih), fill(0, shader=linear((ix, iy - ih), (ix, iy + ih),
                           [rgb("#3a0812"), rgb("#8a1626"), rgb("#f05a66")], [0, 0.45, 1])))
                c.drawPath(oval(ix, iy + 1, iw * 0.42, ih * 0.5), fill(rgb("#14060a")))
                c.drawPath(oval(ix, iy, iw, ih), stroke(rgb("#1c080c"), lw * 0.6))
                c.drawPath(smooth_path([(cx - w, cy - h), (cx + w, cy - h), (cx + w, cy - h * 0.12),
                                        (cx - w, cy - h * 0.05)]), fill(rgb("#3a2030"), 0.35))
                c.drawCircle(ix - iw * 0.4, iy - ih * 0.42, max(1.6, iw * 0.24), fill(rgb("#ffffff")))
            c.drawPath(curve(up), stroke(rgb("#0c0a10"), lw * 1.9))
            ox, oy = up[-1] if not far else up[0]
            if not far:
                c.drawLine(ox, oy, ox + 7, oy - 5, stroke(rgb("#0c0a10"), lw * 1.3))
            c.drawPath(curve(lo[1:3]), stroke(rgb(SKIN_LINE), lw * 0.7))
            c.drawPath(curve([(up[1][0], up[1][1] - 6), (up[2][0] + 2, up[2][1] - 6)]),
                       stroke(rgb(SKIN_LINE), lw * 0.6))

        eye(8, 6, 46, 20, 10.5, 12.0, False)
        eye(-58, 5, 29, 18, 7.2, 11.0, True)
        # brows
        by = -24 - brow * 4
        for pts in ([(-20, by + 4 + brow * 3), (2, by - 5), (32, by)], [(-77, by + 3), (-63, by - 5), (-45, by + 3 + brow * 3)]):
            c.drawPath(curve(pts), stroke(rgb("#18141c"), lw * 1.5))
        # nose, mouth
        c.drawPath(curve([(-41, 22), (-49, 44), (-42, 50)]), stroke(rgb(SKIN_LINE), lw * 0.9))
        if mouth < 0.12:
            c.drawPath(curve([(-58, 76 - smile * 3), (-44, 79 + smile * 2), (-27, 76 - smile * 3)]),
                       stroke(rgb(SKIN_LINE), lw))
        else:
            mh = 4 + 14 * mouth
            mp = smooth_path([(-58, 75), (-44, 73), (-28, 75), (-34, 76 + mh), (-46, 78 + mh)], tension=0.7)
            c.drawPath(mp, fill(rgb("#6a1c26")))
            with Saved(c):
                c.clipPath(mp, doAntiAlias=True)
                c.drawRect(skia.Rect.MakeLTRB(-60, 72, -26, 77), fill(rgb("#f4eeea")))
            c.drawPath(mp, stroke(rgb(SKIN_LINE), lw * 0.8))
        c.drawPath(curve([(-50, 90), (-38, 91)]), stroke(rgb(SKIN_LINE), lw * 0.5))
        # jaw line emphasis (near side) is the face outline already

        # ---- hair: cap + bangs + side lock
        sw = sway * 5
        cap = smooth_path([(-80, -66), (-88, -104), (-66, -146), (-10, -168), (58, -160), (106, -116), (122, -50),
                           (116, 10), (98, 44), (86, -30), (60, -84), (10, -108), (-40, -102)], tension=0.8)
        locks = [
            cap,
            lock((-88, -86), (-58, -114), (-72 + sw, -6), -4, 0.4),
            lock((-66, -112), (-28, -122), (-44 + sw, -12), 0, 0.45),
            lock((-36, -122), (10, -122), (-12 + sw, -22), 4, 0.45),
            lock((0, -122), (48, -110), (30 + sw, -12), 8, 0.45),
            lock((34, -112), (74, -84), (60 + sw, -4), 8, 0.4),
            lock((58, -92), (92, -50), (66 + sw, 96), 6, 0.45),      # long lock in front of the ear
            lock((84, -60), (112, -20), (102 + sw, 60), 4, 0.4),
        ]
        mass = union(*locks)
        c.drawPath(mass, fill(rgb(hair)))
        with Saved(c):
            c.clipPath(mass, doAntiAlias=True)
            # shadow side of the head (away from the light) and a soft sheen band across the crown
            c.drawPath(smooth_path([(30, -180), (64, -120), (74, -40), (60, 30), (70, 120), (140, 120), (140, -180)],
                                   tension=0.8), fill(rgb("#000000"), 0.30))
            for (x0, x1) in ((-76, -46), (-36, 4), (14, 44)):      # broken sheen band, like brushed hair
                sheen = smooth_path([(x0, -100 - (x0 + 80) * 0.22), (x1, -112 - (x1 + 30) * 0.12 + abs(x1) * 0.1),
                                     (x1 - 2, -103 - (x1 + 30) * 0.12 + abs(x1) * 0.1), (x0 + 3, -90 - (x0 + 80) * 0.22)],
                                    tension=0.6)
                c.drawPath(sheen, fill(rgb("#3c3c58"), 0.9))
        for lk in locks[1:]:
            c.drawPath(lk, stroke(rgb("#07060a"), lw * 0.7))
        c.drawPath(mass, stroke(rgb("#07060a"), lw))
        # thin warm rim on the outer contour facing the light
        sil = union(mass, body, tail, face, plate, back, neck, colN, colF, ear)
        rimb = difference(sil, shifted(sil, 4.5, 2))
        c.drawPath(rimb, fill(rgb(rim_col), 0.8))
    return cel


# ======================================================================
#  KAI - out-of-focus foreground (back of head + shoulder), for over-the-shoulder shots
# ======================================================================
def kai_ots(c, x, y, scale, rim_col="#ffc27a", ambient="#1a2036"):
    with Saved(c):
        c.translate(x, y)
        c.scale(scale, scale)
        hair, hood, vest, band_c = "#3a2218", "#4c505c", "#b8641a", "#9aa0ac"
        sh = smooth_path([(-420, 700), (-380, 330), (-250, 250), (-60, 214), (120, 250), (300, 330), (360, 700)],
                         tension=0.7)
        c.drawPath(sh, fill(rgb(mix(hood, ambient, 0.35))))
        vestp = smooth_path([(-330, 700), (-300, 330), (-150, 262), (60, 262), (230, 330), (270, 700)], tension=0.6)
        c.drawPath(vestp, fill(rgb(mix(vest, ambient, 0.3))))
        c.drawRect(skia.Rect.MakeLTRB(-120, 262, -70, 700), fill(rgb(mix(band_c, ambient, 0.3))))
        c.drawRect(skia.Rect.MakeLTRB(80, 262, 130, 700), fill(rgb(mix(band_c, ambient, 0.3))))
        hoodp = smooth_path([(-170, 250), (-140, 170), (0, 150), (140, 176), (170, 250), (0, 300)], tension=0.8)
        c.drawPath(hoodp, fill(rgb(mix(hood, ambient, 0.45))))
        neck = poly_path([(-60, 80), (70, 80), (80, 190), (-70, 190)])
        c.drawPath(neck, fill(rgb(mix(SKIN_SH, ambient, 0.35))))
        ear = oval(128, -10, 22, 40)
        c.drawPath(ear, fill(rgb(mix(SKIN, ambient, 0.2))))
        hp = [(-150, 60), (-120, 110), (-90, 80), (-60, 130), (-20, 90), (10, 136), (50, 92), (84, 128), (110, 70),
              (140, 30), (150, -60), (136, -150), (170, -200), (110, -196), (100, -250), (40, -222), (0, -270),
              (-40, -226), (-100, -256), (-110, -200), (-170, -190), (-150, -120), (-176, -40)]
        c.drawPath(smooth_path(hp, tension=0.4), fill(rgb(mix(hair, ambient, 0.35))))
        whole = union(sh, smooth_path(hp, tension=0.4), ear)
        c.drawPath(difference(whole, shifted(whole, -10, 4)), fill(rgb(rim_col), 0.8))

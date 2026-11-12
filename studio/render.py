"""Build an episode: voices -> timeline -> audio mix -> frames -> MP4.

Usage:
    python studio/render.py                              # Starfall Keeper EP1 (module "ep01")
    python studio/render.py --show faultline.ep01        # FAULTLINE EP1
    python studio/render.py --show faultline.ep01 --shot-stills   # one PNG per shot
    python studio/render.py --stills 5,62,130            # PNG stills at those times (seconds)
    python studio/render.py --audio-only | --video-only
    python studio/render.py --jobs 4 --crf 20

An episode module must define SHOTS (and usually SUB_COLORS). Optional hooks:
    NAME, OUT, TITLE          build sub-folder, output path (relative to repo root), MP4 title
    VOICES, CUES, SFX, AMBIENCE, SFX_DUR, CUE_GAINS   merged into the audio engine
    VOICE_FX {speaker: fn(x)->x}, VOICE_REVERB {speaker: (wet, rt, tone)}
    POST(canvas, surface, tg, t, shot)   frame post-processing before subtitles
    SUB_FONT, SUB_OUTLINE, SUB_SIZE      subtitle styling
Set KOKORO_DIR to the folder holding kokoro-v1.0.onnx and voices-v1.0.bin.
"""
import argparse
import importlib
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from gfx import FPS, H, W, clamp, draw_text, font, letterbox, new_surface, rgb, screen_fade, wrap_text  # noqa: E402

SHOW = None
BUILD = os.path.join(ROOT, "build")


def load_show(name):
    """Import the episode module and wire its hooks into the audio engine."""
    global SHOW, BUILD
    import audio
    SHOW = importlib.import_module(name)
    sub = getattr(SHOW, "NAME", None)
    BUILD = os.path.join(ROOT, "build", sub) if sub else os.path.join(ROOT, "build")
    for attr in ("VOICES", "CUES", "SFX", "AMBIENCE"):
        extra = getattr(SHOW, attr, None)
        if extra:
            getattr(audio, attr).update(extra)
    return SHOW


def out_path():
    rel = getattr(SHOW, "OUT", os.path.join("episode01", "Starfall_Keeper_EP01.mp4"))
    return os.path.join(ROOT, rel)


# ======================================================================
#  timeline
# ======================================================================
def build_timeline():
    import audio
    vdir = os.path.join(BUILD, "voices")
    os.makedirs(vdir, exist_ok=True)
    t0 = 0.0
    shots, lines = [], []
    for si, sh in enumerate(SHOW.SHOTS):
        t = sh.pre
        end_last = 0.0
        sl = []
        for ln in sh.lines:
            x = audio.synth_line(ln.speaker, ln.text, vdir)
            dur = len(x) / audio.SR
            start = ln.at if ln.at is not None else t
            end = start + dur
            t = end + ln.gap
            end_last = max(end_last, end)
            env = audio.lip_envelope(x, FPS)
            rec = dict(shot=si, speaker=ln.speaker, text=ln.sub or ln.text, tts=ln.text, local_start=start,
                       start=t0 + start, dur=dur, env=env)
            sl.append(len(lines))
            lines.append(rec)
        dur = max(sh.min_dur, (end_last + sh.post) if sh.lines else sh.pre + sh.post)
        shots.append(dict(name=sh.name, start=t0, dur=dur, lines=sl, music=sh.music, amb=sh.amb,
                          sfx=sh.sfx, fade_in=sh.fade_in, fade_out=sh.fade_out, bars=sh.bars))
        t0 += dur
    tl = dict(total=t0, shots=shots, lines=lines, fps=FPS)
    os.makedirs(BUILD, exist_ok=True)
    with open(os.path.join(BUILD, "timeline.json"), "w") as f:
        json.dump(tl, f)
    print(f"timeline: {len(shots)} shots, {len(lines)} lines, {t0:.1f}s ({t0 / 60:.2f} min)")
    return tl


def load_timeline():
    with open(os.path.join(BUILD, "timeline.json")) as f:
        return json.load(f)


# ======================================================================
#  audio
# ======================================================================
def build_audio(tl):
    import audio as A
    L = tl["total"] + 1.0
    n = A.secs(L)
    t_start = time.time()
    vdir = os.path.join(BUILD, "voices")
    voice_fx = getattr(SHOW, "VOICE_FX", {})
    voice_rev = {"collector": (0.6, 3.0, 3000)}
    voice_rev.update(getattr(SHOW, "VOICE_REVERB", {}))

    # --- voices: one bus per reverb setting
    buses = {}
    for ln in tl["lines"]:
        x = A.synth_line(ln["speaker"], ln["tts"], vdir)
        if ln["speaker"] in voice_fx:
            x = voice_fx[ln["speaker"]](x)
        key = voice_rev.get(ln["speaker"], (0.14, 0.9, 6000))
        buses.setdefault(key, A.Bus(L)).add(ln["start"], x, 1.0, 0.0)
    voices = np.zeros((2, A.Bus(L).n))
    for (wet, rt, tone), bus in buses.items():
        voices += A.add_reverb(bus.buf, wet, rt, tone)
    print(f"  voices done {time.time() - t_start:.1f}s")

    # --- music cues
    music = A.Bus(L)
    gains = {"op": 0.62, "villain": 0.68, "ed": 0.85, "sting": 0.6, "tender": 0.66}
    gains.update(getattr(SHOW, "CUE_GAINS", {}))
    cues = [(s["start"], s["music"]) for s in tl["shots"] if s["music"]]
    cues.append((tl["total"], "-"))
    seen = set()
    for (st, name), (nx, _) in zip(cues, cues[1:]):
        if name == "-":
            continue
        ln = nx - st + 2.0
        if name in seen:  # a reprise ends hard at the next cue
            ln = nx - st
        seen.add(name)
        sig = A.CUES[name](ln)
        music.add(st, sig, gains.get(name, 0.6))
        print(f"  cue {name:10s} @ {st:6.1f}s len {ln:5.1f}s")

    # --- ambience with per-shot gains
    amb = A.Bus(L)
    state, curves = {}, {}
    for s in tl["shots"]:
        if s["amb"]:
            state.update(s["amb"])
        for k in A.AMBIENCE:
            curves.setdefault(k, []).append((s["start"], state.get(k, 0.0)))
    for k, pts in curves.items():
        if max(g for _, g in pts) <= 0:
            continue
        g = np.zeros(n)
        for (st, gv), nxt in zip(pts, pts[1:] + [(L, pts[-1][1])]):
            g[A.secs(st):A.secs(nxt[0])] = gv
        k_len = A.secs(0.8)
        g = np.convolve(g, np.ones(k_len) / k_len, mode="same")
        sig = A.AMBIENCE[k](L)
        amb.buf[:, :n] += sig[:, :n] * g[None, :]
    print(f"  ambience done {time.time() - t_start:.1f}s")

    # --- sfx
    sfx = A.Bus(L)
    sfx_dur = {"steps": A.sfx_steps}
    sfx_dur.update(getattr(SHOW, "SFX_DUR", {}))
    for s in tl["shots"]:
        for (off, name, gain, pan) in s["sfx"]:
            at = s["start"] + (off if off >= 0 else s["dur"] + off)
            sig = sfx_dur[name](s["dur"]) if name in sfx_dur else A.SFX[name]()
            sfx.add(at, sig, gain, pan)
    sfx_buf = A.add_reverb(sfx.buf, 0.25, 1.8)

    # --- ducking music under dialogue
    v_env = A.lp(np.abs(voices).max(axis=0), 3.0, 1)
    duck = 1.0 - 0.65 * np.clip(v_env * 6, 0, 1)
    mix = voices * 1.0 + music.buf * duck[None, :] + sfx_buf * 0.75 + amb.buf * 0.7
    mix = A.master(mix)
    os.makedirs(BUILD, exist_ok=True)
    path = os.path.join(BUILD, "audio.wav")
    A.write_wav(path, mix)
    print(f"audio: {path} ({time.time() - t_start:.1f}s)")
    return path


# ======================================================================
#  frames
# ======================================================================
class Ctx:
    def __init__(self, tl, si, tg):
        self.tl, self.si, self.tg = tl, si, tg
        self.shot = tl["shots"][si]
        self.lines = [tl["lines"][i] for i in self.shot["lines"]]

    def mouth(self, speaker, twos=False):
        tg = math.floor(self.tg * 12) / 12 if twos else self.tg
        for ln in self.lines:
            if ln["speaker"] == speaker and ln["start"] <= tg < ln["start"] + ln["dur"]:
                i = int((tg - ln["start"]) * FPS)
                env = ln["env"]
                return env[min(i, len(env) - 1)]
        return 0.0

    def line_start(self, i):
        return self.lines[i]["local_start"] if i < len(self.lines) else 0.0

    def line_end(self, i):
        return (self.lines[i]["local_start"] + self.lines[i]["dur"]) if i < len(self.lines) else 0.0

    def current_speaker(self):
        best = None
        for ln in self.lines:
            if ln["start"] - 0.2 <= self.tg:
                best = ln["speaker"]
        return best


_SUB_FONT = None


def draw_subtitles(c, tl, tg):
    global _SUB_FONT
    colors = getattr(SHOW, "SUB_COLORS", {})
    size = getattr(SHOW, "SUB_SIZE", 46)
    if _SUB_FONT is None:
        _SUB_FONT = font(getattr(SHOW, "SUB_FONT", "MPlusRounded1c-ExtraBold.ttf"), size)
    outline = getattr(SHOW, "SUB_OUTLINE", "#120e24")
    lh = size * 1.26
    for ln in tl["lines"]:
        if ln["start"] - 0.05 <= tg <= ln["start"] + ln["dur"] + 0.35:
            a = clamp(min((tg - ln["start"] + 0.05) / 0.12, (ln["start"] + ln["dur"] + 0.35 - tg) / 0.15))
            rows = wrap_text(ln["text"], _SUB_FONT, 1500)
            y = H - 62 - (len(rows) - 1) * lh
            for r in rows:
                draw_text(c, r, W / 2, y, _SUB_FONT, colors.get(ln["speaker"], "#ffffff"), a,
                          outline=outline, outline_w=9)
                y += lh


def render_frame(surf, tl, fi, shot_fns):
    c = surf.getCanvas()
    tg = fi / FPS
    shots = tl["shots"]
    si = 0
    for i, s in enumerate(shots):
        if s["start"] <= tg:
            si = i
    s = shots[si]
    t = tg - s["start"]
    c.clear(rgb("#000000"))
    c.save()
    shot_fns[si](c, t, s["dur"], Ctx(tl, si, tg))
    c.restore()
    if s["bars"]:
        letterbox(c, s["bars"])
    if s["fade_in"]:
        screen_fade(c, clamp(1 - t / s["fade_in"]))
    if s["fade_out"]:
        screen_fade(c, clamp(1 - (s["dur"] - t) / s["fade_out"]))
    post = getattr(SHOW, "POST", None)
    if post is not None:
        post(c, surf, tg, t, s)
    draw_subtitles(c, tl, tg)


def _worker(args):
    show, a, b, seg_path, crf = args
    load_show(show)
    tl = load_timeline()
    fns = [s.fn for s in SHOW.SHOTS]
    surf = new_surface()
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-tune", "animation",
           "-crf", str(crf), "-pix_fmt", "yuv420p", "-threads", "2", seg_path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for fi in range(a, b):
        render_frame(surf, tl, fi, fns)
        p.stdin.write(surf.makeImageSnapshot().toarray().tobytes())
        if (fi - a) % 240 == 0:
            el = time.time() - t0
            print(f"    [{a}-{b}] frame {fi} ({(fi - a) / max(el, 1e-6):.1f} fps)", flush=True)
    p.stdin.close()
    p.wait()
    return seg_path


def render_video(show, tl, jobs=4, crf=20):
    nframes = int(math.ceil(tl["total"] * FPS))
    segdir = os.path.join(BUILD, "segments")
    os.makedirs(segdir, exist_ok=True)
    for f in os.listdir(segdir):
        os.remove(os.path.join(segdir, f))
    nseg = jobs * 3
    bounds = [int(nframes * k / nseg) for k in range(nseg + 1)]
    tasks = [(show, bounds[k], bounds[k + 1], os.path.join(segdir, f"seg_{k:03d}.mp4"), crf) for k in range(nseg)]
    t0 = time.time()
    with mp.Pool(jobs) as pool:
        segs = pool.map(_worker, tasks, chunksize=1)
    print(f"frames: {nframes} in {time.time() - t0:.0f}s")
    lst = os.path.join(segdir, "list.txt")
    with open(lst, "w") as f:
        for s in segs:
            f.write(f"file '{s}'\n")
    vid = os.path.join(BUILD, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    vid], check=True)
    return vid


def mux(video, audio_path, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    title = getattr(SHOW, "TITLE", "Starfall Keeper - Episode 1: The Star in the Net")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", audio_path, "-map", "0:v", "-map",
                    "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                    "-metadata", f"title={title}", out], check=True)
    print(f"wrote {out}")


def render_stills(tl, times, outdir):
    import skia
    fns = [s.fn for s in SHOW.SHOTS]
    surf = new_surface()
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for tg in times:
        render_frame(surf, tl, int(tg * FPS), fns)
        p = os.path.join(outdir, f"still_{tg:07.2f}.png")
        surf.makeImageSnapshot().save(p, skia.kPNG)
        paths.append(p)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", default="ep01", help="episode module, e.g. ep01 or faultline.ep01")
    ap.add_argument("--stills", default=None)
    ap.add_argument("--stills-dir", default=None)
    ap.add_argument("--shot-stills", action="store_true", help="one still per shot")
    ap.add_argument("--audio-only", action="store_true")
    ap.add_argument("--video-only", action="store_true")
    ap.add_argument("--jobs", type=int, default=max(1, os.cpu_count() or 1))
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    load_show(args.show)
    stills_dir = args.stills_dir or os.path.join(BUILD, "stills")
    tl = build_timeline()
    if args.shot_stills:
        times = [s["start"] + s["dur"] * 0.6 for s in tl["shots"]]
        for p in render_stills(tl, times, stills_dir):
            print(p)
        return
    if args.stills:
        for p in render_stills(tl, [float(x) for x in args.stills.split(",")], stills_dir):
            print(p)
        return
    apath = os.path.join(BUILD, "audio.wav")
    if not args.video_only:
        apath = build_audio(tl)
    if args.audio_only:
        return
    vid = render_video(args.show, tl, args.jobs, args.crf)
    mux(vid, apath, args.out or out_path())


if __name__ == "__main__":
    main()

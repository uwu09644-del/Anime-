"""Build STARFALL KEEPER episode 1: voices -> timeline -> audio mix -> frames -> MP4.

Usage:
    python studio/render.py                 # full build -> episode01/Starfall_Keeper_EP01.mp4
    python studio/render.py --stills 5,62,130   # render PNG stills at those times (seconds)
    python studio/render.py --audio-only
    python studio/render.py --jobs 4 --crf 20
Set KOKORO_DIR to the folder holding kokoro-v1.0.onnx and voices-v1.0.bin.
"""
import argparse
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

import numpy as np  # noqa: E402

from gfx import FPS, H, W, clamp, draw_text, fill, font, letterbox, new_surface, rgb, screen_fade, wrap_text  # noqa: E402

BUILD = os.path.join(ROOT, "build")
OUT_DIR = os.path.join(ROOT, "episode01")


# ======================================================================
#  timeline
# ======================================================================
def build_timeline():
    import audio
    from ep01 import SHOTS
    vdir = os.path.join(BUILD, "voices")
    os.makedirs(vdir, exist_ok=True)
    t0 = 0.0
    shots, lines = [], []
    for si, sh in enumerate(SHOTS):
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

    # --- voices
    dry = A.Bus(L)
    wet_heavy = A.Bus(L)
    for ln in tl["lines"]:
        x = A.synth_line(ln["speaker"], ln["tts"], vdir)
        pan = 0.0
        if ln["speaker"] == "collector":
            wet_heavy.add(ln["start"], x, 1.0, pan)
        else:
            dry.add(ln["start"], x, 1.0, pan)
    voices = A.add_reverb(dry.buf, 0.14, 0.9, 6000) + A.add_reverb(wet_heavy.buf, 0.6, 3.0, 3000)
    print(f"  voices done {time.time() - t_start:.1f}s")

    # --- music cues
    music = A.Bus(L)
    cues = [(s["start"], s["music"]) for s in tl["shots"] if s["music"]]
    cues.append((tl["total"], "-"))
    for (st, name), (nx, _) in zip(cues, cues[1:]):
        if name == "-":
            continue
        ln = nx - st + 2.0
        if name == "op" and st > tl["total"] * 0.5:
            ln = nx - st
        sig = A.CUES[name](ln)
        gain = {"op": 0.62, "villain": 0.68, "ed": 0.85, "sting": 0.6, "tender": 0.66}.get(name, 0.6)
        music.add(st, sig, gain)
        print(f"  cue {name:8s} @ {st:6.1f}s len {ln:5.1f}s")

    # --- ambience with per-shot gains
    amb = A.Bus(L)
    state = {}
    curves = {}
    for s in tl["shots"]:
        if s["amb"]:
            state.update(s["amb"])
        for k in A.AMBIENCE:
            curves.setdefault(k, []).append((s["start"], state.get(k, 0.0)))
    for k, pts in curves.items():
        if max(g for _, g in pts) <= 0:
            continue
        times = np.arange(n) / A.SR
        g = np.zeros(n)
        for (st, gv), nxt in zip(pts, pts[1:] + [(L, pts[-1][1])]):
            a, b = A.secs(st), A.secs(nxt[0])
            g[a:b] = gv
        # smooth gain changes (~0.8 s)
        k_len = A.secs(0.8)
        g = np.convolve(g, np.ones(k_len) / k_len, mode="same")
        sig = A.AMBIENCE[k](L)
        amb.buf[:, :n] += sig[:, :n] * g[None, :]
        del times
    print(f"  ambience done {time.time() - t_start:.1f}s")

    # --- sfx
    sfx = A.Bus(L)
    for s in tl["shots"]:
        for (off, name, gain, pan) in s["sfx"]:
            at = s["start"] + (off if off >= 0 else s["dur"] + off)
            sig = A.sfx_steps(s["dur"]) if name == "steps" else A.SFX[name]()
            sfx.add(at, sig, gain, pan)
    sfx_buf = A.add_reverb(sfx.buf, 0.25, 1.8)

    # --- ducking music under dialogue
    v_env = np.abs(voices).max(axis=0)
    v_env = A.lp(v_env, 3.0, 1)
    duck = 1.0 - 0.65 * np.clip(v_env * 6, 0, 1)
    mix = voices * 1.0 + music.buf * duck[None, :] + sfx_buf * 0.75 + amb.buf * 0.7
    mix = A.master(mix)
    os.makedirs(BUILD, exist_ok=True)
    path = os.path.join(BUILD, "ep01_audio.wav")
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

    def mouth(self, speaker):
        for ln in self.lines:
            if ln["speaker"] == speaker and ln["start"] <= self.tg < ln["start"] + ln["dur"]:
                i = int((self.tg - ln["start"]) * FPS)
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


SUB_FONT = None


def draw_subtitles(c, tl, tg, bars):
    global SUB_FONT
    from ep01 import SUB_COLORS
    if SUB_FONT is None:
        SUB_FONT = font("MPlusRounded1c-ExtraBold.ttf", 46)
    for ln in tl["lines"]:
        if ln["start"] - 0.05 <= tg <= ln["start"] + ln["dur"] + 0.35:
            a = clamp(min((tg - ln["start"] + 0.05) / 0.12, (ln["start"] + ln["dur"] + 0.35 - tg) / 0.15))
            rows = wrap_text(ln["text"], SUB_FONT, 1500)
            y = H - 62 - (len(rows) - 1) * 58
            for r in rows:
                draw_text(c, r, W / 2, y, SUB_FONT, SUB_COLORS.get(ln["speaker"], "#ffffff"), a,
                          outline="#120e24", outline_w=9)
                y += 58


def render_frame(c, tl, fi, shot_fns):
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
    draw_subtitles(c, tl, tg, s["bars"])


def _worker(args):
    a, b, seg_path, crf = args
    from ep01 import SHOTS
    tl = load_timeline()
    fns = [s.fn for s in SHOTS]
    surf = new_surface()
    c = surf.getCanvas()
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-tune", "animation",
           "-crf", str(crf), "-pix_fmt", "yuv420p", "-threads", "2", seg_path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for fi in range(a, b):
        render_frame(c, tl, fi, fns)
        arr = surf.makeImageSnapshot().toarray()
        p.stdin.write(arr.tobytes())
        if (fi - a) % 240 == 0:
            el = time.time() - t0
            print(f"    [{a}-{b}] frame {fi} ({(fi - a) / max(el, 1e-6):.1f} fps)", flush=True)
    p.stdin.close()
    p.wait()
    return seg_path


def render_video(tl, jobs=4, crf=20):
    nframes = int(math.ceil(tl["total"] * FPS))
    segdir = os.path.join(BUILD, "segments")
    os.makedirs(segdir, exist_ok=True)
    nseg = jobs * 3
    bounds = [int(nframes * k / nseg) for k in range(nseg + 1)]
    tasks = [(bounds[k], bounds[k + 1], os.path.join(segdir, f"seg_{k:03d}.mp4"), crf) for k in range(nseg)]
    t0 = time.time()
    with mp.Pool(jobs) as pool:
        segs = pool.map(_worker, tasks, chunksize=1)
    print(f"frames: {nframes} in {time.time() - t0:.0f}s")
    lst = os.path.join(segdir, "list.txt")
    with open(lst, "w") as f:
        for s in segs:
            f.write(f"file '{s}'\n")
    vid = os.path.join(BUILD, "ep01_video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    vid], check=True)
    return vid


def mux(video, audio_path, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", audio_path, "-map", "0:v", "-map",
                    "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                    "-metadata", "title=Starfall Keeper - Episode 1: The Star in the Net", out], check=True)
    print(f"wrote {out}")


def render_stills(tl, times, outdir):
    import skia
    from ep01 import SHOTS
    fns = [s.fn for s in SHOTS]
    surf = new_surface()
    c = surf.getCanvas()
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for tg in times:
        fi = int(tg * FPS)
        render_frame(c, tl, fi, fns)
        p = os.path.join(outdir, f"still_{tg:07.2f}.png")
        surf.makeImageSnapshot().save(p, skia.kPNG)
        paths.append(p)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", default=None)
    ap.add_argument("--stills-dir", default=os.path.join(BUILD, "stills"))
    ap.add_argument("--shot-stills", action="store_true", help="one still per shot (middle)")
    ap.add_argument("--audio-only", action="store_true")
    ap.add_argument("--video-only", action="store_true")
    ap.add_argument("--jobs", type=int, default=max(1, os.cpu_count() or 1))
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "Starfall_Keeper_EP01.mp4"))
    args = ap.parse_args()

    tl = build_timeline()
    if args.shot_stills:
        times = [s["start"] + s["dur"] * 0.6 for s in tl["shots"]]
        for p in render_stills(tl, times, args.stills_dir):
            print(p)
        return
    if args.stills:
        for p in render_stills(tl, [float(x) for x in args.stills.split(",")], args.stills_dir):
            print(p)
        return
    apath = os.path.join(BUILD, "ep01_audio.wav")
    if not args.video_only:
        apath = build_audio(tl)
    if args.audio_only:
        return
    vid = render_video(tl, args.jobs, args.crf)
    mux(vid, apath, args.out)


if __name__ == "__main__":
    main()

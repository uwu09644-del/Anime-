---
name: anime-episode
description: Make a new STARFALL KEEPER anime episode (or any short anime) with this repo's code-only pipeline - script, Skia-drawn characters and backgrounds, Kokoro TTS voices with lip sync, synthesized music/SFX, rendered to a 1080p MP4. Use when asked to make, extend, re-render or fix an episode, add a character, or change the art, voices or music.
---

# Making an anime episode with the studio pipeline

Everything is free and runs locally: Python + skia-python (drawing), NumPy/SciPy (music and SFX),
Kokoro-82M (voices, Apache-2.0), FFmpeg (encoding). No paid APIs, no image models.

## 1. Set up (once per machine)

```bash
pip install -r requirements.txt
# Linux: Skia needs EGL even for CPU rendering
apt-get install -y libegl1 libgl1 espeak-ng ffmpeg
# Kokoro voice model (~350 MB) - kept out of git
mkdir -p models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

`KOKORO_DIR` overrides the model folder (default `models/`).

## 2. Where things live

| File | What it holds |
|---|---|
| `studio/gfx.py` | Skia helpers: smooth paths, `lock()` hair shapes, glows, sparkles, text, easing |
| `studio/characters.py` | `draw_mio`, `draw_lumi`, `draw_genzo`, `draw_collector`, `draw_figure`, and `Expr` (blink, mouth, smile, look, brow, blush, surprise, happy_eyes, sad, tear, glow, sway) |
| `studio/backgrounds.py` | night sky, sea, lighthouse, cliff, beach + net, interior, balcony, crimson sky, falling star |
| `studio/audio.py` | Kokoro voices + lip envelopes, synth instruments, music cues (`CUES`), SFX (`SFX`), ambience, reverb, mastering |
| `studio/ep01.py` | The episode: `Shot`/`Line` screenplay list `SHOTS` + one draw function per shot |
| `studio/render.py` | timeline -> audio mix -> parallel frame render -> MP4 |

## 3. Write a new episode

1. Copy `studio/ep01.py` to `studio/epNN.py`; keep the imports and helpers.
2. Write the script first as `episodeNN/SCRIPT.md`, then turn each beat into a `Shot`:
   - `Shot(name, fn, [Line(speaker, text)], pre, post, min_dur, music="cue", amb={...}, sfx=[(t, name, gain, pan)])`
   - Shot length is computed from the voiced lines; use `min_dur` for shots without dialogue.
   - `Line(..., sub="...")` shows different subtitle text than what is spoken (use it for shouts
     like "GRANDPAAA!" that TTS would mangle).
   - `music="-"` silences the score from that shot on.
3. Each draw function is `fn(c, t, d, ctx)`: `t` local time, `d` shot length.
   - Lip sync: `Expr(mouth=ctx.mouth("mio"))`. Blinks: `blink=blink(t, seed)`.
   - `ctx.line_start(i)` / `ctx.line_end(i)` time reactions to dialogue.
   - Night scenes: wrap characters in `with Saved(c, NIGHT()):`; interiors use `WARM()`.
   - Camera: `cam(c, zoom, cx, cy)` inside `with Saved(c):`; shake with `shake(t, amp)`.
4. Point `render.py` at the new module (`from epNN import SHOTS, SUB_COLORS`) and change the output name.

## 4. Check before the full render (do not skip)

```bash
python studio/render.py --shot-stills        # one PNG per shot in build/stills/
montage build/stills/still_*.png -tile 4x -geometry 480x270+4+4 build/sheet.png
```

Look at the contact sheet. Common problems: black edges when the camera zooms past a background
(draw backgrounds with oversized rects), text running off-frame, characters too dark under
`NIGHT()`.

## 5. Render

```bash
python studio/render.py --jobs 4 --crf 20     # -> episode01/Starfall_Keeper_EP01.mp4
python studio/render.py --audio-only          # iterate on the mix quickly
```

About 4 minutes of 1080p24 renders in ~10-15 minutes on 4 cores. Voices are cached in
`build/voices/` and only re-synthesized when a line's text changes.

## Style rules for this show

- Original characters only. Don't copy existing anime designs, names or logos.
- Anime look = clean dark line art (`lw_px` ~4 at close-up), cel shading, big eyes with two
  highlights, zig-zag hair highlight band, soft glows on light sources.
- Subtitle colours: Mio white, Lumi pale gold, Genzo pale blue, Collector pink.

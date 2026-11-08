"""Bildaufbau pro Frame und Video-Export (ffmpeg)."""
from __future__ import annotations

import json
import math
import os
import subprocess
import urllib.parse
import urllib.request
from datetime import date
from multiprocessing import get_context
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from . import brand as B
from .brand import W, H, FPS, font
from .gfx import (AA, Background, clamp, draw_footer, draw_header, draw_progress, ease_in_out_cubic,
                  ease_out_back, ease_out_cubic, fit_font, layer, paste_alpha, prog, rgba, tint_clip_frame)
from .scenes import DEFAULT_SOURCE, SCENES

TRANS = 0.20      # Ausblenden der alten Szene
IN_DELAY = 0.12   # neue Szene beginnt leicht versetzt


# ───────────────────────── Untertitel ─────────────────────────
def build_chunks(words, max_words=3, max_chars=20):
    chunks, cur = [], []
    for i, w in enumerate(words):
        if cur:
            gap = w["s"] - cur[-1]["e"]
            txt = " ".join(x["w"] for x in cur + [w])
            if len(cur) >= max_words or len(txt) > max_chars or gap > 0.38 or cur[-1]["w"][-1:] in ".,!?:;…":
                chunks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        end = chunks[i + 1][0]["s"] if i + 1 < len(chunks) else c[-1]["e"] + 0.5
        end = min(end, c[-1]["e"] + 0.6)
        out.append({"words": c, "s": c[0]["s"], "e": end})
    return out


def draw_captions(img: Image.Image, chunks, t):
    cur = None
    for c in chunks:
        if c["s"] - 0.04 <= t < c["e"]:
            cur = c
            break
    if not cur:
        return
    words = cur["words"]
    base = 64
    txt = " ".join(w["w"] for w in words)
    f = fit_font(txt, "Bold", B.CONTENT_W - 20, base, 40)
    pop = ease_out_back(prog(t, cur["s"] - 0.04, 0.16), 2.0)
    space = f.getlength(" ")
    widths = [f.getlength(w["w"]) for w in words]
    total = sum(widths) + space * (len(words) - 1)
    lay = layer(W, 160)
    d = ImageDraw.Draw(lay)
    x = B.CX - total / 2
    y = 80
    active = 0
    for i, w in enumerate(words):
        if t >= w["s"] - 0.02:
            active = i
    for i, (w, ww) in enumerate(zip(words, widths)):
        is_act = i == active
        col = B.VIO if is_act else B.INK
        lift = 0
        if is_act:
            lift = -6 * (1 - ease_out_cubic(prog(t, w["s"] - 0.02, 0.18)))
        d.text((x, y + lift), w["w"], font=f, fill=rgba(col), anchor="lm",
               stroke_width=7, stroke_fill=rgba(B.BG, .92))
        x += ww + space
    s = 0.92 + 0.08 * clamp(pop, 0, 1.1)
    if abs(s - 1) > 0.005:
        lw, lh = lay.size
        sc = lay.resize((int(lw * s), int(lh * s)), Image.BILINEAR)
        lay = layer(W, 160)
        lay.alpha_composite(sc, ((lw - sc.size[0]) // 2, (lh - sc.size[1]) // 2))
    paste_alpha(img, lay, (0, B.CAPTION_Y - 80), clamp(pop * 3))


# ───────────────────────── Medien (Pexels, optional) ─────────────────────────
def _pexels(path, params):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    url = f"https://api.pexels.com/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "boerse60/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def load_background_clip(query: str, cache: Path) -> Path | None:
    """Lädt einen frei nutzbaren Hintergrund-Clip (Pexels-Lizenz) und speichert ihn lila eingefärbt."""
    cache.mkdir(parents=True, exist_ok=True)
    npy = cache / f"bg_{abs(hash(query)) % 10**8}.npy"
    if npy.exists():
        return npy
    try:
        res = _pexels("videos/search", {"query": query, "orientation": "portrait", "per_page": 5, "size": "medium"})
    except Exception as e:
        print(f"  Hintergrund-Clip nicht geladen: {e}")
        return None
    if not res or not res.get("videos"):
        if res is None:
            print("  Hinweis: Ohne PEXELS_API_KEY nutzt das Video den animierten Marken-Hintergrund.")
        return None
    v = res["videos"][0]
    files = sorted([f for f in v["video_files"] if f.get("width") and f["width"] <= 1080],
                   key=lambda f: -f["width"]) or v["video_files"]
    mp4 = cache / "bg_tmp.mp4"
    urllib.request.urlretrieve(files[0]["link"], mp4)
    cap = cv2.VideoCapture(str(mp4))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(round(src_fps / 12)))
    frames, i = [], 0
    while len(frames) < 12 * 12:
        ok, fr = cap.read()
        if not ok:
            break
        if i % step == 0:
            frames.append(tint_clip_frame(fr))
        i += 1
    cap.release()
    mp4.unlink(missing_ok=True)
    if not frames:
        return None
    frames += frames[::-1]  # nahtlose Schleife
    np.save(npy, np.stack(frames))
    print(f"  Hintergrund-Clip: Pexels / {v.get('user', {}).get('name', '')}")
    return npy


def load_image(sz: dict, base_dir: Path, cache: Path):
    """Vordergrund-Bild (nicht eingefärbt): lokaler Pfad oder Pexels-Fotosuche."""
    if sz.get("bild"):
        p = (base_dir / sz["bild"]).resolve()
        if p.exists():
            return Image.open(p).convert("RGB"), sz.get("bild_credit", "")
    if sz.get("bild_suche"):
        try:
            res = _pexels("v1/search", {"query": sz["bild_suche"], "orientation": "landscape", "per_page": 1})
            if res and res.get("photos"):
                ph = res["photos"][0]
                cache.mkdir(parents=True, exist_ok=True)
                fp = cache / f"img_{ph['id']}.jpg"
                if not fp.exists():
                    urllib.request.urlretrieve(ph["src"]["large2x"], fp)
                return Image.open(fp).convert("RGB"), f"Foto: {ph.get('photographer', '')} / Pexels"
        except Exception as e:
            print(f"  Bild nicht geladen: {e}")
    return None, ""


# ───────────────────────── Renderer ─────────────────────────
class Renderer:
    def __init__(self, ep, data, tl, base_dir: Path, clip_npy: str | None = None):
        self.ep, self.data, self.tl = ep, data, tl
        clip = list(np.load(clip_npy)) if clip_npy else None
        self.bg = Background(clip)
        self.chunks = build_chunks(tl["words"])
        d = date.fromisoformat(ep["datum"])
        self.date_short = f"{B.WT_KURZ[d.weekday()]} {d.day:02d}.{d.month:02d}."
        self.ctx = {"data": data, "bilder": {}, "datum_lang": f"{B.WOCHENTAG[d.weekday()]}, {d.day}. {B.MONAT[d.month - 1]} {d.year}"}
        self.credits = {}
        mi = 0
        cache = base_dir / ".cache"
        for i, sz in enumerate(ep["szenen"]):
            if sz["typ"] == "gewinner_verlierer":
                sz["_movers_idx"] = mi
                mi += 1
            if sz["typ"] == "bild":
                img, cred = load_image(sz, base_dir, cache)
                sz["_bild_key"] = i
                self.ctx["bilder"][i] = img
                self.credits[i] = cred
        self.dur = tl["dauer"]

    def scene_at(self, t):
        sc = self.tl["scenes"]
        for i, s in enumerate(sc):
            if s["start"] <= t < s["end"]:
                return i
        return len(sc) - 1

    def source_for(self, i):
        sz = self.ep["szenen"][i]
        if sz.get("quelle"):
            return sz["quelle"]
        if i in self.credits and self.credits[i]:
            return self.credits[i]
        if sz["typ"] in DEFAULT_SOURCE:
            return DEFAULT_SOURCE[sz["typ"]]
        q = self.ep.get("quellen") or []
        return ", ".join(q[:2])

    def render_scene(self, i, t_local):
        sz = self.ep["szenen"][i]
        s = self.tl["scenes"][i]
        fn = SCENES.get(sz["typ"])
        if not fn:
            return layer()
        return fn(self.ctx, sz, t_local, s["end"] - s["start"])

    def frame(self, n: int) -> np.ndarray:
        t = n / FPS
        energy = 1.0
        i = self.scene_at(t)
        s = self.tl["scenes"][i]
        tl_ = t - s["start"]
        img = Image.fromarray(self.bg.frame(t, energy)).convert("RGBA")

        # ausgehende Szene (überlappt die ersten TRANS Sekunden der neuen)
        if i > 0 and tl_ < TRANS:
            e = ease_in_out_cubic(tl_ / TRANS)
            prev = self.tl["scenes"][i - 1]
            out = self.render_scene(i - 1, t - prev["start"])
            paste_alpha(img, out, (0, -90 * e), (1 - e) ** 1.6)
        cur = self.render_scene(i, tl_ - (IN_DELAY if i > 0 else 0))
        img.alpha_composite(cur)

        # Lichtstreifen beim Wechsel
        if i > 0 and tl_ < TRANS + 0.15:
            e = clamp(tl_ / (TRANS + 0.15))
            band = AA(W, 14, 2)
            x = -400 + (W + 800) * ease_out_cubic(e)
            band.rrect((x - 220, 5, x + 220, 9), 2, fill=rgba(B.VIO, 0.9 * (1 - e)))
            paste_alpha(img, band.done(), (0, B.STAGE_TOP - 34))

        is_outro = self.ep["szenen"][i]["typ"] == "outro"
        draw_header(img, self.date_short)
        draw_progress(img, clamp(t / self.dur))
        if not is_outro:
            src_alpha = 1.0
            if i > 0 and tl_ < TRANS:
                src_alpha = tl_ / TRANS
            draw_footer(img, self.source_for(i), src_alpha)
        else:
            draw_footer(img, "Yahoo Finance (Kursdaten)" if not self.ep.get("quellen") else
                        ", ".join(self.ep["quellen"][:2]))
        draw_captions(img, self.chunks, t)
        return np.asarray(img.convert("RGB"))


_R: Renderer | None = None


def _init(ep, data, tl, base_dir, clip):
    global _R
    B.ensure_fonts()
    _R = Renderer(ep, data, tl, Path(base_dir), clip)


def _job(n):
    return _R.frame(n).tobytes()


def render_video(ep, data, tl, out_mp4: Path, base_dir: Path, workers=None, clip=None,
                 musik: str | None = None, fps=FPS, preview=False):
    nframes = int(math.ceil(tl["dauer"] * fps))
    ff = B.ffmpeg_bin()
    cmd = [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-"]
    audio = tl.get("audio")
    if audio:
        cmd += ["-i", audio]
    if musik:
        cmd += ["-stream_loop", "-1", "-i", musik]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22" if preview else "18",
            "-maxrate", "8M" if preview else "20M", "-bufsize", "40M",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart"]
    if audio and musik:
        cmd += ["-filter_complex", "[2:a]volume=0.09[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    elif audio:
        cmd += ["-map", "0:v", "-map", "1:a"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += [str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    workers = workers or max(1, (os.cpu_count() or 2))
    ctx = get_context("spawn" if os.name == "nt" else "fork")
    step = max(1, FPS // fps)
    frames = list(range(0, int(math.ceil(tl["dauer"] * FPS)), step))
    nframes = len(frames)
    import time
    t0 = time.time()
    with ctx.Pool(workers, initializer=_init, initargs=(ep, data, tl, str(base_dir), clip)) as pool:
        for k, buf in enumerate(pool.imap(_job, frames, chunksize=4)):
            proc.stdin.write(buf)
            if k % 60 == 0:
                el = time.time() - t0
                eta = el / max(1, k) * (nframes - k)
                print(f"\r  Frame {k}/{nframes}  ·  noch ca. {eta:4.0f} s", end="", flush=True)
    proc.stdin.close()
    proc.wait()
    print(f"\r  Fertig: {nframes} Frames in {time.time() - t0:.0f} s{' ' * 20}")
    return out_mp4


def render_still(ep, data, tl, t, base_dir: Path, clip=None) -> Image.Image:
    B.ensure_fonts()
    r = Renderer(ep, data, tl, base_dir, clip)
    return Image.fromarray(r.frame(int(t * FPS)))

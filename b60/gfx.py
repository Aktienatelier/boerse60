"""Grafik-Werkzeuge: Easing, Kantenglättung, Glow, Text, Hintergrund, Header/Footer."""
from __future__ import annotations

import math
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw

from . import brand as B
from .brand import W, H, font

# ───────────────────────── Easing ─────────────────────────
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def prog(t, start, dur):
    """0→1 zwischen start und start+dur."""
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return clamp((t - start) / dur)


def ease_out_cubic(x):
    return 1 - (1 - x) ** 3


def ease_out_expo(x):
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_in_out_cubic(x):
    return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=1.70158):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, x):
    return a + (b - a) * x


def mix(c1, c2, x):
    return tuple(int(round(lerp(a, b, x))) for a, b in zip(c1, c2))


def rgba(c, a=1.0):
    return (int(c[0]), int(c[1]), int(c[2]), int(round(255 * clamp(a))))


def move_color(pct: float):
    """Gewinn-/Verlustfarbe nach Vorzeichen."""
    return B.GAIN if pct > 0 else B.LOSS if pct < 0 else B.GREY


# ───────────────────────── Ebenen ─────────────────────────
def layer(w=W, h=H):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def paste_alpha(dst: Image.Image, src: Image.Image, xy=(0, 0), alpha: float = 1.0):
    if alpha <= 0.003:
        return
    if alpha < 0.999:
        a = src.getchannel("A").point(lambda v: int(v * alpha))
        src = src.copy()
        src.putalpha(a)
    dst.alpha_composite(src, dest=(int(xy[0]), int(xy[1])))


def glow(img: Image.Image, radius: float = 24, strength: float = 1.0) -> Image.Image:
    """Weicher Leuchtschein einer RGBA-Ebene (für additive Überlagerung)."""
    arr = np.asarray(img).astype(np.float32)
    k = int(radius * 3) | 1
    blurred = cv2.GaussianBlur(arr, (k, k), radius)
    blurred[..., 3] = np.clip(blurred[..., 3] * strength, 0, 255)
    return Image.fromarray(blurred.astype(np.uint8), "RGBA")


# ───────────────────────── Kantengeglättete Vektoren ─────────────────────────
class AA:
    """Zeichenfläche mit Supersampling (Faktor ss) – für Linien, Flächen, Kreise."""

    def __init__(self, w, h, ss=3):
        self.w, self.h, self.ss = int(w), int(h), ss
        self.img = Image.new("RGBA", (self.w * ss, self.h * ss), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def _p(self, pts):
        s = self.ss
        return [(x * s, y * s) for x, y in pts]

    def line(self, pts, fill, width=4, joint="curve"):
        if len(pts) >= 2:
            self.d.line(self._p(pts), fill=fill, width=max(1, int(width * self.ss)), joint=joint)
            r = width * self.ss / 2
            for x, y in (self._p([pts[0]])[0], self._p([pts[-1]])[0]):
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def poly(self, pts, fill):
        if len(pts) >= 3:
            self.d.polygon(self._p(pts), fill=fill)

    def circle(self, cx, cy, r, fill=None, outline=None, width=2):
        s = self.ss
        self.d.ellipse(((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s),
                       fill=fill, outline=outline, width=int(width * s))

    def rrect(self, box, r, fill=None, outline=None, width=2):
        s = self.ss
        x0, y0, x1, y1 = box
        self.d.rounded_rectangle((x0 * s, y0 * s, x1 * s, y1 * s), radius=r * s,
                                 fill=fill, outline=outline, width=int(width * s))

    def dashed(self, p0, p1, fill, width=2, dash=10, gap=8):
        (x0, y0), (x1, y1) = p0, p1
        L = math.hypot(x1 - x0, y1 - y0)
        if L == 0:
            return
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        pos = 0.0
        while pos < L:
            e = min(pos + dash, L)
            self.d.line(self._p([(x0 + ux * pos, y0 + uy * pos), (x0 + ux * e, y0 + uy * e)]),
                        fill=fill, width=max(1, int(width * self.ss)))
            pos = e + gap

    def tri(self, cx, cy, size, up=True, fill=(255, 255, 255, 255)):
        h = size * 0.86
        if up:
            pts = [(cx, cy - h / 2), (cx + size / 2, cy + h / 2), (cx - size / 2, cy + h / 2)]
        else:
            pts = [(cx, cy + h / 2), (cx + size / 2, cy - h / 2), (cx - size / 2, cy - h / 2)]
        self.poly(pts, fill)

    def done(self) -> Image.Image:
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def gradient_fill(mask: Image.Image, top_rgba, bottom_rgba) -> Image.Image:
    """Vertikaler Verlauf, maskiert durch den Alphakanal von mask."""
    w, h = mask.size
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    c0 = np.array(top_rgba, np.float32)[None, None, :]
    c1 = np.array(bottom_rgba, np.float32)[None, None, :]
    g = np.repeat(c0 + (c1 - c0) * t, w, axis=1)
    m = np.asarray(mask.getchannel("A"), np.float32)[..., None] / 255.0
    g[..., 3:4] *= m
    return Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGBA")


# ───────────────────────── Text ─────────────────────────
def text_size(txt, fnt, tracking=0):
    if not txt:
        return 0, 0
    l, t, r, b = fnt.getbbox(txt)
    return r - l + tracking * max(0, len(txt) - 1), b - t


def text_w(txt, fnt, tracking=0):
    if tracking == 0:
        return fnt.getlength(txt)
    return sum(fnt.getlength(c) for c in txt) + tracking * max(0, len(txt) - 1)


def draw_text(d: ImageDraw.ImageDraw, xy, txt, fnt, fill, anchor="la", tracking=0):
    if tracking == 0:
        d.text(xy, txt, font=fnt, fill=fill, anchor=anchor)
        return
    total = text_w(txt, fnt, tracking)
    x, y = xy
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    va = "l" + {"t": "a"}.get(anchor[1], anchor[1])
    for c in txt:
        d.text((x, y), c, font=fnt, fill=fill, anchor=va)
        x += fnt.getlength(c) + tracking


def fit_font(txt, weight, max_w, start, min_size=24, tracking=0):
    size = start
    while size > min_size:
        f = font(weight, size)
        if text_w(txt, f, tracking) <= max_w:
            return f
        size -= 2
    return font(weight, min_size)


def tabular(d, xy, txt, fnt, fill, anchor="ls"):
    """Zahlen mit fester Ziffernbreite – kein Zittern beim Hochzählen."""
    cell = fnt.getlength("0")
    widths = [cell if ch.isdigit() else fnt.getlength(ch) for ch in txt]
    total = sum(widths)
    x, y = xy
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    for ch, cw in zip(txt, widths):
        if ch.isdigit():
            d.text((x + cw / 2, y), ch, font=fnt, fill=fill, anchor="m" + anchor[1])
        else:
            d.text((x, y), ch, font=fnt, fill=fill, anchor="l" + anchor[1])
        x += cw
    return total


def tabular_w(txt, fnt):
    cell = fnt.getlength("0")
    return sum(cell if ch.isdigit() else fnt.getlength(ch) for ch in txt)


def wrap(txt, fnt, max_w):
    words, lines, cur = txt.split(), [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if fnt.getlength(test) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


# ───────────────────────── Hintergrund ─────────────────────────
class Background:
    """Nachtschwarz mit zwei langsam wandernden Lichtern, Vignette und feinem Korn.
    Optional ein lila eingefärbter Hintergrund-Clip (nur Hintergrund wird eingefärbt)."""

    def __init__(self, clip_frames: list[np.ndarray] | None = None, clip_fps: float = 12):
        self.lw, self.lh = W // 4, H // 4
        yy, xx = np.mgrid[0:self.lh, 0:self.lw].astype(np.float32)
        self.xx, self.yy = xx / self.lw, yy / self.lh * (H / W)
        vy, vx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((vx - W / 2) / (W * .75)) ** 2 + ((vy - H / 2) / (H * .7)) ** 2)
        self.vignette = np.clip(1 - 0.55 * d ** 2, 0.35, 1)[..., None].astype(np.float32)
        rng = np.random.default_rng(7)
        self.grain = [rng.normal(0, 2.2, (H, W, 1)).astype(np.float32) for _ in range(6)]
        self.base = np.array(B.BG, np.float32)
        self.clip = clip_frames
        self.clip_fps = clip_fps

    def blob(self, cx, cy, r):
        d2 = (self.xx - cx) ** 2 + (self.yy - cy) ** 2
        return np.exp(-d2 / (2 * r * r))

    def frame(self, t: float, energy: float = 1.0) -> np.ndarray:
        g1 = self.blob(.30 + .14 * math.sin(t * .31), .55 + .10 * math.cos(t * .23), .42)
        g2 = self.blob(.78 + .10 * math.cos(t * .27), 1.25 + .14 * math.sin(t * .19), .48)
        g3 = self.blob(.55 + .2 * math.sin(t * .13 + 1), 1.0 + .3 * math.cos(t * .17), .30)
        c1 = np.array(B.GLOW1, np.float32) - self.base
        c2 = np.array(B.GLOW2, np.float32) - self.base
        low = (g1[..., None] * c1 * .30 + g2[..., None] * c2 * .26 + g3[..., None] * c1 * .10) * energy
        up = cv2.resize(low, (W, H), interpolation=cv2.INTER_CUBIC)
        img = self.base[None, None, :] + up
        if self.clip:
            idx = int(t * self.clip_fps) % len(self.clip)
            c = cv2.resize(self.clip[idx], (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)
            img = img * 0.62 + c * 0.38
        img = img * self.vignette + self.grain[int(t * 4) % len(self.grain)]
        return np.clip(img, 0, 255).astype(np.uint8)


def tint_clip_frame(bgr: np.ndarray) -> np.ndarray:
    """Hintergrund-Clip: unscharf, abgedunkelt, auf Lila-Verlauf abgebildet."""
    small = cv2.resize(bgr, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    gray = cv2.GaussianBlur(gray, (0, 0), 2.2)
    lo = np.array(B.BG, np.float32)
    mid = np.array(B.GLOW1, np.float32) * 0.55
    hi = np.array(B.GLOW2, np.float32) * 0.9
    g = gray[..., None]
    out = np.where(g < .5, lo + (mid - lo) * (g / .5), mid + (hi - mid) * ((g - .5) / .5))
    return np.clip(out * 0.75, 0, 255).astype(np.uint8)


# ───────────────────────── Logo ─────────────────────────
@lru_cache(maxsize=4)
def logo_mark(size: int = 66) -> Image.Image:
    """Logo-Zeichen aus assets/logo_zeichen.png; sonst ein Platzhalter in Markenfarben."""
    for name in ("logo_zeichen.png", "logo.png"):
        p = B.ASSET_DIR / name
        if p.exists():
            im = Image.open(p).convert("RGBA")
            bb = im.getbbox()
            if bb:
                im = im.crop(bb)
            im.thumbnail((int(size * 1.6), size), Image.LANCZOS)
            return im
    a = AA(size, size, 4)
    a.rrect((2, 2, size - 2, size - 2), size * .26, fill=rgba(B.GLOW1))
    s = size
    a.line([(s * .24, s * .70), (s * .45, s * .48), (s * .58, s * .60), (s * .78, s * .32)],
           fill=rgba(B.INK), width=s * .085)
    a.poly([(s * .80, s * .26), (s * .80, s * .44), (s * .64, s * .30)], fill=rgba(B.INK))
    return a.done()


# ───────────────────────── Feste Elemente ─────────────────────────
def draw_header(img: Image.Image, date_label: str, alpha: float = 1.0):
    lg = logo_mark(62)
    lay = layer(W, 120)
    lay.alpha_composite(lg, (B.SAFE_LEFT, 6 + (62 - lg.size[1]) // 2))
    d = ImageDraw.Draw(lay)
    draw_text(d, (B.SAFE_LEFT + lg.size[0] + 18, 38), B.BRAND_NAME, font("SemiBold", 27), rgba(B.INK, .92),
              anchor="lm", tracking=5)
    # Datums-Pille rechts (endet vor dem rechten Rand)
    f = font("SemiBold", 24)
    tw = text_w(date_label, f, 2)
    x1 = B.SAFE_RIGHT
    x0 = x1 - tw - 40
    a = AA(W, 120, 2)
    a.rrect((x0, 16, x1, 60), 22, fill=rgba(B.AUB, .9), outline=rgba(B.AUB2), width=2)
    lay.alpha_composite(a.done())
    d = ImageDraw.Draw(lay)
    draw_text(d, ((x0 + x1) / 2, 38), date_label, f, rgba(B.LAV), anchor="mm", tracking=2)
    paste_alpha(img, lay, (0, B.HEADER_Y), alpha)


def draw_progress(img: Image.Image, frac: float, alpha=1.0):
    y = B.HEADER_Y + 96
    a = AA(B.CONTENT_W, 8, 3)
    a.rrect((0, 2, B.CONTENT_W, 6), 2, fill=rgba(B.AUB2, .9))
    if frac > 0.002:
        a.rrect((0, 2, max(6, B.CONTENT_W * frac), 6), 2, fill=rgba(B.VIO))
    paste_alpha(img, a.done(), (B.SAFE_LEFT, y), alpha)


def draw_footer(img: Image.Image, source: str, alpha: float = 1.0):
    lay = layer(W, 40)
    d = ImageDraw.Draw(lay)
    f = font("Regular", 21)
    disc = B.DISCLAIMER
    dw = f.getlength(disc)
    src = f"Quelle: {source}" if source else ""
    max_src = B.CONTENT_W - dw - 30
    while src and f.getlength(src) > max_src:
        src = src[:-2].rstrip() + "…" if not src.endswith("…") else src[:-3].rstrip() + "…"
    d.text((B.SAFE_LEFT, 20), src, font=f, fill=rgba(B.GREY, .85), anchor="lm")
    d.text((B.SAFE_RIGHT, 20), disc, font=f, fill=rgba(B.GREY, .85), anchor="rm")
    paste_alpha(img, lay, (0, B.FOOTER_Y - 20), alpha)


def card(w, h, r=28, fill=None, border=None, accent=None):
    """Karte in Aubergine mit feinem Rand; optional farbige Akzentkante links."""
    a = AA(w, h, 3)
    a.rrect((1, 1, w - 1, h - 1), r, fill=rgba(fill or B.AUB, .86), outline=rgba(border or B.AUB2), width=2)
    if accent:
        a.rrect((1, 1, 10, h - 1), 5, fill=rgba(accent))
    return a.done()


def chip(text, fnt, fg, bg, pad_x=20, h=None, tri=None):
    """Pille mit Text; tri='up'/'down' zeichnet ein Dreieck davor."""
    tw = fnt.getlength(text)
    h = h or int(fnt.size * 1.55)
    ts = fnt.size * 0.55 if tri else 0
    w = int(tw + 2 * pad_x + (ts + 12 if tri else 0))
    a = AA(w, h, 3)
    a.rrect((0, 0, w, h), h / 2, fill=bg)
    if tri:
        a.tri(pad_x + ts / 2, h / 2 + (1 if tri == "up" else 0), ts, up=(tri == "up"), fill=fg)
    im = a.done()
    d = ImageDraw.Draw(im)
    d.text((pad_x + (ts + 12 if tri else 0), h / 2 + 1), text, font=fnt, fill=fg, anchor="lm")
    return im

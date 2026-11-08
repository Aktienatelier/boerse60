"""Aktienatelier – Branding für „Börse in 60 Sekunden“.

Farbsystem „Nacht“ (aus dem Logo gemessen, Nov. 2026), Schrift Poppins,
Sicherheitsränder für TikTok und Instagram (Hochformat 1080 × 1920).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "fonts"
ASSET_DIR = ROOT / "assets"

# ───────────────────────── Format ─────────────────────────
W, H = 1080, 1920
FPS = 30

# Ränder: oben 230, unten 430, rechts 140 px frei für die Bedienelemente
SAFE_TOP = 230
SAFE_BOTTOM = H - 430          # 1490
SAFE_LEFT = 60
SAFE_RIGHT = W - 140           # 940
CONTENT_W = SAFE_RIGHT - SAFE_LEFT  # 880
CX = (SAFE_LEFT + SAFE_RIGHT) // 2  # optische Mitte des freien Bereichs (500)

# Vertikale Zonen innerhalb des sicheren Bereichs
HEADER_Y = SAFE_TOP + 14       # Logo-Zeile
STAGE_TOP = 360                # Szenen-Inhalt
STAGE_BOTTOM = 1235
CAPTION_Y = 1352               # Mitte der Untertitel
FOOTER_Y = 1452                # Quelle + Hinweis

# ───────────────────────── Farbsystem „Nacht“ ─────────────────────────
def hexrgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


BG = hexrgb("130E19")      # Nachtschwarz – Hintergrund
AUB = hexrgb("241A2E")     # Aubergine – Karten, Gitter
AUB2 = hexrgb("2F2239")    # Aubergine hell – Kartenrand
VIO = hexrgb("B565D9")     # Orchidee – Akzent (eine Aussage pro Bild)
TVIO = hexrgb("4F0F49")    # Pflaume – Akzent auf hellem Grund
LAV = hexrgb("E0C8F0")     # Flieder – zweite Linie
INK = hexrgb("F7F0FA")     # Nebel – Text
GREY = hexrgb("A898B0")    # Graphit – Nebentext, Quellen
LOSS = hexrgb("FF6B7A")    # Verlust – nur für Rückgänge
GAIN = hexrgb("3DD9A0")    # Gewinn – nur für Anstiege
GLOW1 = hexrgb("8D4CCB")   # Hintergrundlicht Violett
GLOW2 = hexrgb("95348B")   # Hintergrundlicht Magenta

BRAND_NAME = "AKTIENATELIER"
SERIES = "BÖRSE IN 60 SEKUNDEN"
DISCLAIMER = "Keine Anlageberatung"

# ───────────────────────── Schriften ─────────────────────────
_POPPINS = {
    "Regular": "Poppins-Regular.ttf",
    "Medium": "Poppins-Medium.ttf",
    "SemiBold": "Poppins-SemiBold.ttf",
    "Bold": "Poppins-Bold.ttf",
    "ExtraBold": "Poppins-ExtraBold.ttf",
}
_GF_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/{}"
_FALLBACK = {"SemiBold": "Bold", "ExtraBold": "Bold"}


def _system_font(name: str) -> Path | None:
    for base in ("/usr/share/fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts"),
                 "C:/Windows/Fonts", os.path.expanduser("~/.local/share/fonts")):
        if os.path.isdir(base):
            for dp, _, files in os.walk(base):
                if name in files:
                    return Path(dp) / name
    return None


def ensure_fonts(verbose: bool = False) -> None:
    """Lädt Poppins automatisch (Google Fonts, OFL) nach ./fonts, falls nötig."""
    FONT_DIR.mkdir(exist_ok=True)
    for weight, fn in _POPPINS.items():
        dst = FONT_DIR / fn
        if dst.exists():
            continue
        sys_f = _system_font(fn)
        if sys_f:
            shutil.copy(sys_f, dst)
            continue
        try:
            urllib.request.urlretrieve(_GF_URL.format(fn), dst)
            if verbose:
                print(f"  Schrift geladen: {fn}")
        except Exception:
            if dst.exists():
                dst.unlink()


@lru_cache(maxsize=256)
def font(weight: str = "Regular", size: int = 40) -> ImageFont.FreeTypeFont:
    w = weight
    for _ in range(3):
        p = FONT_DIR / _POPPINS.get(w, "Poppins-Regular.ttf")
        if p.exists():
            return ImageFont.truetype(str(p), size)
        sys_f = _system_font(_POPPINS.get(w, ""))
        if sys_f:
            return ImageFont.truetype(str(sys_f), size)
        w = _FALLBACK.get(w, "Regular")
    for fb in ("DejaVuSans-Bold.ttf" if "Bold" in weight else "DejaVuSans.ttf",):
        p = _system_font(fb)
        if p:
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


# ───────────────────────── Zahlen deutsch ─────────────────────────
def de_num(x: float, dec: int = 2) -> str:
    s = f"{abs(x):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if x < 0 else "") + s


def de_pct(x: float, dec: int = 2, sign: bool = True) -> str:
    s = de_num(abs(x), dec)
    if sign:
        s = ("+" if x > 0 else "−" if x < 0 else "±") + s
    return s + " %"


WOCHENTAG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WT_KURZ = ["MO", "DI", "MI", "DO", "FR", "SA", "SO"]
MONAT = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
         "September", "Oktober", "November", "Dezember"]


def ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def have_ffmpeg() -> bool:
    try:
        subprocess.run([ffmpeg_bin(), "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False

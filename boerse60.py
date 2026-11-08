#!/usr/bin/env python3
"""Börse in 60 Sekunden – Aktienatelier

  python boerse60.py skript      folgen/2026-11-06.json            # Sprechtext zum Einsprechen
  python boerse60.py vorschau    folgen/2026-11-06.json            # stumme Vorschau mit geschätztem Timing
  python boerse60.py standbilder folgen/2026-11-06.json            # ein PNG pro Szene (schnelle Kontrolle)
  python boerse60.py render      folgen/2026-11-06.json --audio aufnahme.wav
  python boerse60.py daten       folgen/2026-11-06.json --neu      # Kursdaten neu laden

Ausgabe: ausgabe/<datum>/  (Video, Titelbild, Captions)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from b60 import brand as B  # noqa: E402
from b60 import data as D  # noqa: E402
from b60.audio import estimate_timeline, process_recording, script_sentences  # noqa: E402


def load_ep(p: Path) -> dict:
    ep = json.loads(p.read_text(encoding="utf-8"))
    for i, sz in enumerate(ep.get("szenen", [])):
        if sz.get("typ") not in ("hook", "markt", "aktie", "sektoren", "gewinner_verlierer", "zahl",
                                 "bild", "termine", "outro"):
            sys.exit(f"Unbekannter Szenentyp in Szene {i + 1}: {sz.get('typ')}")
    return ep


def out_dir(ep, p: Path) -> Path:
    d = ROOT / "ausgabe" / ep.get("datum", p.stem)
    d.mkdir(parents=True, exist_ok=True)
    return d


def check_script(ep):
    n = sum(len(s["words"]) for s in script_sentences(ep))
    hints = []
    for s in script_sentences(ep):
        if re.search(r"aktienatelier", s["text"], re.I):
            hints.append(f"Satz mit „Aktienatelier“ bitte streichen: „{s['text'][:60]}“")
    return n, hints


def cmd_skript(ep, p, args):
    n, hints = check_script(ep)
    lines = [f"BÖRSE IN 60 SEKUNDEN – {ep.get('datum')}", f"{n} Wörter · ca. {n / 2.5 * 1 / 1.1:.0f} s nach 1,1-fach", ""]
    for i, sz in enumerate(ep["szenen"], 1):
        if sz.get("text"):
            lines += [f"[{i}] {sz['typ'].upper()}", sz["text"], ""]
    txt = "\n".join(lines)
    print(txt)
    for h in hints:
        print("⚠", h)
    (out_dir(ep, p) / "sprechtext.txt").write_text(txt, encoding="utf-8")


def _clip(ep, p):
    if ep.get("hintergrund_suche"):
        from b60.render import load_background_clip
        c = load_background_clip(ep["hintergrund_suche"], ROOT / ".cache")
        return str(c) if c else None
    return None


def _write_captions(ep, od):
    cap = ep.get("caption") or []
    tags = " ".join(ep.get("hashtags") or [])
    txt = ""
    for i, c in enumerate(cap, 1):
        txt += f"── Variante {i} ──\n{c}\n{tags}\n\n"
    if txt:
        (od / "caption.txt").write_text(txt, encoding="utf-8")


def cmd_vorschau(ep, p, args):
    from b60.render import render_video
    data = D.load_or_fetch(p, ep, args.neu)
    tl = estimate_timeline(ep)
    od = out_dir(ep, p)
    _warn_len(tl)
    out = od / "vorschau.mp4"
    print(f"Rendere Vorschau ({tl['dauer']:.1f} s, 15 fps, ohne Ton) …")
    render_video(ep, data, tl, out, ROOT, workers=args.kerne, clip=_clip(ep, p), fps=15, preview=True)
    print(f"→ {out}")


def cmd_standbilder(ep, p, args):
    from b60.render import render_still
    data = D.load_or_fetch(p, ep, args.neu)
    tl = estimate_timeline(ep)
    od = out_dir(ep, p) / "standbilder"
    od.mkdir(exist_ok=True)
    clip = _clip(ep, p)
    for i, s in enumerate(tl["scenes"]):
        t = s["start"] + min(s["end"] - s["start"] - 0.1, args.zeit)
        im = render_still(ep, data, tl, t, ROOT, clip)
        f = od / f"{i + 1:02d}_{ep['szenen'][i]['typ']}.png"
        im.save(f)
        print(f"  {f.name}  (t = {t:.1f} s)")


def cmd_render(ep, p, args):
    from b60.render import render_still, render_video
    data = D.load_or_fetch(p, ep, args.neu)
    od = out_dir(ep, p)
    if args.audio:
        print("Bereite Aufnahme auf (Versprecher raus, Pausen kürzen, Variante C) …")
        tl = process_recording(ep, Path(args.audio), od, args.whisper)
    else:
        print("Keine Aufnahme angegeben – Video ohne Ton mit geschätztem Timing.")
        tl = estimate_timeline(ep)
    _warn_len(tl)
    out = od / f"boerse60_{ep['datum']}.mp4"
    print(f"Rendere Video ({tl['dauer']:.1f} s, 1080 × 1920, 30 fps) …")
    clip = _clip(ep, p)
    render_video(ep, data, tl, out, ROOT, workers=args.kerne, clip=clip, musik=args.musik)
    cover = render_still(ep, data, tl, min(2.2, tl["scenes"][0]["end"] - 0.1), ROOT, clip)
    cover.save(od / "titelbild.png")
    _write_captions(ep, od)
    print(f"→ {out}\n→ {od / 'titelbild.png'}")


def cmd_daten(ep, p, args):
    D.load_or_fetch(p, ep, True)


def _warn_len(tl):
    if tl["dauer"] < 61:
        print(f"⚠ Video ist nur {tl['dauer']:.1f} s lang – Ziel ist über 1 Minute. Sprechtext etwas verlängern.")


def main():
    ap = argparse.ArgumentParser(description="Börse in 60 Sekunden – Aktienatelier")
    ap.add_argument("befehl", choices=["skript", "vorschau", "standbilder", "render", "daten"])
    ap.add_argument("folge", help="Pfad zur Folgen-Datei (JSON)")
    ap.add_argument("--audio", help="Deine Aufnahme (WAV/MP3/M4A)")
    ap.add_argument("--musik", help="optionale Hintergrundmusik (leise)")
    ap.add_argument("--whisper", default="medium", help="Whisper-Modell: base, small, medium")
    ap.add_argument("--kerne", type=int, default=None, help="Anzahl CPU-Kerne")
    ap.add_argument("--neu", action="store_true", help="Kursdaten neu laden")
    ap.add_argument("--zeit", type=float, default=2.6, help="Zeitpunkt in der Szene für Standbilder")
    args = ap.parse_args()
    p = Path(args.folge).resolve()
    ep = load_ep(p)
    B.ensure_fonts(verbose=True)
    {"skript": cmd_skript, "vorschau": cmd_vorschau, "standbilder": cmd_standbilder,
     "render": cmd_render, "daten": cmd_daten}[args.befehl](ep, p, args)


if __name__ == "__main__":
    main()

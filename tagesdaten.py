#!/usr/bin/env python3
"""Tagesüberblick für die Recherche: Indizes, Rohstoffe, Sektoren, Top/Flop (US + DAX).

  python tagesdaten.py                # letzter Handelstag
  python tagesdaten.py 2026-11-06     # bestimmter Tag
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b60 import data as D  # noqa: E402

datum = sys.argv[1] if len(sys.argv) > 1 else None
ep = {"datum": datum, "szenen": [
    {"typ": "markt", "werte": ["^GSPC", "^NDX", "^DJI", "^RUT", "^GDAXI", "^STOXX50E", "^VIX", "^TNX",
                               "BTC-USD", "GC=F", "BZ=F", "EURUSD=X"]},
    {"typ": "sektoren"},
    {"typ": "gewinner_verlierer", "markt": "us"},
    {"typ": "gewinner_verlierer", "markt": "de"},
]}
d = D.fetch(ep, verbose=False)
print("\nINDIZES & CO.")
for tk, r in d["werte"].items():
    print(f"  {tk:<10} {r['name']:<20} {r['datum']}  {r['kurs']:>12,.2f}  {r['pct']:+6.2f} %")
print("\nSEKTOREN (US)")
for tk, s in sorted(d["sektoren"].items(), key=lambda x: -x[1]["pct"]):
    print(f"  {tk:<5} {s['name']:<20} {s['pct']:+6.2f} %")
for label, mv in zip(("US-UNIVERSUM", "DAX"), d["movers"]):
    print(f"\n{label} – TOP 5")
    for m in reversed(mv[-5:]):
        print(f"  {m['ticker']:<9} {m['name']:<20} {m['pct']:+6.2f} %")
    print(f"{label} – FLOP 5")
    for m in mv[:5]:
        print(f"  {m['ticker']:<9} {m['name']:<20} {m['pct']:+6.2f} %")
Path("tagesdaten.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

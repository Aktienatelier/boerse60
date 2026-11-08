"""Szenentypen für „Börse in 60 Sekunden“.

Jede Szene ist eine reine Funktion der Zeit: render(ctx, szene, t_lokal, dauer) → RGBA-Ebene.
Dadurch lässt sich jedes Bild unabhängig (parallel) berechnen.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
from PIL import Image, ImageDraw

from . import brand as B
from .brand import W, H, font, de_num, de_pct
from .gfx import (AA, card, chip, clamp, draw_text, ease_in_out_cubic, ease_out_back,
                  ease_out_cubic, ease_out_expo, fit_font, glow, gradient_fill, layer, lerp,
                  mix, move_color, paste_alpha, prog, rgba, tabular, tabular_w, text_w, wrap)

L, R = B.SAFE_LEFT, B.SAFE_RIGHT
CW = B.CONTENT_W


# ───────────────────────── Bausteine ─────────────────────────
def enter(t, delay=0.0, dur=0.55):
    """Standard-Eintritt: (Anteil, y-Versatz)."""
    p = ease_out_expo(prog(t, delay, dur))
    return p, (1 - p) * 46


def kicker_title(lay, t, kicker, title, y=B.STAGE_TOP, title_size=66, color=None):
    d = ImageDraw.Draw(lay)
    p, dy = enter(t, 0.0)
    if kicker:
        c = color or B.VIO
        a = AA(14, 14, 4)
        a.circle(7, 7, 6, fill=rgba(c, p))
        lay.alpha_composite(a.done(), (L, int(y + 12 + dy)))
        draw_text(d, (L + 26, y + 19 + dy), kicker.upper(), font("SemiBold", 26), rgba(c, p),
                  anchor="lm", tracking=4)
    if title:
        p2, dy2 = enter(t, 0.08)
        f = fit_font(title, "Bold", CW, title_size, 40)
        d.text((L, y + 52 + dy2), title, font=f, fill=rgba(B.INK, p2), anchor="lt")
    return y + 52 + (title_size + 20 if title else 0)


def counter(value, t, delay=0.15, dur=1.1):
    return value * ease_out_cubic(prog(t, delay, dur))


def ticker_badge(tk, fsize=28, color=None):
    c = color or B.VIO
    f = font("SemiBold", fsize)
    label = tk.replace(".DE", "").replace("^", "")
    tw = f.getlength(label)
    w, h = int(tw + 36), int(fsize * 1.7)
    a = AA(w, h, 3)
    a.rrect((1, 1, w - 1, h - 1), 12, fill=rgba(c, .14), outline=rgba(c, .9), width=2)
    im = a.done()
    ImageDraw.Draw(im).text((w / 2, h / 2 + 1), label, font=f, fill=rgba(c), anchor="mm")
    return im


def pct_chip(pct, size=36, alpha=1.0):
    c = move_color(pct)
    return chip(de_pct(pct).replace("+", "+").replace("−", "−"), font("Bold", size), rgba(c),
                rgba(c, .16), tri="up" if pct > 0 else "down" if pct < 0 else None)


def value_text(v, unit, dec=None):
    if v is None:
        return "–"
    if dec is None:
        dec = 0 if abs(v) >= 10000 else 2
    if unit in ("Pkt.",):
        return de_num(v, dec)
    if unit == "%":
        return de_num(v, 2) + " %"
    if unit in ("$", "€", "£", "¥"):
        return de_num(v, dec) + " " + unit
    return de_num(v, dec) + (" " + unit if unit else "")


# ───────────────────────── Chart ─────────────────────────
def draw_chart(lay, box, series, t, *, t0=0.25, dur=2.0, baseline=None, color=None,
               x_labels=None, event_idx=None, event_label=None, unit="", show_head=True,
               grid=True, label_dec=2):
    """Animierter Linienchart mit Verlaufsfläche, Glow, Kopfpunkt und Vortageslinie."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    vals = [v for _, v in series if v is not None]
    if len(vals) < 2:
        return
    lo, hi = min(vals), max(vals)
    if baseline is not None:
        lo, hi = min(lo, baseline), max(hi, baseline)
    pad = (hi - lo) * 0.12 or abs(hi) * 0.01 or 1
    lo, hi = lo - pad, hi + pad * 1.4
    gx0, gx1 = 8, w - 112        # rechts Platz für Achsenwerte
    gy0, gy1 = 18, h - 44        # unten Platz für Zeitachse
    n = len(vals)

    def X(i):
        return gx0 + (gx1 - gx0) * i / (n - 1)

    def Y(v):
        return gy1 - (gy1 - gy0) * (v - lo) / (hi - lo)

    color = color or (move_color(vals[-1] - (baseline if baseline is not None else vals[0])))
    p = ease_in_out_cubic(prog(t, t0, dur))
    fade = ease_out_cubic(prog(t, 0, 0.5))
    if fade <= 0:
        return

    base = AA(w, h, 2)
    # Gitter + Achsenwerte
    if grid:
        for k in range(4):
            v = lo + (hi - lo) * (0.12 + 0.76 * k / 3)
            yy = Y(v)
            base.line([(gx0, yy), (gx1, yy)], fill=rgba(B.AUB2, .9 * fade), width=1.5)
    if baseline is not None:
        base.dashed((gx0, Y(baseline)), (gx1, Y(baseline)), fill=rgba(B.GREY, .55 * fade), width=2, dash=9, gap=9)
    lay.alpha_composite(base.done(), (x0, y0))

    d = ImageDraw.Draw(lay)
    fl = font("Regular", 22)
    if grid:
        for k in range(4):
            v = lo + (hi - lo) * (0.12 + 0.76 * k / 3)
            d.text((x0 + w - 4, y0 + Y(v)), de_num(v, label_dec if abs(v) < 10000 else 0), font=fl,
                   fill=rgba(B.GREY, .8 * fade), anchor="rm")
    if baseline is not None:
        d.text((x0 + gx0 + 4, y0 + Y(baseline) - 8), "Vortag", font=font("Medium", 20),
               fill=rgba(B.GREY, .8 * fade), anchor="lb")
    if x_labels:
        for i, lab in x_labels:
            xx = x0 + X(i)
            anc = "lt" if i == 0 else "rt" if i == n - 1 else "mt"
            d.text((xx, y0 + gy1 + 14), lab, font=fl, fill=rgba(B.GREY, .8 * fade), anchor=anc)

    # Linie bis zum aktuellen Fortschritt
    if p <= 0:
        return
    upto = p * (n - 1)
    k = int(upto)
    pts = [(X(i), Y(vals[i])) for i in range(k + 1)]
    if k < n - 1:
        f_ = upto - k
        pts.append((X(upto), Y(lerp(vals[k], vals[k + 1], f_))))
    if len(pts) < 2:
        return
    # Fläche
    area = AA(w, h, 2)
    area.poly(pts + [(pts[-1][0], gy1), (pts[0][0], gy1)], fill=(255, 255, 255, 255))
    mask = area.done()
    lay.alpha_composite(gradient_fill(mask, rgba(color, .30), rgba(color, 0.0)), (x0, y0))
    # Linie mit Glow
    ln = AA(w, h, 2)
    ln.line(pts, fill=rgba(color), width=5)
    line_img = ln.done()
    lay.alpha_composite(glow(line_img, 10, 1.4), (x0, y0))
    lay.alpha_composite(line_img, (x0, y0))

    # Ereignis-Markierung
    if event_idx is not None and 0 <= event_idx < n and upto >= event_idx:
        ep = ease_out_back(prog(upto, event_idx, max(1, n * 0.08)))
        ex = X(event_idx)
        ev = AA(w, h, 2)
        ev.dashed((ex, gy0), (ex, gy1), fill=rgba(B.LAV, .7 * ep), width=2, dash=7, gap=7)
        ev.circle(ex, Y(vals[event_idx]), 9 * ep, fill=rgba(B.LAV))
        lay.alpha_composite(ev.done(), (x0, y0))
        if event_label:
            c = chip(event_label, font("SemiBold", 22), rgba(B.BG), rgba(B.LAV, .95), pad_x=14)
            cx = int(clamp(x0 + ex - c.size[0] / 2, x0, x0 + gx1 - c.size[0]))
            paste_alpha(lay, c, (cx, y0 + gy0 - 4 - 30 * (1 - ep)), ep)

    # Kopfpunkt mit Puls + Wertlabel
    if show_head:
        hx, hy = pts[-1]
        pulse = (t * 1.6) % 1.0
        hd = AA(w, h, 3)
        hd.circle(hx, hy, 10 + 26 * pulse, fill=rgba(color, .35 * (1 - pulse)))
        hd.circle(hx, hy, 10, fill=rgba(color))
        hd.circle(hx, hy, 4.5, fill=rgba(B.INK))
        lay.alpha_composite(hd.done(), (x0, y0))
        cur_v = lerp(vals[k], vals[min(k + 1, n - 1)], upto - k)
        lab = de_num(cur_v, label_dec if abs(cur_v) < 10000 else 0)
        c = chip(lab, font("Bold", 24), rgba(B.BG), rgba(color), pad_x=12, h=38)
        cx = int(clamp(x0 + hx - c.size[0] + 18, x0, x0 + gx1 - c.size[0] - 4))
        cy = int(y0 + hy - 58) if hy > 70 else int(y0 + hy + 22)
        lay.alpha_composite(c, (cx, cy))


def series_for(rec, mode):
    """Gibt (Serie, x-Labels, Basislinie) für einen Chart-Modus zurück."""
    if mode == "intraday" and len(rec.get("intraday") or []) >= 6:
        s = rec["intraday"]
        n = len(s)
        labs = [(0, s[0][0]), (n // 2, s[n // 2][0]), (n - 1, s[-1][0])]
        return s, labs, rec.get("vortag")
    span = {"1w": 5, "1m": 22, "3m": 63, "6m": 126, "1j": 252, "intraday": 22}.get(mode, 63)
    s = rec.get("tage", [])[-span:]
    n = len(s)
    if n < 2:
        return s, None, None
    mon = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

    def lab(i):
        dd = date.fromisoformat(s[i][0])
        return f"{dd.day}. {mon[dd.month - 1]}"
    labs = [(0, lab(0)), (n // 2, lab(n // 2)), (n - 1, lab(n - 1))]
    return s, labs, None


# ───────────────────────── Szenen ─────────────────────────
def sc_hook(ctx, sz, t, dur):
    lay = layer()
    d = ImageDraw.Draw(lay)
    # Serien-Chip mit pulsierendem Punkt
    p, dy = enter(t, 0.0, 0.5)
    f = font("SemiBold", 26)
    label = B.SERIES
    tw = text_w(label, f, 4)
    cw_, ch_ = int(tw + 86), 58
    a = AA(cw_, ch_, 3)
    a.rrect((1, 1, cw_ - 1, ch_ - 1), 29, fill=rgba(B.VIO, .16), outline=rgba(B.VIO, .85), width=2)
    pulse = 0.5 + 0.5 * math.sin(t * 6)
    a.circle(32, 29, 8 + 5 * pulse, fill=rgba(B.VIO, .25))
    a.circle(32, 29, 7, fill=rgba(B.VIO))
    c = a.done()
    draw_text(ImageDraw.Draw(c), (56, 30), label, f, rgba(B.INK), anchor="lm", tracking=4)
    paste_alpha(lay, c, (L, 392 + dy), p)

    dl = ctx["datum_lang"]
    p2, dy2 = enter(t, 0.12)
    d.text((L, 480 + dy2), dl, font=font("Medium", 36), fill=rgba(B.GREY, p2), anchor="lt")

    # Schlagzeile – kinetisch: Zeilen steigen auf, Buchstabenabstand zieht sich zusammen
    z1 = sz.get("zeile1", "")
    y = 590
    lines = wrap(z1, font("Bold", 118), CW) if z1 else []
    if len(lines) > 2:
        lines = wrap(z1, font("Bold", 96), CW)
    for li, line in enumerate(lines[:3]):
        pz = ease_out_expo(prog(t, 0.22 + li * 0.12, 0.7))
        trk = int(26 * (1 - pz))
        fz = fit_font(line, "Bold", CW - trk * len(line), 118, 60)
        draw_text(d, (L, y + (1 - pz) * 70), line, fz, rgba(B.INK, pz), anchor="lt", tracking=trk)
        y += int(fz.size * 1.08)

    # Große Zahl (aus Kursdaten) oder zweite Zeile
    y += 24
    tk = sz.get("ticker")
    rec = ctx["data"]["werte"].get(tk) if tk else None
    if rec and rec.get("pct") is not None:
        pct = rec["pct"]
        col = move_color(pct)
        pv = ease_out_expo(prog(t, 0.55, 0.6))
        val = counter(pct, t, 0.55, 1.3)
        txt = de_pct(val)
        fz = fit_font(de_pct(pct) + "0", "Bold", CW - 140, 200, 90)
        # Leuchten hinter der Zahl
        gl = layer(W, 360)
        ga = AA(W, 360, 1)
        ga.rrect((L + 40, 110, L + 760, 260), 70, fill=rgba(col, .55 * pv))
        paste_alpha(lay, glow(ga.done(), 60, 1.0), (0, y - 80), 0.9 * (0.85 + 0.15 * math.sin(t * 3)))
        tri = AA(120, 120, 3)
        tri.tri(60, 62, 92, up=pct > 0, fill=rgba(col))
        paste_alpha(lay, tri.done(), (L - 6, y + 58 + (1 - pv) * 40), pv)
        tabular(d, (L + 128, y + 128 + (1 - pv) * 40), txt, fz, rgba(col, pv), anchor="lm")
        y += 250
    elif sz.get("zeile2"):
        pz = ease_out_expo(prog(t, 0.5, 0.7))
        fz = fit_font(sz["zeile2"], "Bold", CW, 120, 56)
        d.text((L, y + (1 - pz) * 50), sz["zeile2"], font=fz, fill=rgba(B.VIO, pz), anchor="lt")
        y += int(fz.size * 1.25)

    if sz.get("unterzeile"):
        pu = ease_out_cubic(prog(t, 0.85, 0.6))
        fu = font("Regular", 42)
        for i, line in enumerate(wrap(sz["unterzeile"], fu, CW)[:3]):
            d.text((L, y + 20 + i * 56 + (1 - pu) * 24), line, font=fu, fill=rgba(B.LAV, pu), anchor="lt")
    return lay


def sc_markt(ctx, sz, t, dur):
    lay = layer()
    kicker_title(lay, t, sz.get("kicker", "So lief der Tag"), sz.get("titel", "Die Märkte im Überblick"))
    werte = sz.get("werte") or ["^GSPC", "^NDX", "^GDAXI", "BTC-USD"]
    recs = [(tk, ctx["data"]["werte"].get(tk)) for tk in werte]
    recs = [(tk, r) for tk, r in recs if r][:6]
    rows = math.ceil(len(recs) / 2)
    gap = 22
    cw_ = (CW - gap) // 2
    top = 520
    ch_ = min(300, (B.STAGE_BOTTOM - top - gap * (rows - 1)) // max(1, rows))
    for i, (tk, r) in enumerate(recs):
        col, row = i % 2, i // 2
        x, y = L + col * (cw_ + gap), top + row * (ch_ + gap)
        delay = 0.25 + i * 0.11
        p = ease_out_expo(prog(t, delay, 0.6))
        if p <= 0:
            continue
        c = card(cw_, ch_, 26)
        cd = ImageDraw.Draw(c)
        pct = counter(r["pct"], t, delay + 0.15, 1.0)
        pc = pct_chip(pct if abs(pct) > 0.005 else r["pct"] * 0.001, 26)
        c.alpha_composite(pc, (cw_ - 20 - pc.size[0], 20))
        cd.text((24, 22 + pc.size[1] / 2), r["name"],
                font=fit_font(r["name"], "Medium", cw_ - 60 - pc.size[0], 30, 18), fill=rgba(B.GREY), anchor="lm")
        vt = value_text(r["kurs"], r["einheit"])
        fv = fit_font(vt, "Bold", cw_ - 48, 46, 26)
        tabular(cd, (24, 112), vt, fv, rgba(B.INK), anchor="ls")
        # Sparkline (Tagesverlauf)
        s, _, base = series_for(r, "intraday")
        vals = [v for _, v in s]
        sy, sh = 128, ch_ - 128 - 16
        if len(vals) >= 3 and sh > 30:
            sw = cw_ - 48
            lo = min(vals + ([base] if base else []))
            hi = max(vals + ([base] if base else []))
            rng = (hi - lo) or 1
            pp = ease_in_out_cubic(prog(t, delay + 0.3, 1.2))
            m = max(2, int(len(vals) * pp))
            pts = [(sw * j / (len(vals) - 1), sh - 4 - (sh - 8) * (v - lo) / rng) for j, v in enumerate(vals[:m])]
            colr = move_color(r["pct"])
            sp = AA(sw, sh, 2)
            if base:
                by = sh - 4 - (sh - 8) * (base - lo) / rng
                sp.dashed((0, by), (sw, by), rgba(B.GREY, .45), width=1.5, dash=6, gap=6)
            ar = AA(sw, sh, 2)
            ar.poly(pts + [(pts[-1][0], sh), (0, sh)], fill=(255, 255, 255, 255))
            c.alpha_composite(gradient_fill(ar.done(), rgba(colr, .30), rgba(colr, 0)), (24, sy))
            sp.line(pts, fill=rgba(colr), width=3.5)
            sp.circle(pts[-1][0], pts[-1][1], 5, fill=rgba(colr))
            c.alpha_composite(sp.done(), (24, sy))
        paste_alpha(lay, c, (x, y + (1 - p) * 60), p)
    return lay


def sc_aktie(ctx, sz, t, dur):
    lay = layer()
    d = ImageDraw.Draw(lay)
    tk = sz["ticker"]
    r = ctx["data"]["werte"].get(tk)
    kicker = sz.get("kicker", "Aktie im Fokus")
    p, dy = enter(t, 0)
    a = AA(14, 14, 4)
    a.circle(7, 7, 6, fill=rgba(B.VIO, p))
    lay.alpha_composite(a.done(), (L, int(B.STAGE_TOP + 12 + dy)))
    draw_text(d, (L + 26, B.STAGE_TOP + 19 + dy), kicker.upper(), font("SemiBold", 26), rgba(B.VIO, p),
              anchor="lm", tracking=4)
    if not r:
        d.text((L, 500), f"Keine Daten für {tk}", font=font("Bold", 50), fill=rgba(B.LOSS), anchor="lt")
        return lay
    name = sz.get("name") or r["name"]
    p1, dy1 = enter(t, 0.08)
    badge = ticker_badge(tk)
    paste_alpha(lay, badge, (L, 420 + dy1), p1)
    fn = fit_font(name, "Bold", CW - badge.size[0] - 24, 72, 40)
    d.text((L + badge.size[0] + 22, 420 + badge.size[1] / 2 + dy1), name, font=fn, fill=rgba(B.INK, p1), anchor="lm")

    # Kurs + Veränderung
    p2, dy2 = enter(t, 0.18)
    vt = value_text(r["kurs"], r["einheit"])
    fp = font("Bold", 78)
    tabular(d, (L, 600 + dy2), vt, fp, rgba(B.INK, p2), anchor="ls")
    pct = counter(r["pct"], t, 0.25, 1.2)
    pc = pct_chip(pct if abs(pct) > 0.005 else r["pct"] * 0.001, 40)
    paste_alpha(lay, pc, (L + tabular_w(vt, fp) + 26, 600 - pc.size[1] + 2 + dy2 - 6), p2)
    sub = sz.get("zusatz") or ("Kursverlauf heute" if sz.get("chart", "intraday") == "intraday" else "")
    if sub:
        d.text((L, 628 + dy2), sub, font=font("Regular", 26), fill=rgba(B.GREY, p2), anchor="lt")

    fakten = sz.get("fakten") or []
    cy0 = 690
    cy1 = 1050 if fakten else 1225
    mode = sz.get("chart", "intraday")
    s, labs, base = series_for(r, mode)
    ev_idx, ev_lab = None, None
    if sz.get("ereignis") and mode != "intraday":
        ed = sz["ereignis"].get("datum")
        for i, (dd, _) in enumerate(s):
            if dd >= ed:
                ev_idx = i
                break
        ev_lab = sz["ereignis"].get("label")
    col = move_color(r["pct"]) if mode == "intraday" else None
    draw_chart(lay, (L, cy0, R, cy1), s, t, t0=0.35, dur=min(2.4, dur * 0.45), baseline=base,
               color=col, x_labels=labs, event_idx=ev_idx, event_label=ev_lab, unit=r["einheit"])

    # Fakten-Karten
    if fakten:
        n = min(3, len(fakten))
        gap = 18
        fw = (CW - gap * (n - 1)) // n
        for i, fk in enumerate(fakten[:3]):
            delay = min(dur * 0.5, 2.4) + i * 0.22
            pf = ease_out_expo(prog(t, delay, 0.55))
            if pf <= 0:
                continue
            c = card(fw, 168, 22, accent=B.VIO)
            cd = ImageDraw.Draw(c)
            cd.text((26, 22), fk.get("label", ""), font=fit_font(fk.get("label", ""), "Medium", fw - 44, 24, 18),
                    fill=rgba(B.GREY), anchor="lt")
            wv = fk.get("wert", "")
            wcol = B.LOSS if wv.strip().startswith(("-", "−")) else B.GAIN if wv.strip().startswith("+") else B.INK
            cd.text((26, 60), wv, font=fit_font(wv, "Bold", fw - 44, 42, 24), fill=rgba(wcol), anchor="lt")
            if fk.get("delta"):
                dv = fk["delta"]
                neg = dv.strip().startswith(("-", "−"))
                cd.text((26, 120), dv, font=fit_font(dv, "SemiBold", fw - 44, 26, 16),
                        fill=rgba(B.LOSS if neg else B.GAIN), anchor="lt")
            elif fk.get("hinweis"):
                cd.text((26, 122), fk["hinweis"], font=fit_font(fk["hinweis"], "Regular", fw - 44, 24, 16),
                        fill=rgba(B.GREY), anchor="lt")
            paste_alpha(lay, c, (L + i * (fw + gap), 1068 + (1 - pf) * 50), pf)
    return lay


def _squarify(items, x, y, w, h):
    """Einfacher Squarified-Treemap-Algorithmus. items: [(gewicht, payload)] absteigend."""
    out = []
    items = list(items)
    total = sum(v for v, _ in items)
    if not items or total <= 0:
        return out
    scale = w * h / total
    rects = [(v * scale, p) for v, p in items]

    def worst(row, side):
        s = sum(a for a, _ in row)
        mx, mn = max(a for a, _ in row), min(a for a, _ in row)
        return max(side * side * mx / (s * s), (s * s) / (side * side * mn))

    while rects:
        side = min(w, h)
        row = [rects.pop(0)]
        while rects and worst(row + [rects[0]], side) <= worst(row, side):
            row.append(rects.pop(0))
        s = sum(a for a, _ in row)
        if w >= h:
            cw_ = s / h
            yy = y
            for a, pl in row:
                hh = a / cw_
                out.append((x, yy, cw_, hh, pl))
                yy += hh
            x += cw_
            w -= cw_
        else:
            rh = s / w
            xx = x
            for a, pl in row:
                ww = a / rh
                out.append((xx, y, ww, rh, pl))
                xx += ww
            y += rh
            h -= rh
    return out


def sc_sektoren(ctx, sz, t, dur):
    lay = layer()
    kicker_title(lay, t, sz.get("kicker", "US-Sektoren"), sz.get("titel", "Wo das Geld hinfloss"))
    sek = ctx["data"].get("sektoren", {})
    items = sorted(((v["gewicht"], v) for v in sek.values()), key=lambda x: -x[0])
    box = (L, 540, R, B.STAGE_BOTTOM)
    rects = _squarify(items, box[0], box[1], box[2] - box[0], box[3] - box[1])
    mx = max([abs(v["pct"]) for v in sek.values()] + [1.5])
    order = sorted(range(len(rects)), key=lambda i: -abs(rects[i][4]["pct"]))
    rank = {i: k for k, i in enumerate(order)}
    for i, (x, y, w, h, v) in enumerate(rects):
        delay = 0.3 + rank[i] * 0.07
        p = ease_out_back(prog(t, delay, 0.55), 1.2)
        if p <= 0:
            continue
        g = 5
        tw_, th_ = max(10, w - 2 * g), max(10, h - 2 * g)
        k = clamp(abs(v["pct"]) / mx)
        col = move_color(v["pct"])
        fill = mix(B.AUB, mix(B.BG, col, .75), 0.18 + 0.72 * k)
        s = 0.86 + 0.14 * clamp(p, 0, 1.2)
        ww, hh = int(tw_ * s), int(th_ * s)
        if ww < 8 or hh < 8:
            continue
        a = AA(ww, hh, 2)
        a.rrect((0, 0, ww, hh), min(18, ww / 4, hh / 4), fill=rgba(fill), outline=rgba(mix(fill, col, .5), .9), width=2)
        tile = a.done()
        td = ImageDraw.Draw(tile)
        pv = counter(v["pct"], t, delay, 0.9)
        big = min(ww, hh)
        fsize = int(clamp(big * 0.22, 20, 48))
        nsize = int(clamp(big * 0.13, 16, 30))
        name = v["name"]
        fnm = fit_font(name, "Medium", ww - 20, nsize, 14)
        if hh > fsize + nsize + 22 and ww > 70:
            td.text((ww / 2, hh / 2 - fsize * 0.45), name, font=fnm, fill=rgba(B.INK, .85), anchor="mm")
            td.text((ww / 2, hh / 2 + nsize * 0.65), de_pct(pv), font=fit_font(de_pct(pv), "Bold", ww - 16, fsize, 14),
                    fill=rgba(B.INK), anchor="mm")
        elif ww > 50:
            td.text((ww / 2, hh / 2), de_pct(pv, 1), font=fit_font(de_pct(pv, 1), "Bold", ww - 10, fsize, 12),
                    fill=rgba(B.INK), anchor="mm")
        paste_alpha(lay, tile, (x + g + (tw_ - ww) / 2, y + g + (th_ - hh) / 2), clamp(p))
    p, _ = enter(t, 0.2)
    ImageDraw.Draw(lay).text((L, 510), "Kachelgröße ≈ Gewicht im S&P 500 · Sektor-ETFs von SPDR",
                             font=font("Regular", 22), fill=rgba(B.GREY, p * .9), anchor="lm")
    return lay


def sc_gewinner_verlierer(ctx, sz, t, dur):
    lay = layer()
    kicker_title(lay, t, sz.get("kicker", "Top & Flop"), sz.get("titel", "Gewinner und Verlierer"))
    idx = sz.get("_movers_idx", 0)
    mv = ctx["data"]["movers"][idx] if ctx["data"].get("movers") else []
    n = int(sz.get("anzahl", 3))
    tops = list(reversed(mv[-n:])) if mv else []
    flops = mv[:n] if mv else []
    mx = max([abs(m["pct"]) for m in tops + flops] + [1])
    d = ImageDraw.Draw(lay)

    def block(y, label, rows, col, up, base_delay):
        p, dy = enter(t, base_delay)
        a = AA(30, 30, 3)
        a.tri(15, 16, 22, up=up, fill=rgba(col, p))
        lay.alpha_composite(a.done(), (L, int(y + dy)))
        draw_text(d, (L + 40, y + 15 + dy), label, font("SemiBold", 26), rgba(col, p), anchor="lm", tracking=4)
        for i, m in enumerate(rows):
            yy = y + 54 + i * 98
            delay = base_delay + 0.15 + i * 0.12
            pr = ease_out_expo(prog(t, delay, 0.6))
            if pr <= 0:
                continue
            rr = card(CW, 92, 20)
            rd = ImageDraw.Draw(rr)
            rd.text((24, 30), m["name"], font=fit_font(m["name"], "Bold", 340, 34, 20), fill=rgba(B.INK), anchor="lm")
            rd.text((24, 66), m["ticker"].replace(".DE", ""), font=font("Regular", 22), fill=rgba(B.GREY), anchor="lm")
            bl = 300 * abs(m["pct"]) / mx * ease_out_cubic(prog(t, delay + 0.1, 0.9))
            bar = AA(320, 92, 3)
            bar.rrect((0, 34, 300, 58), 12, fill=rgba(B.AUB2))
            if bl > 2:
                bar.rrect((0, 34, max(24, bl), 58), 12, fill=rgba(col))
            rr.alpha_composite(bar.done(), (400, 0))
            pv = counter(m["pct"], t, delay + 0.1, 0.9)
            rd.text((CW - 24, 46), de_pct(pv), font=font("Bold", 34), fill=rgba(col), anchor="rm")
            paste_alpha(lay, rr, (L + (1 - pr) * 80, yy), pr)

    block(522, sz.get("label_top", "GEWINNER"), tops, B.GAIN, True, 0.2)
    block(522 + 54 + n * 98 + 26, sz.get("label_flop", "VERLIERER"), flops, B.LOSS, False, 0.2 + 0.15 + n * 0.12)
    return lay


def sc_zahl(ctx, sz, t, dur):
    lay = layer()
    d = ImageDraw.Draw(lay)
    y = kicker_title(lay, t, sz.get("kicker", "Zahl des Tages"), None)
    titel = sz.get("titel", "")
    p, dy = enter(t, 0.1)
    ft = font("Bold", 58)
    for i, line in enumerate(wrap(titel, ft, CW)[:3]):
        d.text((L, 430 + i * 72 + dy), line, font=ft, fill=rgba(B.INK, p), anchor="lt")
    tk = sz.get("ticker")
    rec = ctx["data"]["werte"].get(tk) if tk else None
    pv = ease_out_expo(prog(t, 0.4, 0.7))
    yv = 760
    farbe = {"gewinn": B.GAIN, "verlust": B.LOSS}.get(sz.get("farbe", ""), B.VIO)
    if sz.get("wert"):
        txt = sz["wert"]
        col = farbe
    elif rec:
        txt = value_text(counter(rec["kurs"], t, 0.4, 1.3), rec["einheit"])
        col = B.VIO
    else:
        txt, col = "–", B.GREY
    fv = fit_font(txt, "Bold", CW, 210, 80)
    ga = AA(W, 300, 1)
    ga.rrect((L + 60, 100, L + 720, 220), 60, fill=rgba(col, .5 * pv))
    paste_alpha(lay, glow(ga.done(), 55), (0, yv - 160), 0.8)
    tabular(d, (L, yv + (1 - pv) * 40), txt, fv, rgba(col, pv), anchor="lm")
    yb = yv + fv.size * 0.55 + 20
    if rec and not sz.get("ohne_veraenderung"):
        pc = pct_chip(rec["pct"], 36)
        paste_alpha(lay, pc, (L, yb), pv)
        yb += pc.size[1] + 18
    if sz.get("unterzeile"):
        pu = ease_out_cubic(prog(t, 0.8, 0.6))
        fu = font("Regular", 38)
        for i, line in enumerate(wrap(sz["unterzeile"], fu, CW)[:2]):
            d.text((L, yb + i * 50), line, font=fu, fill=rgba(B.LAV, pu), anchor="lt")
        yb += 110
    if rec and sz.get("chart"):
        s, labs, base = series_for(rec, sz["chart"])
        top = max(int(yb + 20), 1000)
        if B.STAGE_BOTTOM - top > 150:
            draw_chart(lay, (L, top, R, B.STAGE_BOTTOM), s, t, t0=0.9, dur=1.8, baseline=base,
                       x_labels=labs, color=B.VIO if sz.get("neutral") else None)
    return lay


def sc_bild(ctx, sz, t, dur):
    lay = layer()
    kicker_title(lay, t, sz.get("kicker", "Im Blick"), None)
    img = ctx["bilder"].get(sz.get("_bild_key"))
    p, dy = enter(t, 0.1, 0.7)
    bw, bh = CW, 600
    if img is not None:
        z = 1.0 + 0.07 * prog(t, 0, max(dur, 1))
        iw, ih = img.size
        sc = max(bw / iw, bh / ih) * z
        im = img.resize((int(iw * sc), int(ih * sc)), Image.LANCZOS)
        ox, oy = (im.size[0] - bw) // 2, (im.size[1] - bh) // 2
        im = im.crop((ox, oy, ox + bw, oy + bh)).convert("RGBA")
        m = AA(bw, bh, 2)
        m.rrect((0, 0, bw, bh), 30, fill=(255, 255, 255, 255))
        im.putalpha(m.done().getchannel("A"))
        sh = AA(bw + 80, bh + 80, 1)
        sh.rrect((40, 50, bw + 40, bh + 50), 30, fill=(0, 0, 0, 200))
        paste_alpha(lay, glow(sh.done(), 28), (L - 40, 430 - 40 + dy), p)
        paste_alpha(lay, im, (L, 430 + dy), p)
    d = ImageDraw.Draw(lay)
    y = 1060
    if sz.get("titel"):
        p2, dy2 = enter(t, 0.35)
        ft = font("Bold", 54)
        for i, line in enumerate(wrap(sz["titel"], ft, CW)[:2]):
            d.text((L, y + i * 66 + dy2), line, font=ft, fill=rgba(B.INK, p2), anchor="lt")
            y += 0
        y += 66 * min(2, len(wrap(sz["titel"], ft, CW)))
    if sz.get("unterzeile"):
        p3, dy3 = enter(t, 0.5)
        d.text((L, y + 6 + dy3), sz["unterzeile"], font=fit_font(sz["unterzeile"], "Regular", CW, 34, 22),
               fill=rgba(B.LAV, p3), anchor="lt")
    return lay


def sc_termine(ctx, sz, t, dur):
    lay = layer()
    kicker_title(lay, t, sz.get("kicker", "Ausblick"), sz.get("titel", "Das wird jetzt wichtig"))
    items = sz.get("eintraege", [])[:4]
    d = ImageDraw.Draw(lay)
    x_line = L + 22
    y0 = 540
    step = min(170, (B.STAGE_BOTTOM - y0) // max(1, len(items)))
    pl = ease_in_out_cubic(prog(t, 0.2, 0.4 + 0.25 * len(items)))
    a = AA(W, H, 2)
    a.line([(x_line, y0 + 10), (x_line, y0 + 10 + (step * (len(items) - 1) + 20) * pl)], fill=rgba(B.AUB2), width=4)
    lay.alpha_composite(a.done())
    for i, it in enumerate(items):
        yy = y0 + i * step
        delay = 0.3 + i * 0.25
        p = ease_out_expo(prog(t, delay, 0.6))
        if p <= 0:
            continue
        dot = AA(60, 60, 3)
        dot.circle(30, 30, 14 * ease_out_back(prog(t, delay, 0.5)), fill=rgba(B.VIO))
        dot.circle(30, 30, 6, fill=rgba(B.BG, p))
        lay.alpha_composite(dot.done(), (x_line - 30, yy - 10))
        xo = L + 70 + (1 - p) * 40
        tag = it.get("tag", "")
        draw_text(d, (xo, yy + 20), tag.upper(), font("SemiBold", 26), rgba(B.VIO, p), anchor="lm", tracking=3)
        d.text((xo, yy + 44), it.get("titel", ""), font=fit_font(it.get("titel", ""), "Bold", R - xo, 42, 26),
               fill=rgba(B.INK, p), anchor="lt")
        if it.get("info"):
            d.text((xo, yy + 104), it["info"], font=fit_font(it["info"], "Regular", R - xo, 28, 18),
                   fill=rgba(B.GREY, p), anchor="lt")
    return lay


def sc_outro(ctx, sz, t, dur):
    lay = layer()
    d = ImageDraw.Draw(lay)
    p = ease_out_back(prog(t, 0.05, 0.7), 1.3)
    from .gfx import logo_mark
    lg = logo_mark(200)
    s = clamp(p, 0, 1.15)
    if s > 0.02:
        lgs = lg.resize((max(1, int(lg.size[0] * s)), max(1, int(lg.size[1] * s))), Image.LANCZOS)
        cx, cy = B.CX, 640
        gl = layer(520, 520)
        ga = AA(520, 520, 1)
        ga.circle(260, 260, 150, fill=rgba(B.GLOW1, .8))
        paste_alpha(lay, glow(ga.done(), 70), (cx - 260, cy - 260), (0.6 + 0.2 * math.sin(t * 2.4)) * clamp(p))
        lay.alpha_composite(lgs, (int(cx - lgs.size[0] / 2), int(cy - lgs.size[1] / 2)))
    p1, dy1 = enter(t, 0.3)
    t1 = sz.get("titel", "Morgen gibt’s die nächste Folge.")
    ft = fit_font(t1, "Bold", CW, 58, 34)
    d.text((B.CX, 860 + dy1), t1, font=ft, fill=rgba(B.INK, p1), anchor="mt")
    p2, dy2 = enter(t, 0.45)
    t2 = sz.get("unterzeile", "Folge für den täglichen Börsen-Überblick.")
    d.text((B.CX, 940 + dy2), t2, font=fit_font(t2, "Regular", CW, 36, 24), fill=rgba(B.LAV, p2), anchor="mt")
    p3, dy3 = enter(t, 0.65)
    c = card(CW, 150, 24)
    cd = ImageDraw.Draw(c)
    cd.text((CW / 2, 52), "Keine Anlageberatung. Alle Angaben ohne Gewähr.", font=font("SemiBold", 28),
            fill=rgba(B.INK), anchor="mm")
    cd.text((CW / 2, 100), "Bildung statt Empfehlung – Kurse ändern sich laufend.", font=font("Regular", 24),
            fill=rgba(B.GREY), anchor="mm")
    paste_alpha(lay, c, (L, 1060 + dy3), p3)
    return lay


SCENES = {
    "hook": sc_hook, "markt": sc_markt, "aktie": sc_aktie, "sektoren": sc_sektoren,
    "gewinner_verlierer": sc_gewinner_verlierer, "zahl": sc_zahl, "bild": sc_bild,
    "termine": sc_termine, "outro": sc_outro,
}

DEFAULT_SOURCE = {
    "markt": "Yahoo Finance (Kursdaten)", "aktie": "Yahoo Finance (Kursdaten)",
    "sektoren": "Yahoo Finance, SPDR Sektor-ETFs", "gewinner_verlierer": "Yahoo Finance (Kursdaten)",
    "outro": "",
}

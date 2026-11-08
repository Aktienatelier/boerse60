"""Sprachaufnahme verarbeiten: Transkription (faster-whisper, lokal & kostenlos),
Versprecher/wiederholte Satzanfänge herausschneiden, Pausen kürzen,
Klang „Variante C“ (1,1-fach, warmer Radioklang) und Wort-Zeitstempel für Untertitel.

Ohne Aufnahme erzeugt `estimate_timeline` eine geschätzte Zeitleiste (für Vorschauen).
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import wave
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

from .brand import ffmpeg_bin

TEMPO = 1.1
SR = 48000
SENT_GAP = 0.20          # Pause zwischen Sätzen (vor Tempo)
MAX_INNER_GAP = 0.42     # längere Pausen im Satz werden gekürzt …
INNER_GAP = 0.22         # … auf diese Länge
PAD_IN, PAD_OUT = 0.05, 0.09

# Variante C: warmer Radioklang, kein Exciter, kein Gate, ohne Verzerrung
VOICE_CHAIN = ",".join([
    "highpass=f=75",
    "equalizer=f=130:t=q:w=1.0:g=2.5",     # Wärme
    "equalizer=f=320:t=q:w=1.2:g=-1.5",    # Mulm weg
    "equalizer=f=3200:t=q:w=1.4:g=1.5",    # Verständlichkeit
    "equalizer=f=9000:t=h:w=0.8:g=-1.0",   # weiche Höhen, kein Zischen
    "acompressor=threshold=-20dB:ratio=3:attack=8:release=140:makeup=2",
    f"atempo={TEMPO}",
    "loudnorm=I=-14:TP=-1.5:LRA=7",
    "alimiter=limit=0.89",
])


# ───────────────────────── Text-Hilfen ─────────────────────────
_NUMW = {"0": "null", "1": "eins", "2": "zwei", "3": "drei", "4": "vier", "5": "fünf",
         "6": "sechs", "7": "sieben", "8": "acht", "9": "neun", "10": "zehn"}


def norm(tok: str) -> str:
    t = tok.lower().replace("%", " prozent").replace("€", " euro").replace("$", " dollar")
    t = re.sub(r"[^\wäöüß]+", "", t)
    return _NUMW.get(t, t)


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def script_sentences(ep: dict) -> list[dict]:
    """Alle Sätze aller Szenen in Reihenfolge, mit Szenen-Index."""
    out = []
    for si, sz in enumerate(ep["szenen"]):
        for s in split_sentences(sz.get("text", "")):
            words = s.split()
            out.append({"szene": si, "text": s, "words": words, "toks": [norm(w) for w in words]})
    return out


# ───────────────────────── Geschätzte Zeitleiste ─────────────────────────
def estimate_timeline(ep: dict, wps: float = 2.55) -> dict:
    """Ohne Aufnahme: Wortlängen nach Silben geschätzt, Pausen an Satzzeichen."""
    sents = script_sentences(ep)
    t, words, scene_start = 0.35, [], {}
    for s in sents:
        scene_start.setdefault(s["szene"], max(0.0, t - 0.25))
        for w in s["words"]:
            syl = max(1, len(re.findall(r"[aeiouyäöü]+", w.lower())))
            dur = (0.16 + 0.11 * syl) * (2.55 / wps)
            words.append({"w": w, "s": round(t, 3), "e": round(t + dur * .92, 3)})
            t += dur
            if w[-1:] in ",;:–":
                t += 0.16
        t += 0.30
    return _finish(ep, words, scene_start, t + 0.4, audio=None)


def _finish(ep, words, scene_start, total, audio):
    n = len(ep["szenen"])
    starts = [scene_start.get(i) for i in range(n)]
    # Szenen ohne Text bekommen 2,5 s
    for i in range(n):
        if starts[i] is None:
            prev_end = starts[i - 1] if i else 0.0
            starts[i] = (prev_end or 0.0) + 0.01
    starts[0] = 0.0
    scenes = []
    for i in range(n):
        end = starts[i + 1] if i + 1 < n else total + ep["szenen"][i].get("nachlauf", 1.6)
        if end - starts[i] < 1.2:
            end = starts[i] + 2.5
            if i + 1 < n:
                starts[i + 1] = end
        scenes.append({"start": round(starts[i], 3), "end": round(end, 3)})
    return {"words": words, "scenes": scenes, "dauer": scenes[-1]["end"], "audio": audio}


# ───────────────────────── Whisper & Schnitt ─────────────────────────
def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1500:])


def transcribe(wav16: Path, model_size="small"):
    from faster_whisper import WhisperModel
    print(f"  Transkribiere mit faster-whisper ({model_size}) …")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    audio = _read_wav(wav16)  # als Array übergeben – unabhängig von der PyAV-Version
    segs, _ = model.transcribe(audio, language="de", word_timestamps=True,
                               vad_filter=True, beam_size=5,
                               vad_parameters={"min_silence_duration_ms": 300})
    words = []
    for sg in segs:
        for w in sg.words or []:
            tok = norm(w.word)
            if tok:
                words.append({"raw": w.word.strip(), "tok": tok, "s": float(w.start), "e": float(w.end)})
    return words


def _tok_eq(a, b):
    return a == b or (len(a) > 3 and len(b) > 3 and SequenceMatcher(None, a, b).ratio() >= 0.8)


def _match(sent_toks, words, p):
    """Wie gut passt der Satz ab Position p? → (Anteil, letzter Index, Zuordnung)"""
    n = len(sent_toks)
    win = words[p:p + n + 5]
    sm = SequenceMatcher(None, sent_toks, [w["tok"] for w in win], autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size]
    hit = sum(b.size for b in blocks)
    if not blocks:
        return 0.0, p, {}
    mapping = {}
    for b in blocks:
        for k in range(b.size):
            mapping[b.a + k] = p + b.b + k
    last = max(mapping.values())
    return hit / max(1, n), last, mapping


def _first_hit(sent, words, frm, thr=0.6):
    toks = sent["toks"]
    for p in range(frm, len(words)):
        if _tok_eq(words[p]["tok"], toks[0]) or (len(toks) > 1 and _tok_eq(words[p]["tok"], toks[1])):
            r, last, mp = _match(toks, words, p)
            if r >= thr:
                return p
    return None


def align(sents, words):
    """Für jeden Satz die letzte vollständige Aufnahme vor dem nächsten Satz wählen
    (so fallen Versprecher und wiederholte Satzanfänge heraus)."""
    cursor, res, warn = 0, [], []
    for i, s in enumerate(sents):
        nxt = _first_hit(sents[i + 1], words, cursor) if i + 1 < len(sents) else None
        limit = nxt if nxt is not None else len(words)
        best = None
        for p in range(cursor, limit):
            t0 = s["toks"][0]
            if not (_tok_eq(words[p]["tok"], t0) or (len(s["toks"]) > 1 and _tok_eq(words[p]["tok"], s["toks"][1]))):
                continue
            r, last, mp = _match(s["toks"], words, p)
            if r >= 0.6:
                best = (p, last, mp, r)
        if best is None:
            if cursor < limit:
                p, last = cursor, limit - 1
                r, _, mp = _match(s["toks"], words, cursor)
                best = (p, last, mp, r)
                warn.append(f"Satz {i + 1} nur unsicher gefunden: „{s['text'][:50]}…“")
            else:
                warn.append(f"Satz {i + 1} fehlt in der Aufnahme: „{s['text'][:50]}…“")
                res.append(None)
                continue
        p, last, mp, r = best
        res.append({"p": p, "last": last, "map": mp})
        cursor = last + 1
    return res, warn


def _read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return a


def _write_wav(path: Path, a: np.ndarray, sr=SR):
    a = np.clip(a, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


def process_recording(ep: dict, wav_in: Path, out_dir: Path, model_size="small") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_bin()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        w16, w48 = td / "a16.wav", td / "a48.wav"
        _run([ff, "-y", "-i", str(wav_in), "-ac", "1", "-ar", "16000", str(w16)])
        _run([ff, "-y", "-i", str(wav_in), "-ac", "1", "-ar", str(SR), str(w48)])
        words = transcribe(w16, model_size)
        sents = script_sentences(ep)
        aligned, warn = align(sents, words)
        src = _read_wav(w48)

        pieces, out_words, scene_start = [], [], {}
        t_out = 0.25
        pieces.append(np.zeros(int(SR * 0.25), np.float32))
        fade = int(SR * 0.012)

        def add(a0, a1):
            nonlocal t_out
            seg = src[int(a0 * SR):int(a1 * SR)].copy()
            if len(seg) > 2 * fade:
                seg[:fade] *= np.linspace(0, 1, fade)
                seg[-fade:] *= np.linspace(1, 0, fade)
            pieces.append(seg)
            start = t_out
            t_out += len(seg) / SR
            return start

        for s, al in zip(sents, aligned):
            if al is None:
                continue
            span = words[al["p"]:al["last"] + 1]
            # Satz in Stücke an langen Pausen teilen
            chunks, cur = [], [span[0]]
            for a, b in zip(span, span[1:]):
                if b["s"] - a["e"] > MAX_INNER_GAP:
                    chunks.append(cur)
                    cur = [b]
                else:
                    cur.append(b)
            chunks.append(cur)
            tmap = []  # (in0, in1, out0)
            for ci, ch in enumerate(chunks):
                a0 = max(0.0, ch[0]["s"] - PAD_IN)
                a1 = ch[-1]["e"] + PAD_OUT
                o0 = add(a0, a1)
                tmap.append((a0, a1, o0))
                if ci < len(chunks) - 1:
                    pieces.append(np.zeros(int(SR * INNER_GAP), np.float32))
                    t_out += INNER_GAP

            def to_out(t):
                for a0, a1, o0 in tmap:
                    if t <= a1 + 1e-3:
                        return o0 + max(0.0, t - a0)
                a0, a1, o0 = tmap[-1]
                return o0 + (t - a0)

            # Skriptwörter (korrekte Schreibweise) mit Zeiten aus der Aufnahme
            n = len(s["words"])
            times = [None] * n
            for k, wi in al["map"].items():
                if 0 <= k < n and al["p"] <= wi <= al["last"]:
                    times[k] = (to_out(words[wi]["s"]), to_out(words[wi]["e"]))
            s_beg, s_end = to_out(span[0]["s"]), to_out(span[-1]["e"])
            known = [i for i, v in enumerate(times) if v]
            for k in range(n):
                if times[k] is None:
                    lo = max([i for i in known if i < k], default=None)
                    hi = min([i for i in known if i > k], default=None)
                    t0 = times[lo][1] if lo is not None else s_beg
                    t1 = times[hi][0] if hi is not None else s_end
                    gaps = (hi if hi is not None else n) - (lo if lo is not None else -1)
                    pos = k - (lo if lo is not None else -1)
                    a = t0 + (t1 - t0) * (pos - 1) / gaps
                    b = t0 + (t1 - t0) * pos / gaps
                    times[k] = (a, b)
            scene_start.setdefault(s["szene"], max(0.0, times[0][0] - 0.25))
            for wtxt, (a, b) in zip(s["words"], times):
                out_words.append({"w": wtxt, "s": a, "e": b})
            pieces.append(np.zeros(int(SR * SENT_GAP), np.float32))
            t_out += SENT_GAP

        pieces.append(np.zeros(int(SR * 0.4), np.float32))
        cut = td / "cut.wav"
        _write_wav(cut, np.concatenate(pieces))
        final = out_dir / "stimme_final.wav"
        _run([ff, "-y", "-i", str(cut), "-af", VOICE_CHAIN, "-ar", str(SR), str(final)])

    # Zeiten auf 1,1-faches Tempo umrechnen
    for w in out_words:
        w["s"] = round(w["s"] / TEMPO, 3)
        w["e"] = round(w["e"] / TEMPO, 3)
    scene_start = {k: v / TEMPO for k, v in scene_start.items()}
    total = (t_out + 0.4) / TEMPO
    tl = _finish(ep, out_words, scene_start, total, audio=str(final))
    tl["hinweise"] = warn
    (out_dir / "zeitleiste.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    for w_ in warn:
        print("  ⚠", w_)
    return tl

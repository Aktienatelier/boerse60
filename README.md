# Börse in 60 Sekunden – Aktienatelier

Tägliches Kurzvideo (1080 × 1920, 30 fps) für TikTok und Instagram: Kursdaten, animierte Charts, Sektoren-Heatmap, Gewinner und Verlierer, Untertitel Wort für Wort. Alles ist kostenlos, Kursdaten kommen von Yahoo Finance.

## Einmalig einrichten

```bash
pip install -r requirements.txt
```
Außerdem wird **ffmpeg** benötigt (Windows: `winget install ffmpeg`, Mac: `brew install ffmpeg`).

- **Logo:** dein freigestelltes Logo-Zeichen als `assets/logo_zeichen.png` ablegen. Ohne die Datei erscheint ein Platzhalter.
- **Schrift:** Poppins wird beim ersten Start automatisch nach `fonts/` geladen.
- **Hintergrund-Clips und Fotos (optional):** kostenlosen Schlüssel auf pexels.com/api holen und als Umgebungsvariable `PEXELS_API_KEY` setzen. Clips werden nur im Hintergrund lila eingefärbt, Fotos im Vordergrund bleiben im Original. Ohne Schlüssel läuft der animierte Marken-Hintergrund.

## Täglicher Ablauf

1. **Gegen 23 Uhr** kommt der Sprechtext mit der Folgen-Datei `JJJJ-MM-TT.json`. Die Datei kommt in den Ordner `folgen/`.
2. **Einsprechen** in Audacity, in einem Rutsch. Bei einem Versprecher einfach den Satz neu beginnen. Das Programm behält jeweils den letzten vollständigen Durchgang und schneidet den Rest heraus. Als WAV exportieren.
3. **Rendern:**
   ```bash
   python boerse60.py render folgen/2026-11-09.json --audio aufnahme.wav
   ```
4. **Morgens hochladen:** Die Dateien liegen in `ausgabe/<datum>/`, nämlich `boerse60_<datum>.mp4`, `titelbild.png` und `caption.txt` (zwei Varianten plus Hashtags).

Die Stimme wird automatisch nach Variante C bearbeitet: 1,1-fach schneller bei gleicher Tonhöhe, warmer Radioklang, Lautheit −15 LUFS (zwei Durchgänge), lange Pausen gekürzt – identisch mit der Kette aus den bisherigen Videos (Säubern „natürlich“ + Variante C).

## Weitere Befehle

| Befehl | Wozu |
|---|---|
| `python boerse60.py skript folgen/X.json` | Sprechtext anzeigen und als `sprechtext.txt` speichern |
| `python boerse60.py standbilder folgen/X.json` | ein PNG pro Szene, als schneller Check in wenigen Sekunden |
| `python boerse60.py vorschau folgen/X.json` | stummes Video mit geschätztem Timing (15 fps) |
| `python boerse60.py daten folgen/X.json` | Kursdaten neu laden (`--neu` geht auch bei render) |
| `--musik datei.mp3` | leise Hintergrundmusik dazumischen |
| `--whisper small` | schnellere, etwas ungenauere Erkennung (Standard: medium) |

## Szenentypen

`hook` · `markt` · `aktie` · `zahl` · `sektoren` · `gewinner_verlierer` · `bild` · `termine` · `outro`
Ein vollständiges Beispiel steht in `folgen/2026-11-06.json`. Jede Szene hat einen eigenen `"text"` als Sprechtext und optional eine `"quelle"`, die unten eingeblendet wird.

## Design-Regeln (fest eingebaut)

- Farbsystem „Nacht“: Nachtschwarz, Orchidee als Akzent, Grün und Rot nur für Gewinne und Verluste, immer mit Vorzeichen und Dreieck.
- Freie Ränder: oben 230 px, unten 430 px, rechts 140 px. Untertitel, Quelle und „Keine Anlageberatung“ liegen innerhalb des sicheren Bereichs.
- Zahlen mit fester Ziffernbreite, damit beim Hochzählen nichts zittert.

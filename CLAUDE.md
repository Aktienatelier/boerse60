# Börse in 60 Sekunden – Arbeitsanleitung für Claude

Tägliches TikTok/Instagram-Kurzvideo von **Aktienatelier** (deutschsprachige Finanzbildung, BaFin-konform: Fakten und Einordnung, **keine Anlageberatung**). Der Nutzer arbeitet **nur am Handy**: Er liest den Sprechtext, nimmt ihn als Sprachmemo auf, schickt die Datei in die Sitzung und bekommt das fertige Video zurück. **Immer auf Deutsch antworten.**

## Einrichtung (jede neue Sitzung)
```bash
pip install --break-system-packages -q -r requirements.txt
```
ffmpeg ist vorhanden. Schrift und Whisper-Modell werden beim ersten Lauf automatisch geladen.

## Teil A – Abendrecherche (ca. 23 Uhr, nach US-Börsenschluss)
1. **Daten:** `python tagesdaten.py` ausführen → Indizes, Sektoren, Top/Flop (US und DAX). **Alle Zahlen im Sprechtext müssen dazu passen.** Hat die US-Börse nicht gehandelt (Feiertag), eine kürzere Folge mit Europa-Fokus machen oder melden, dass heute keine Folge nötig ist.
2. **Recherche:** Mit WebSearch/WebFetch die 1–2 wichtigsten Geschichten des Tages finden (Quartalszahlen, Übernahmen, Notenbank, Konjunktur, Skandale). Nur seriöse Quellen (Reuters, CNBC, Bloomberg, Handelsblatt, FAZ, tagesschau, Unternehmensmeldungen). Gründe für Kursbewegungen nur nennen, wenn eine Quelle sie belegt, sonst vorsichtig formulieren. Termine nur mit geprüftem Datum.
3. **Sprechtext:**
   - 210–240 Wörter, damit das Video über 1 Minute lang wird (die Stimme läuft 1,1-fach).
   - Locker, dynamisch, kurze Sätze, gesprochene Sprache. Starker Aufhänger im ersten Satz.
   - Zahlen so schreiben, wie man sie spricht („elf Prozent“).
   - **Das Wort „Aktienatelier“ darf nicht vorkommen.**
   - Keine Kauf-/Verkaufsempfehlungen, keine eigenen Kursziele. Reale Personen nur sinngemäß wiedergeben, niemals erfundene Zitate. Politik neutral und ohne Reizwörter.
   - Die letzte Szene endet mit „Keine Anlageberatung, nur Einordnung.“ und „Bis morgen!“ (freitags „Bis Montag!“).
4. **Folgen-Datei** `folgen/JJJJ-MM-TT.json` schreiben. Das Format zeigt `folgen/2026-11-06.json`, die Szenentypen stehen unten.
   - Bei `gewinner_verlierer` immer `"tickers"` mit genau den 6 Werten (3 Top, 3 Flop) aus `tagesdaten.py` angeben.
5. **Prüfen:**
   - `python boerse60.py standbilder folgen/<datum>.json` ausführen.
   - Die PNGs ansehen: Text darf nicht abgeschnitten sein, die Ränder müssen frei bleiben (oben 230 px, unten 430 px, rechts 140 px), die Zahlen müssen stimmen. Fehler beheben.
6. **Archivieren:** `git add folgen/ && git commit -m "Folge <datum>" && git push`. Vorher `git pull --rebase`.
7. **Ausliefern:**
   - Mit **SendUserMessage** schicken:
     - Überschrift „Börse in 60 Sekunden – <Wochentag, Datum>“
     - je Szene „[Nr]“ und den Sprechtext
     - Wortzahl
     - die zwei Captions mit Hashtags
     - Quellenliste mit Links
   - Mit **SendUserFile** das Standbild der ersten Szene als Vorschau schicken.
   - Zum Schluss: „Sprich den Text als Sprachmemo ein und schick mir die Datei hier in den Chat – Versprecher sind egal, einfach den Satz neu beginnen.“

## Teil B – Aufnahme kommt (Antwort des Nutzers in derselben Sitzung)
1. Die angehängte Audiodatei finden (m4a, mp3, wav, ogg, alles geht).
2. Rendern:
   ```bash
   python boerse60.py render folgen/<datum>.json --audio <datei>
   ```
   Das Programm schneidet Versprecher und wiederholte Satzanfänge heraus, kürzt Pausen und bearbeitet die Stimme mit der festen Kette aus `b60/audio.py` (Säubern „natürlich“ + Variante C: 1,1-fach, warmer Radioklang, −15 LUFS). Diese Einstellungen nicht ändern. Die Untertitel kommen aus dem Skript.
3. Warnungen in der Ausgabe beachten (Satz nicht gefunden, Video unter 61 s) und dem Nutzer kurz melden.
4. Mit **SendUserFile** schicken: `ausgabe/<datum>/boerse60_<datum>.mp4` und `titelbild.png`. Den Inhalt von `caption.txt` als Nachricht zum Kopieren dazu.
5. Videos **nicht** ins Repository committen, sie sind zu groß.

## Szenentypen (Felder)
- **hook:** `zeile1` (max. 4 Wörter); `ticker` (zeigt die Tagesveränderung groß) oder `zeile2`; `unterzeile`
- **markt:** `titel`; `werte` mit 4 oder 6 Yahoo-Tickern
- **aktie:**
  - `ticker`, `name`
  - `chart`: intraday | 1m | 3m | 6m | 1j
  - `ereignis`: {datum, label}, nur bei Tages-Charts
  - `fakten`: bis zu 3 × {label, wert, hinweis}; `wert` mit +/− wird grün/rot
- **zahl:**
  - `kicker`, `titel`
  - `wert` (Text) oder `ticker`
  - `farbe`: gewinn | verlust
  - optional: `unterzeile`, `chart`, `ohne_veraenderung`
- **sektoren:** nur `text`
- **gewinner_verlierer:** `tickers` (6), `titel`
- **bild:** `titel`, `unterzeile`, `bild_suche` (englisch, Pexels; keine Logos, keine Personen)
- **termine:** `titel`, `eintraege`: bis zu 4 × {tag, titel, info}
- **outro:** `titel`, `text`

Jede Szene hat dazu `text` (Sprechtext) und optional `quelle` (wird unten eingeblendet).

## Design-Regeln
- Farbsystem „Nacht“ (`b60/brand.py`)
- Grün/Rot nur für Gewinne und Verluste
- Quelle und „Keine Anlageberatung“ in jeder Szene
- Hintergrund-Clips nur im Hintergrund lila einfärben, Vordergrundbilder nie

# 🧰 Fortnite Chest Counter

Zählt, wie viele Truhen du in Fortnite insgesamt geöffnet hast. Der Zähler aktualisiert sich live und wird als Overlay direkt über dem Spiel angezeigt.

- **Automatische Erkennung** per Bilderkennung: Das Tool erkennt den Truhen-Hinweis und deinen Tastendruck.
- **Hotkeys** zum Korrigieren: `´` = +1, `ß` = −1
- **Startwert** setzen: beim ersten Start, jederzeit mit `F6` oder per `--set`
- **Gesamtzahl** wird dauerhaft gespeichert und bleibt auch nach Neustarts erhalten.
- **Ingame-Overlay**: transparent, immer im Vordergrund und klick-durchlässig. Die Position lässt sich verschieben.

> **Ist das erlaubt?** Das Tool liest **keinen** Spielspeicher, verändert keine Spieldateien und injiziert nichts. Es macht nur Screenshots eines kleinen Bildschirmausschnitts und zeichnet ein eigenes Fenster darüber, genau wie OBS oder das Discord-Overlay.

> **Warum Bilderkennung?** Epic stellt die Zahl der geöffneten Truhen nirgends bereit, weder per API noch in Statistiken oder Logdateien. Das Tool muss das Öffnen deshalb selbst erkennen.

---

## Installation (Windows)

1. Installiere **Python 3.10 oder neuer** von <https://www.python.org/downloads/>. Setze beim Setup den Haken bei **„Add python.exe to PATH“**.
2. Lade dieses Repository herunter (grüner Button „Code“ → „Download ZIP“) und entpacke es.
3. Starte **`start.bat`** per Doppelklick. Beim ersten Mal werden automatisch alle Abhängigkeiten installiert.
4. Beim allerersten Start fragt das Tool nach deinem **Startwert**, also wie viele Truhen du schon geöffnet hattest, bevor du mit dem Zählen anfängst.

Optional baut **`build_exe.bat`** eine einzelne `dist\FortniteChestCounter.exe`, die ohne Python-Installation läuft.

### Fortnite-Einstellung (wichtig für das Overlay)
Stell in Fortnite unter **Einstellungen → Grafik → Fenstermodus** die Option **„Rahmenloses Fenster“** (bzw. „Fullscreen Windowed“) ein. Im exklusiven Vollbild verdeckt das Spiel jedes andere Fenster, und das Overlay ist nicht zu sehen.

---

## Einrichtung der automatischen Erkennung (einmalig)

1. Geh in Fortnite zu einer Truhe, zum Beispiel im Kreativmodus oder im Match, und schau sie an, sodass der Hinweis **„Truhe / Durchsuchen“** erscheint.
2. Drück **`F9`**. Das Tool speichert den Hinweis als Vorlage, und im Overlay erscheint „Vorlage gespeichert“.
3. Fertig. Ab jetzt zählt das Tool automatisch **+1**, sobald du die Truhe mit deiner Interaktionstaste öffnest.

Tipps:
- Am besten kalibrierst du vor einem eher dunklen Hintergrund. Das Tool schneidet automatisch auf den hellen Text zu.
- Du kannst mehrmals `F9` drücken, zum Beispiel für verschiedene Truhenarten. Alle Vorlagen werden verwendet.
- Läuft die Erkennung schlecht, lösch den Ordner `templates` im Datenordner (siehe unten) und kalibriere neu.

### So zählt die Erkennung
Das Tool scannt etwa 15-mal pro Sekunde den Bereich rechts vom Fadenkreuz. Es zählt nur, wenn alle drei Bedingungen erfüllt sind:
1. Der Truhen-Hinweis ist sichtbar.
2. Du drückst deine Interaktionstaste (Standard `E`).
3. Der Hinweis verschwindet kurz danach, weil die Truhe offen ist.

Läufst du an einer Truhe nur vorbei oder drückst E ohne Hinweis, zählt nichts. Ein Cooldown von 1,5 s verhindert Doppelzählungen.

---

## Hotkeys

| Taste | Funktion |
|---|---|
| `´` (links neben Backspace) | **+1 Truhe** |
| `ß` | **−1 Truhe** (Korrektur) |
| `F6` | Zählerstand / Startwert manuell setzen |
| `F9` | Truhen-Hinweis als Vorlage kalibrieren |
| `F10` | Overlay verschieben (mit der Maus ziehen, nochmal `F10` zum Fixieren) |
| `F11` | Auto-Erkennung pausieren/fortsetzen |
| `Strg+Shift+F12` | Programm beenden |

Die Hotkeys funktionieren global, also auch, während Fortnite im Fokus ist.

### Startwert / Zählerstand setzen
- **Beim ersten Start** erscheint automatisch ein Eingabefenster.
- **Jederzeit** öffnet `F6` das Eingabefenster. Zahl eintippen und mit Enter bestätigen. Wechsle bei Bedarf kurz mit Alt+Tab aus dem Spiel.
- **Per Kommandozeile:** `start.bat --set 250`, alternativ `python run.py --set 250`.
- Den aktuellen Stand zeigt `python run.py --show` an.

---

## Konfiguration

Alle Einstellungen stehen in `config.json` im **Datenordner**:

```
%APPDATA%\FortniteChestCounter\
  config.json   – Einstellungen
  stats.json    – dein Zählerstand
  templates\    – Vorlagen aus der Kalibrierung
  log.txt       – Protokoll (bei Problemen hier nachschauen)
```

Wichtige Optionen:

| Option | Standard | Bedeutung |
|---|---|---|
| `hotkeys.*` | siehe oben | Tastennamen (z. B. `"f8"`, `"ctrl+k"`) oder Scan-Codes als Zahl |
| `interact_key` | `"e"` | Deine Interaktionstaste in Fortnite |
| `detection.region` | `[0.48, 0.45, 0.78, 0.70]` | Scan-Bereich als Anteil des Bildschirms (links, oben, rechts, unten) |
| `detection.match_threshold` | `0.75` | Wie genau die Vorlage passen muss: höher = strenger, niedriger = toleranter |
| `detection.brightness_threshold` | `200` | Ab welcher Helligkeit ein Pixel als Text zählt |
| `detection.monitor` | `1` | Bildschirm, auf dem Fortnite läuft |
| `overlay.font_size`, `overlay.color`, `overlay.label` | | Aussehen des Overlays |

Nach Änderungen das Programm neu starten.

---

## Probleme?

| Problem | Lösung |
|---|---|
| Overlay ist im Spiel nicht sichtbar | Fortnite auf **„Rahmenloses Fenster“** stellen |
| Hotkeys reagieren nicht | `start.bat` per Rechtsklick **als Administrator** starten |
| `´` reagiert nicht | `´` ist eine Tottaste. Trag in `config.json` bei `"increment"` den Scan-Code `13` ein oder nimm eine andere Taste |
| Truhen werden nicht gezählt | Neu kalibrieren (`F9`), `match_threshold` z. B. auf `0.65` senken, `interact_key` prüfen |
| Es wird zu viel gezählt | `match_threshold` z. B. auf `0.85` erhöhen. Mit `ß` korrigieren |
| Andere Auflösung / mehrere Monitore | `detection.monitor` und `detection.region` anpassen, dann neu kalibrieren |

Wer die Interaktion auf die Maus (z. B. das Mausrad) gelegt hat, zählt mit den Hotkeys. Die Erkennung wertet nur Tastaturtasten aus.

---

## Entwicklung

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Struktur:

```
chest_counter/
  app.py       – verdrahtet Erkennung, Hotkeys, Speicherung, Overlay
  detector.py  – Bildverarbeitung + Zustandsautomat (ohne Bildschirm testbar)
  capture.py   – Bildschirmaufnahme (mss)
  hotkeys.py   – globale Hotkeys (keyboard)
  overlay.py   – transparentes tkinter-Overlay
  storage.py   – Zählerstand (atomar gespeichert)
  config.py    – Standardwerte + config.json
tests/         – Tests mit synthetischen Bildern
```

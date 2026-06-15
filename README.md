# ⚽ Spielplan

Eine einfache, große, übersichtliche Fußball-App für Android (und jedes Handy):
**Wann spielt wer gegen wen, auf welchem Sender, mit Quoten und KI-Prognose** –
für Bundesliga, Champions League, WM und EM. Mit FC Bayern, Deutschland und
Bosnien immer ganz oben.

---

## 1. Sofort ansehen (auf deinem Laptop)

Du brauchst nichts zu installieren – **Python ist bereits vorhanden.**

1. Doppelklick auf **`Vorschau-starten.bat`**
2. Der Browser öffnet sich mit der App (`http://localhost:8000` bzw. `:8123`).
3. Zum Beenden einfach das schwarze Fenster schließen.

Du siehst dann **Beispieldaten** (Stand: WM-Zeit, Juni 2026). Echte Live-Daten
kommen, sobald der Updater mit API-Schlüsseln läuft (Schritt 3).

---

## 2. Die App auf das Handy deines Vaters bringen

Die App ist eine **PWA** (eine Web-App, die sich wie eine echte App installiert).
Sobald sie ins Internet gestellt ist (Schritt 3), geht das so:

1. Den Link der App im **Chrome** auf seinem Handy öffnen.
2. Oben rechts auf **⋮ → „App installieren"** (bzw. „Zum Startbildschirm hinzufügen").
3. Fertig – es erscheint ein **App-Icon** auf dem Startbildschirm. Beim Tippen
   startet die App im Vollbild, ganz ohne Browser-Leiste.

> Kein Google Play, keine Anmeldung, keine Kosten – genau richtig für eine Person.

---

## 3. „Immer aktuell, ohne dass der Laptop an ist"

Dafür laufen zwei Dinge **kostenlos in der Cloud** über ein GitHub-Konto:

- **GitHub Pages** stellt die App ins Internet (der Link für Schritt 2).
- **GitHub Actions** führt den Updater automatisch aus (alle paar Stunden) und
  aktualisiert die Daten – egal ob dein Laptop an ist oder nicht.

### Einrichtung (einmalig, ~20 Minuten)

1. **GitHub-Konto** erstellen (gratis) und ein neues Repository anlegen, z. B. `spielplan`.
2. Diesen Ordner dort hochladen (per GitHub Desktop oder `git push`).
3. Unter **Settings → Pages**: Quelle „Deploy from a branch", `main`-Branch, Ordner `/docs` stellen.
   → Die App ist dann unter `https://DEINNAME.github.io/spielplan/` erreichbar.
4. Unter **Settings → Secrets and variables → Actions** die API-Schlüssel als
   *Secrets* hinterlegen (siehe Schritt 4): `FOOTBALL_DATA_API_KEY`,
   `ODDS_API_KEY`, `ANTHROPIC_API_KEY`.
5. Fertig. Der Updater läuft ab jetzt automatisch (siehe `.github/workflows/update.yml`)
   und kann unter **Actions** auch jederzeit manuell gestartet werden.

---

## 4. API-Schlüssel besorgen (für echte Daten)

| Wofür | Anbieter | Gratis? | Schlüssel-Name |
|---|---|---|---|
| Spielpläne | [football-data.org](https://www.football-data.org/) | Ja (mit Limit) | `FOOTBALL_DATA_API_KEY` |
| Quoten | [the-odds-api.com](https://the-odds-api.com/) | Ja (500/Monat) | `ODDS_API_KEY` |
| KI-Prognose | [Google Gemini](https://aistudio.google.com/apikey) **(empfohlen)** | Ja (Gratis-Tarif) | `GOOGLE_API_KEY` |
| KI-Prognose (Alternative) | [Anthropic / Claude](https://console.anthropic.com/) | Nein (günstig) | `ANTHROPIC_API_KEY` |

**KI-Anbieter:** Setze **entweder** `GOOGLE_API_KEY` **oder** `ANTHROPIC_API_KEY`.
Ist ein Google-Key gesetzt, nutzt der Updater automatisch **Gemini**. Empfohlenes
Modell (Sweet Spot aus Preis & Qualität): **`gemini-2.5-flash-lite`** – günstig,
mit Gratis-Tarif, für unsere kurzen Prognosen mehr als ausreichend. Etwas „klüger"
geht mit `gemini-2.5-flash`. Den Key bekommst du gratis im
[Google AI Studio](https://aistudio.google.com/apikey).

**Zum lokalen Testen** auf dem Laptop:
1. `updater/config.example.json` kopieren zu `updater/config.json`
2. Schlüssel eintragen
3. Im Ordner `updater` ausführen: `python update.py`

Der Updater schreibt dann `docs/data.json` neu. Fehlt ein Schlüssel, wird der
jeweilige Teil übersprungen und die vorhandenen Daten bleiben erhalten.

---

## 5. TV-Sender (vollautomatisch – keine Pflege nötig)

Die TV-Sender werden **automatisch** bestimmt, in zwei Stufen (in `updater/tv_sources.py`):

1. **Live-Quelle [fussballgucken.info](https://fussballgucken.info/fussball-heute)** –
   liefert den **exakten Sender je Spiel** (Sky/DAZN/ARD/ZDF/Amazon/MagentaTV …).
   Die Seite hat eine offene `robots.txt` und sauber strukturiertes HTML; der
   Updater liest nur die Fakten (Sender je Spiel) höflich und gecacht aus und
   ordnet sie deinen Spielen über **Datum + Anstoßzeit** zu.
2. **Regel-Engine** aus den mehrjährig festen Übertragungsrechten – deckt alles
   ab, was die Live-Quelle (noch) nicht hat, und greift auch, falls die Seite mal
   ausfällt. Der bekannte **Champions-League-Rechtewechsel ab 2027/28**
   (DAZN/Amazon → Paramount+/Amazon) ist als Stichtag bereits eingebaut.

> **Du musst hier nichts pflegen.** Optional kannst du in
> `updater/overrides/broadcasters.json` einzelne Spiele manuell übersteuern
> (Abschnitt `byMatch`) – das hat dann Vorrang, ist aber für den Normalbetrieb
> nicht nötig. Abschalten der Live-Quelle: `USE_TV_SCRAPE=0` (dann nur Regeln).

---

## 6. Was die App alles kann

- 📅 **Heute zuerst**, Wischen/Pfeile für Vergangenheit & Zukunft, Datum antippen = direkt springen
- ⭐ **FC Bayern, Deutschland, Bosnien** immer ganz oben (nur Männer-Profis)
- 📺 **TV-Sender groß hervorgehoben**, frei empfangbar grün markiert
- 💰 **Quoten** (1 / X / 2)
- 🤖 **KI-Prognose** mit Wahrscheinlichkeit und Stichpunkt-Begründung
- ⚡ **Live-Ergebnis** während des Spiels (App lädt automatisch nach)
- ⏰ **Erinnerung**: legt das Spiel in den Handy-Kalender (erinnert 1 Std. vorher)
- ↗ **Teilen für WhatsApp**: einzelnes Spiel, ganzer Tag, alle Spiele eines Teams
  oder eines Wettbewerbs – als sauberer Text
- 📴 **Offline**: zeigt die zuletzt geladenen Daten auch ohne Internet
- 🔠 **Große-Schrift-Modus** in den Einstellungen
- 🌙 Heller & dunkler Modus automatisch
- „Maximal Bekanntes": steht Gegner/Uhrzeit/Sender noch nicht fest, wird das
  angezeigt, was sicher ist – und automatisch ergänzt, sobald mehr feststeht.

---

## 7. Ordnerstruktur

```
Spielplan/
├─ docs/                 ← die App (das, was auf dem Handy läuft; GitHub Pages liefert diesen Ordner aus)
│  ├─ index.html, styles.css, app.js
│  ├─ manifest.webmanifest, sw.js   (Installierbarkeit + Offline)
│  ├─ icons/
│  └─ data.json          ← die Daten (vom Updater erzeugt)
├─ updater/              ← das Python-Programm, das die Daten holt
│  ├─ update.py
│  ├─ config.example.json
│  └─ overrides/broadcasters.json   ← TV-Sender-Regeln
├─ .github/workflows/update.yml     ← automatischer Lauf in der Cloud
└─ Vorschau-starten.bat             ← lokale Vorschau (Doppelklick)
```

---

## 8. Kosten

| Posten | Kosten |
|---|---|
| Hosting (GitHub Pages) | 0 € |
| Automatischer Updater (GitHub Actions) | 0 € |
| Spielpläne + Quoten (Gratis-Tarife) | 0 € |
| TV-Sender (Live-Quelle + Regeln) | 0 € |
| KI-Prognosen mit **Gemini 2.5 Flash-Lite** | **0 € im Gratis-Tarif**, bei Bezahl-Nutzung Cent-Beträge |

→ In der Praxis **rund 0 €/Monat**, weit unter den vereinbarten ~10 €.
Damit nicht unnötig oft gerechnet wird, werden Prognosen **zwischengespeichert**
(`PRED_TTL_HOURS`, Standard 20 Std.) – also höchstens ~1× pro Tag je Spiel.
`USE_WEB_SEARCH=1` lässt die KI zusätzlich live im Internet recherchieren – bei
Gemini 2.5 sind dafür täglich 1.500 Suchanfragen frei (für uns also weiterhin
gratis), darüber hinaus kostenpflichtig.

---

## 9. Hinweise

- Die App zeigt **nur Männer-Profimannschaften** (so eingerichtet).
- Quoten/KI-Prognosen sind **Schätzungen**, keine Garantie – das steht auch in der App.
- Solange noch keine echten Daten geladen sind, zeigt die App klar gekennzeichnete
  **Beispieldaten**.
```

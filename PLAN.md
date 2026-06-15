# Spielplan – Architektur & Plan

## Ziel

Eine sehr einfache, optisch ansprechende Android-App für einen älteren Nutzer,
die für **Bundesliga, Champions League, WM und EM** (nur Männer-Profis) anzeigt:
- wann, wer gegen wen
- **auf welchem Sender** (wichtigster Punkt)
- Quoten
- KI-Prognose mit kurzer Begründung + Wahrscheinlichkeit

Immer aktuell, **ohne dass ein Laptop läuft**. FC Bayern, Deutschland und Bosnien
immer ganz oben. Alles per WhatsApp teilbar.

## Grundentscheidung: warum PWA + Cloud-Updater

| Anforderung | Lösung |
|---|---|
| „Ohne Laptop, immer aktuell" | Updater läuft in der **Cloud** (GitHub Actions), nicht lokal |
| „Fühlt sich an wie eine App" | **PWA**: installierbar, Vollbild, eigenes Icon, offline |
| „Einfach + günstig + eine Person" | Kein Play-Store-Aufwand, Gratis-Hosting (GitHub Pages) |
| „Auf jedem Android" | Web-Technik läuft überall, kein App-Store-Review |

Eine native Kotlin-App wäre deutlich aufwändiger (Android Studio, Build, Signierung,
Updates) – ohne echten Mehrwert für diesen Anwendungsfall.

## Datenfluss

```
                 ┌──────────────────── Cloud (kostenlos) ────────────────────┐
                 │                                                            │
  football-data ─┤                                                            │
  the-odds-api  ─┤──►  updater/update.py  ──►  app/data.json  ──► GitHub Pages │
  Claude (KI)   ─┤      (alle paar Std.)        (eine Datei)         (Hosting) │
                 │                                                            │
                 └────────────────────────────────────────────────────────────┘
                                                                  │
                                                          Handy (PWA)
                                                   liest data.json, zeigt an,
                                                   teilt, erinnert, offline
```

Der Updater ist **dependency-frei** (nur Python-Standardbibliothek), damit er
überall läuft. Die App ist reines HTML/CSS/JS, kein Framework.

## Komponenten

- **app/** – Frontend (Anzeige). Tagesansicht, Favoriten oben, Sender groß,
  Quoten, KI-Prognose, Teilen, Erinnern, Live, Offline.
- **updater/update.py** – holt Spiele, ordnet Quoten zu, bestimmt TV-Sender
  (Regeln + Übersteuerung), erzeugt KI-Prognosen, schreibt `data.json`.
- **updater/overrides/broadcasters.json** – die TV-Sender-Logik (pflegbar).
- **.github/workflows/update.yml** – Zeitplan für den automatischen Lauf.

## TV-Sender: vollautomatisch (Recherche-Ergebnis)

Eine mehrstufige Recherche (4 parallele Rechercheure + Quellenprüfung) hat ergeben:
es gibt **keine saubere kostenlose offizielle API** für „Sender je Spiel".
- **SportMonks** (`include=tvStations`) wäre technisch sauber, kostet aber
  29–39 €/Monat (über Budget).
- **TheSportsDB** (`lookuptv.php`) läge bei ~8 €/Monat, ist aber crowdsourced und
  lückenhaft.
- Reine Fixture-APIs (OpenLigaDB gratis, football-data.org, API-Football) haben
  **kein** Sender-Feld.

Gewählte Lösung = **wartungsfreier Hybrid** (`updater/tv_sources.py`):
1. **Live-Quelle [fussballgucken.info](https://fussballgucken.info)** – offene
   `robots.txt`, server-gerendertes HTML, Sender je Spiel über alle vier
   Wettbewerbe; Zuordnung zu Fixtures über Datum + Anstoßzeit. Verifiziert: Parser
   läuft live korrekt.
2. **Regel-Engine** aus den mehrjährig fixen Rechten (Bundesliga Sky/DAZN bis
   2028/29; CL DAZN/Amazon bis 2026/27, danach Paramount+/Amazon – Stichtag
   eingebaut; WM 2026 ARD/ZDF/MagentaTV; EM 2028 ARD/ZDF) als Fallback.

→ **Keine manuelle Saison-Pflege nötig.** Rechtlich: nur Fakten, offene robots.txt,
niedrige Frequenz, Caching, kein Re-Publishing (private Einzel-App). Manuelle
Einzel-Übersteuerung in `broadcasters.json` bleibt optional möglich.

## Ehrliche offene Punkte

1. **Live-Quelle ist HTML** (kein offizielles API). Wenn fussballgucken.info sein
   Seitenlayout grundlegend ändert, kann der Parser brechen – dann zeigt die App
   automatisch den **Regel-Sender** weiter (kein Ausfall, nur etwas grober).
   Der Parser ist bewusst einfach gehalten und leicht anzupassen.
2. **Quoten in Deutschland**: rechtlich für private Nutzung unkritisch; bei
   öffentlicher Veröffentlichung (Play Store) Werberegeln beachten. → Hier
   Privatinstallation, daher unkritisch.
3. **Push-Erinnerungen**: echte Hintergrund-Pushes brauchen einen kleinen
   Push-Server. Aktuell zuverlässig über **Kalender-Eintrag** gelöst (das Handy
   erinnert selbst) + Benachrichtigung, solange die App offen ist. Echtes Push
   kann später ergänzt werden.
4. **National-Team-Spiele (Bosnien)**: Abdeckung hängt vom Daten-Anbieter und
   Wettbewerb ab (Quali/Turnier). Über die Wettbewerbe WM/EM abgedeckt; reine
   Freundschaftsspiele ggf. nicht. → bei Bedarf zweite Quelle ergänzen.

## Mögliche nächste Ausbaustufen

- Live-Tabellen der Bundesliga / Gruppen-Tabellen bei Turnieren
- Startbildschirm-Widget „Nächstes Bayern-Spiel"
- Echte Push-Benachrichtigungen über einen kleinen Push-Dienst
- Mehr Wettbewerbe (DFB-Pokal, Europa League) per Konfiguration
- Anpinnen weiterer Lieblingsteams direkt in der App
```

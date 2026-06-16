#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TV-Sender-Bestimmung (automatisch, ohne Saison-Handarbeit)
==========================================================

Zwei Stufen, die zusammen den Sender je Spiel liefern:

  1) REGEL-ENGINE  -> deckt ~90% deterministisch ab, aus den (mehrjährig fixen)
     deutschen Übertragungsrechten. Läuft immer, ohne Internet, ohne Pflege.
     Den bekannten Champions-League-Rechtewechsel ab Saison 2027/28
     (DAZN/Amazon -> Paramount/Amazon) ist als Stichtag schon eingebaut.

  2) SCRAPER fussballgucken.info -> verfeinert/bestätigt den exakten Sender je
     Einzelspiel (z.B. Bundesliga-Topspiel-Auswahl, Free-/Pay-Detail).
     Die Seite hat eine vollständig offene robots.txt (User-agent: * / Allow: /)
     und sauber strukturiertes HTML. Nur Fakten (Sender je Spiel), niedrige
     Frequenz, mit Caching – respektvoll genutzt.

Wenn der Scraper nichts findet oder ausfällt, bleibt die Regel-Engine als
verlässliche Grundlage. Es bleibt dadurch nichts manuell zu pflegen.

Rechte-Stand (Quellen siehe PLAN.md / Recherche):
  Bundesliga 2025/26–2028/29: Sky/WOW + DAZN (Slot-abhängig); Free-TV: Sat.1 (Auswahl)
  Champions League 2024/25–2026/27: DAZN (alle Di/Mi) + Amazon Prime (1 Topspiel Di)
                   ab 2027/28: Paramount+ + Amazon Prime
  WM 2026: MagentaTV (alle 104) + ARD/ZDF (60 im Free-TV, alle DE-Spiele)
  EM 2028: ARD/ZDF (alle 51, Free-TV)
"""

import re
import html as htmllib
import time
import urllib.request
from datetime import datetime

UA = {"User-Agent": "Mozilla/5.0 (SpielplanApp; privater Gebrauch) Python-urllib"}

# ----------------------------------------------------------------------------
# 1) REGEL-ENGINE
# ----------------------------------------------------------------------------

def tv_by_rules(competition, kickoff_iso, kickoff_known, date_local):
    """Liefert {known, channels, free, note} aus den Übertragungsrechten."""
    if competition == "WM":
        return {"known": True, "channels": ["ARD/ZDF", "MagentaTV"], "free": True,
                "note": "Free-TV bei ARD/ZDF oder exklusiv bei MagentaTV"}
    if competition == "EM":
        return {"known": True, "channels": ["ARD/ZDF"], "free": True, "note": None}
    if competition == "DFB-Pokal":
        return {"known": True, "channels": ["Sky"], "free": False,
                "note": "ausgewählte Spiele frei im ZDF/ARD/Sat.1"}
    if competition == "Champions League":
        # Rechtewechsel ab Saison 2027/28 (Stichtag ~ 1. Juli 2027)
        if date_local and date_local >= "2027-07-01":
            return {"known": True, "channels": ["Paramount+", "Amazon Prime Video"], "free": False,
                    "note": "ab Saison 2027/28"}
        return {"known": True, "channels": ["DAZN"], "free": False,
                "note": "Dienstags-Topspiel bei Amazon Prime Video"}
    if competition == "Bundesliga":
        if not (kickoff_iso and kickoff_known):
            return {"known": False, "channels": [], "free": False,
                    "note": "Sendetermin steht noch nicht fest (i.d.R. Sky/DAZN)"}
        try:
            dt = datetime.fromisoformat(kickoff_iso)
        except Exception:
            return {"known": True, "channels": ["Sky"], "free": False, "note": "Sky oder DAZN"}
        wd, hour = dt.weekday(), dt.hour  # Mo=0 .. So=6
        if wd == 4:  # Freitag 20:30
            return {"known": True, "channels": ["Sky"], "free": False, "note": None}
        if wd == 5 and hour < 17:  # Samstag 15:30
            return {"known": True, "channels": ["Sky"], "free": False, "note": "Konferenz auf DAZN"}
        if wd == 5:  # Samstag 18:30 Topspiel
            return {"known": True, "channels": ["Sky"], "free": False, "note": None}
        if wd == 6:  # Sonntag
            return {"known": True, "channels": ["DAZN"], "free": False, "note": None}
        # Englische Woche (Di/Mi/Do)
        return {"known": True, "channels": ["Sky"], "free": False, "note": "Konferenz auf DAZN"}
    return {"known": False, "channels": [], "free": False, "note": None}


# ----------------------------------------------------------------------------
# 2) SCRAPER fussballgucken.info
# ----------------------------------------------------------------------------

# /sender/<slug>  ->  (Anzeigename, frei_empfangbar)   – nur deutsche Sender
def map_channel(slug, name):
    s = slug.lower()
    if "das-erste" in s or s == "ard":           return ("ARD", True)
    if "zdf" in s:                                return ("ZDF", True)
    if "magenta" in s or "fussball-tv" in s:      return ("MagentaTV", False)
    if "dazn" in s:                               return ("DAZN", False)
    if "wow" in s:                                return ("WOW", False)
    if "sky" in s:                                return ("Sky", False)
    if "amazon" in s or "prime" in s:             return ("Amazon Prime Video", False)
    if "rtlplus" in s or "rtl-plus" in s:         return ("RTL+", False)
    if s == "rtl" or s.startswith("rtl-") or "rtl-television" in s: return ("RTL", True)
    if "nitro" in s:                              return ("Nitro", True)
    if "sat-1" in s or "sat1" in s:               return ("Sat.1", True)
    if "sport1" in s or "sport-1" in s:           return ("Sport1", True)
    return (None, False)  # internationaler/irrelevanter Sender -> verwerfen


def scrape_day(date_str, timeout=30):
    """Holt fussballgucken.info für einen Tag und parst alle Spiele.
    Rückgabe: Liste von {time:'HH:MM', comp_slug, home_slug, away_slug, channels:[...], free:bool}."""
    url = "https://fussballgucken.info/fussball-heute?date=" + date_str
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")

    # In Blöcke je Spiel schneiden: jeder Block beginnt bei einer meta-time
    parts = re.split(r'<div class="meta-time">(\d{1,2}:\d{2})</div>', raw)
    # parts = [vortext, time1, block1, time2, block2, ...]
    matches = []
    for k in range(1, len(parts) - 1, 2):
        tm = parts[k]
        block = parts[k + 1]
        murl = re.search(r'data-url="/match/\d+/([a-z0-9-]+)/([^"]+)"', block)
        if not murl:
            continue
        comp_slug = murl.group(1)
        teams = re.findall(r'href="/team/([a-z0-9-]+)"', block)
        home_slug = teams[0] if len(teams) >= 1 else ""
        away_slug = teams[1] if len(teams) >= 2 else ""
        # Sender einsammeln
        channels = []
        free = False
        for m in re.finditer(r'href="/sender/([a-z0-9-]+)"[^>]*>([^<]+)</a>', block):
            disp, is_free = map_channel(m.group(1), htmllib.unescape(m.group(2)).strip())
            if disp and disp not in channels:
                channels.append(disp)
                if is_free:
                    free = True
        if channels:
            matches.append({
                "time": ("0" + tm) if len(tm) == 4 else tm,
                "comp_slug": comp_slug, "home_slug": home_slug, "away_slug": away_slug,
                "channels": channels[:3], "free": free,
            })
    return matches


def build_scrape_index(dates, polite_delay=1.0, log=print):
    """Baut einen Index (date, 'HH:MM') -> Liste von Scrape-Treffern für mehrere Tage."""
    index = {}
    ok_days = 0
    for d in dates:
        try:
            day = scrape_day(d)
        except Exception as e:
            log(f"[WARN] TV-Scrape {d}: {e}")
            continue
        if day:
            ok_days += 1
        for row in day:
            index.setdefault((d, row["time"]), []).append(row)
        time.sleep(polite_delay)  # höflich bleiben
    log(f"[INFO] TV-Scrape: {ok_days}/{len(dates)} Tage, {sum(len(v) for v in index.values())} Einträge.")
    return index


def _norm_team(s):
    s = (s or "").lower()
    repl = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "é": "e", "è": "e", "á": "a", "ô": "o", "ç": "c"}
    for a, b in repl.items():
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def lookup_scrape(index, date_local, kickoff_iso, home_name, away_name):
    """Findet den Scrape-Treffer für ein Spiel über Datum+Uhrzeit (+ Team-Fuzzy bei Gleichstand)."""
    if not (kickoff_iso and date_local):
        return None
    try:
        hhmm = datetime.fromisoformat(kickoff_iso).strftime("%H:%M")
    except Exception:
        return None
    cands = index.get((date_local, hhmm))
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    # Mehrere Spiele zur selben Zeit -> über Team-Slugs disambiguieren
    hn, an = _norm_team(home_name), _norm_team(away_name)
    best, best_score = None, 0
    for c in cands:
        ch, ca = _norm_team(c["home_slug"]), _norm_team(c["away_slug"])
        score = 0
        for a, b in ((hn, ch), (an, ca)):
            if a and b and (a in b or b in a or a[:5] == b[:5]):
                score += 1
        if score > best_score:
            best, best_score = c, score
    return best if best_score > 0 else None


# Mini-Selbsttest:  python tv_sources.py 2026-06-26
if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    print(f"Scrape {d} ...")
    for r in scrape_day(d):
        print(f"  {r['time']}  {r['comp_slug']:12} {r['home_slug']} – {r['away_slug']}"
              f"  -> {', '.join(r['channels'])}{'  [frei]' if r['free'] else ''}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spielplan – Daten-Updater
=========================

Holt Spielpläne, Quoten und TV-Sender, lässt eine KI eine Prognose erstellen
und schreibt alles in docs/data.json. Diese Datei liest die App.

Bewusst OHNE Zusatzpakete (nur Python-Standardbibliothek), damit es überall
läuft – auf deinem Laptop genauso wie kostenlos in der Cloud (GitHub Actions).

Steuerung über Umgebungsvariablen (oder updater/config.json):
  FOOTBALL_DATA_API_KEY   Spielpläne von football-data.org   (Gratis-Konto)
  ODDS_API_KEY            Quoten von the-odds-api.com         (Gratis-Konto)
  ANTHROPIC_API_KEY       KI-Prognose über Claude             (kostet pro Anfrage)
  PREDICTION_MODEL        Claude-Modell (Standard: günstig)
  USE_WEB_SEARCH          "1" = KI recherchiert live im Internet (etwas teurer)
  DAYS_AHEAD              Wie viele Tage in die Zukunft (Standard 21)
  OUTPUT                  Zielpfad (Standard: ../docs/data.json)

Wenn ein Schlüssel fehlt, überspringt der Updater den jeweiligen Teil und
behält die vorhandene data.json, statt sie kaputtzuschreiben.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

import tv_sources  # Regel-Engine + fussballgucken-Scraper für TV-Sender
from teams_de import de_name  # englische -> deutsche Mannschaftsnamen

HERE = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------------

def load_config():
    cfg = {}
    cfg_path = os.path.join(HERE, "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            print(f"[WARN] config.json konnte nicht gelesen werden: {e}")

    def get(key, default=None):
        return os.environ.get(key) or cfg.get(key) or default

    # KI-Anbieter automatisch erkennen: Google (Gemini) hat Vorrang, falls ein
    # Google-Key gesetzt ist; sonst Anthropic (Claude).
    gemini_key = get("GOOGLE_API_KEY") or get("GEMINI_API_KEY")
    anthropic_key = get("ANTHROPIC_API_KEY")
    provider = "gemini" if gemini_key else ("claude" if anthropic_key else None)
    default_model = "gemini-2.5-flash-lite" if provider == "gemini" else "claude-haiku-4-5-20251001"

    return {
        "football_key": get("FOOTBALL_DATA_API_KEY"),
        "odds_key": get("ODDS_API_KEY"),
        "anthropic_key": anthropic_key,
        "gemini_key": gemini_key,
        "provider": provider,
        "model": get("PREDICTION_MODEL", default_model),
        "use_web_search": str(get("USE_WEB_SEARCH", "0")) == "1",
        "pred_ttl_hours": int(get("PRED_TTL_HOURS", "20")),
        "days_ahead": int(get("DAYS_AHEAD", "21")),
        "use_tv_scrape": str(get("USE_TV_SCRAPE", "1")) == "1",
        "tv_scrape_days": int(get("TV_SCRAPE_DAYS", "10")),
        "output": get("OUTPUT", os.path.join(HERE, "..", "docs", "data.json")),
        "tz_offset": "+02:00",  # Europe/Berlin Sommerzeit (wird unten genauer behandelt)
    }


# Wettbewerbe: App-Name -> football-data.org Code  +  the-odds-api Sport-Key
COMPETITIONS = [
    {"name": "WM",                "fd_code": "WC",  "odds_key": "soccer_fifa_world_cup"},
    {"name": "EM",                "fd_code": "EC",  "odds_key": "soccer_uefa_european_championship"},
    {"name": "Champions League",  "fd_code": "CL",  "odds_key": "soccer_uefa_champs_league"},
    {"name": "Bundesliga",        "fd_code": "BL1", "odds_key": "soccer_germany_bundesliga"},
]


# ----------------------------------------------------------------------------
# HTTP-Hilfen (nur Standardbibliothek)
# ----------------------------------------------------------------------------

def http_get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_json(url, payload, headers=None, timeout=90):
    data = json.dumps(payload).encode("utf-8")
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_json_retry(url, payload, headers=None, tries=3, base_sleep=3):
    """Wie http_post_json, aber wiederholt bei vorübergehenden Fehlern (429/503)."""
    for i in range(tries):
        try:
            return http_post_json(url, payload, headers=headers)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < tries - 1:
                time.sleep(base_sleep * (i + 1))
                continue
            raise


# ----------------------------------------------------------------------------
# Datum / Zeit
# ----------------------------------------------------------------------------

def berlin_offset(dt_utc):
    """Grobe Sommer-/Winterzeit-Bestimmung für Europe/Berlin (ohne Zusatzpakete).
    Sommerzeit: letzter Sonntag März bis letzter Sonntag Oktober -> +02:00, sonst +01:00."""
    y = dt_utc.year
    def last_sunday(month):
        d = datetime(y, month, 31, tzinfo=timezone.utc)
        while d.month != month:
            d -= timedelta(days=1)
        while d.weekday() != 6:
            d -= timedelta(days=1)
        return d
    start = last_sunday(3).replace(hour=1)
    end = last_sunday(10).replace(hour=1)
    return timezone(timedelta(hours=2)) if start <= dt_utc < end else timezone(timedelta(hours=1))


def to_local(utc_iso):
    """UTC-ISO -> (dateLocal 'YYYY-MM-DD', kickoff_iso_local, kickoff_known)."""
    if not utc_iso:
        return None, None, False
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None, None, False
    off = berlin_offset(dt)
    local = dt.astimezone(off)
    # Mitternacht-UTC ist bei football-data oft ein Platzhalter für "Zeit noch offen"
    known = not (dt.hour == 0 and dt.minute == 0)
    return local.strftime("%Y-%m-%d"), local.isoformat(), known


# ----------------------------------------------------------------------------
# Spielpläne (football-data.org)
# ----------------------------------------------------------------------------

STATUS_MAP = {
    "SCHEDULED": "scheduled", "TIMED": "scheduled",
    "IN_PLAY": "live", "PAUSED": "live", "SUSPENDED": "live",
    "FINISHED": "finished", "AWARDED": "finished",
    "POSTPONED": "scheduled", "CANCELLED": "scheduled",
}


def fetch_fixtures(cfg):
    """Holt Spiele aller konfigurierten Wettbewerbe im Zeitfenster."""
    if not cfg["football_key"]:
        print("[INFO] Kein FOOTBALL_DATA_API_KEY – Spielpläne werden übersprungen.")
        return None

    date_from = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_to = (datetime.now(timezone.utc) + timedelta(days=cfg["days_ahead"])).strftime("%Y-%m-%d")
    headers = {"X-Auth-Token": cfg["football_key"]}
    matches = []

    for comp in COMPETITIONS:
        url = (f"https://api.football-data.org/v4/competitions/{comp['fd_code']}/matches"
               f"?dateFrom={date_from}&dateTo={date_to}")
        try:
            data = http_get_json(url, headers=headers)
        except urllib.error.HTTPError as e:
            # 403 = nicht im Gratis-Tarif, 429 = zu viele Anfragen
            print(f"[WARN] {comp['name']} ({comp['fd_code']}): HTTP {e.code} – übersprungen.")
            time.sleep(6 if e.code == 429 else 0)
            continue
        except Exception as e:
            print(f"[WARN] {comp['name']}: {e}")
            continue

        for fx in data.get("matches", []):
            date_local, kickoff, known = to_local(fx.get("utcDate"))
            if not date_local:
                continue
            ft = (fx.get("score") or {}).get("fullTime") or {}
            home = fx.get("homeTeam") or {}
            away = fx.get("awayTeam") or {}
            stage = build_stage(fx)
            matches.append({
                "id": f"fd-{fx.get('id')}",
                "competition": comp["name"],
                "competitionStage": stage,
                "dateLocal": date_local,
                "kickoff": kickoff,
                "kickoffKnown": known,
                "status": STATUS_MAP.get(fx.get("status"), "scheduled"),
                "minute": fx.get("minute"),
                "home": team_obj(home, ft.get("home")),
                "away": team_obj(away, ft.get("away")),
                "tv": {"known": False, "channels": [], "free": False, "note": None},
                "odds": {"known": False},
                "prediction": {"available": False},
                "_oddsKey": comp["odds_key"],
            })
        time.sleep(6)  # Gratis-Tarif: max 10 Anfragen/Minute – höflich warten

    print(f"[INFO] {len(matches)} Spiele geladen.")
    return matches


def team_obj(t, score):
    name = de_name(t.get("name") or t.get("shortName") or "?")
    return {
        "name": name,
        "short": t.get("tla") or t.get("shortName") or name[:3].upper(),
        "crest": t.get("crest"),
        "score": score,
    }


def build_stage(fx):
    parts = []
    stage = (fx.get("stage") or "").replace("_", " ").title()
    if stage and stage.lower() not in ("regular Season".lower(),):
        # Übersetzungen für gängige Turnierphasen
        trans = {
            "Group Stage": "Gruppenphase", "Last 16": "Achtelfinale",
            "Quarter Finals": "Viertelfinale", "Semi Finals": "Halbfinale",
            "Final": "Finale", "League Stage": "Ligaphase",
        }
        stage = trans.get(stage, stage)
        parts.append(stage)
    if fx.get("group"):
        parts.append(str(fx["group"]).replace("GROUP", "Gruppe").title())
    if fx.get("matchday") and (fx.get("stage") in (None, "REGULAR_SEASON", "LEAGUE_STAGE")):
        parts.append(f"{fx['matchday']}. Spieltag")
    return " · ".join(parts) if parts else None


# ----------------------------------------------------------------------------
# Quoten (the-odds-api.com)
# ----------------------------------------------------------------------------

def attach_odds(cfg, matches):
    if not cfg["odds_key"]:
        print("[INFO] Kein ODDS_API_KEY – Quoten werden übersprungen.")
        return
    # je Wettbewerb einmal abfragen
    keys = sorted({m["_oddsKey"] for m in matches if m.get("_oddsKey")})
    odds_index = {}
    for sport in keys:
        url = (f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
               f"?apiKey={cfg['odds_key']}&regions=eu&markets=h2h&oddsFormat=decimal")
        try:
            events = http_get_json(url)
        except Exception as e:
            print(f"[WARN] Quoten {sport}: {e}")
            continue
        for ev in events:
            odds_index[norm(ev.get("home_team")) + "|" + norm(ev.get("away_team"))] = ev

    for m in matches:
        key = norm(m["home"]["name"]) + "|" + norm(m["away"]["name"])
        ev = odds_index.get(key) or fuzzy_odds(odds_index, m)
        if not ev:
            continue
        h, d, a = extract_h2h(ev)
        if h:
            m["odds"] = {"known": True, "home": h, "draw": d, "away": a, "source": "the-odds-api"}


def extract_h2h(ev):
    """Durchschnitts-/erste verfügbare 1-X-2-Quote aus den Buchmachern."""
    home = ev.get("home_team"); away = ev.get("away_team")
    for bm in ev.get("bookmakers", []):
        for mk in bm.get("markets", []):
            if mk.get("key") != "h2h":
                continue
            o = {x.get("name"): x.get("price") for x in mk.get("outcomes", [])}
            return o.get(home), o.get("Draw"), o.get(away)
    return None, None, None


def fuzzy_odds(index, m):
    hn = norm(m["home"]["name"]); an = norm(m["away"]["name"])
    for key, ev in index.items():
        kh, ka = key.split("|")
        if (hn in kh or kh in hn) and (an in ka or ka in an):
            return ev
    return None


def norm(s):
    if not s:
        return ""
    return (s.lower().replace("fc ", "").replace(" fc", "")
            .replace("und herzegowina", "").replace("&", "").strip())


# ----------------------------------------------------------------------------
# TV-Sender (Regeln + manuelle Übersteuerung)
# ----------------------------------------------------------------------------

def load_overrides():
    path = os.path.join(HERE, "overrides", "broadcasters.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"defaults": {}, "byMatch": {}}


def determine_tv(cfg, matches, ov):
    """Setzt TV-Sender vollautomatisch, in dieser Reihenfolge:
      1) manuelle Übersteuerung (overrides/broadcasters.json -> byMatch), falls vorhanden
      2) Live-Quelle: fussballgucken.info (exakter Sender je Spiel, per Datum+Uhrzeit zugeordnet)
      3) Regel-Engine aus den Übertragungsrechten (deckt den Rest deterministisch ab)
    So bleibt nichts manuell zu pflegen; fällt die Live-Quelle aus, greifen die Regeln."""
    by_match = ov.get("byMatch", {})

    # Live-Quelle einmalig für das relevante Zeitfenster abrufen
    scrape_index = {}
    if cfg.get("use_tv_scrape"):
        today = datetime.now(timezone.utc)
        dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(cfg.get("tv_scrape_days", 10))]
        try:
            scrape_index = tv_sources.build_scrape_index(dates)
        except Exception as e:
            print(f"[WARN] TV-Live-Quelle nicht erreichbar: {e}")

    n_override = n_scrape = n_rules = n_unknown = 0
    for m in matches:
        # 1) manuelle Übersteuerung
        key_names = f"{m['home']['name']} vs {m['away']['name']}"
        rule = by_match.get(m["id"]) or by_match.get(key_names)
        if rule and not str(m["id"]).startswith("_"):
            m["tv"] = {"known": True, "channels": rule.get("channels", []),
                       "free": rule.get("free", False), "note": rule.get("note")}
            n_override += 1
            continue

        # 2) Live-Quelle (Datum + Uhrzeit)
        hit = tv_sources.lookup_scrape(scrape_index, m["dateLocal"], m.get("kickoff"),
                                       m["home"]["name"], m["away"]["name"])
        if hit and hit.get("channels"):
            m["tv"] = {"known": True, "channels": hit["channels"], "free": hit["free"], "note": None}
            n_scrape += 1
            continue

        # 3) Regel-Engine
        tv = tv_sources.tv_by_rules(m["competition"], m.get("kickoff"),
                                    m.get("kickoffKnown"), m["dateLocal"])
        m["tv"] = tv
        if tv["known"]:
            n_rules += 1
        else:
            n_unknown += 1

    print(f"[INFO] TV-Sender: {n_override} manuell, {n_scrape} aus Live-Quelle, "
          f"{n_rules} per Regel, {n_unknown} noch offen.")


# ----------------------------------------------------------------------------
# KI-Prognose (Claude / Anthropic API)
# ----------------------------------------------------------------------------

PRED_SYSTEM = (
    "Du bist ein nüchterner Fußball-Analyst. Schätze den Ausgang eines Spiels ein. "
    "Antworte AUSSCHLIESSLICH mit einem JSON-Objekt, ohne weiteren Text, in diesem Format:\n"
    '{"outcome":"Sieg <Team> | Unentschieden","scoreline":"2:1",'
    '"probs":{"home":0.5,"draw":0.3,"away":0.2},'
    '"reasons":["kurzer Stichpunkt 1","Stichpunkt 2","Stichpunkt 3"]}\n'
    "Die drei Wahrscheinlichkeiten müssen zusammen 1.0 ergeben. "
    "Die Stichpunkte sind knapp, auf Deutsch und nennen den fachlichen Grund."
)


def generate_predictions(cfg, matches):
    if not cfg["provider"]:
        print("[INFO] Kein KI-Schlüssel (GOOGLE_API_KEY oder ANTHROPIC_API_KEY) – Prognosen übersprungen.")
        return

    # Vorhandene Prognosen aus der letzten data.json wiederverwenden (Kostenersparnis):
    # nicht bei jedem Lauf (alle 3 Std.) neu rechnen, sondern höchstens alle PRED_TTL_HOURS.
    prev = load_prev_predictions(cfg)
    ttl = timedelta(hours=cfg["pred_ttl_hours"])
    now = datetime.now(timezone.utc)
    horizon = (now + timedelta(days=8)).strftime("%Y-%m-%d")

    count = reused = 0
    for m in matches:
        if m["status"] == "finished":
            continue
        if m["dateLocal"] > horizon:  # Kostenkontrolle: nur Spiele der nächsten 8 Tage
            continue
        cached = prev.get(m["id"])
        if cached and _fresh(cached.get("generatedAt"), now, ttl):
            m["prediction"] = cached
            reused += 1
            continue
        pred = predict_match(cfg, m)
        if pred:
            m["prediction"] = pred
            count += 1
            time.sleep(1)
    print(f"[INFO] KI-Prognosen ({cfg['provider']}/{cfg['model']}): {count} neu, {reused} aus Cache.")


def load_prev_predictions(cfg):
    path = os.path.abspath(cfg["output"])
    out = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for m in data.get("matches", []):
                p = m.get("prediction")
                if p and p.get("available"):
                    out[m["id"]] = p
        except Exception:
            pass
    return out


def _fresh(iso, now, ttl):
    if not iso:
        return False
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (now - dt) < ttl
    except Exception:
        return False


def build_pred_prompt(m):
    odds_txt = ""
    if m["odds"].get("known"):
        odds_txt = f" Buchmacher-Quoten 1/X/2: {m['odds']['home']}/{m['odds'].get('draw')}/{m['odds']['away']}."
    return (
        f"{m['competition']}{(' – ' + m['competitionStage']) if m.get('competitionStage') else ''}, "
        f"am {m['dateLocal']}: {m['home']['name']} (Heim) gegen {m['away']['name']} (Auswärts)."
        f"{odds_txt} Berücksichtige Form, Verletzungen, Tabellensituation und Heimvorteil. "
        f"Gib deine Einschätzung als JSON zurück."
    )


def finalize_prediction(data, model):
    if not data:
        return None
    probs = data.get("probs", {})
    try:
        ph, pd, pa = float(probs.get("home", 0)), float(probs.get("draw", 0)), float(probs.get("away", 0))
    except Exception:
        ph = pd = pa = 0.0
    s = ph + pd + pa
    if s > 0:
        ph, pd, pa = ph / s, pd / s, pa / s
    return {
        "available": True,
        "outcome": data.get("outcome", ""),
        "scoreline": data.get("scoreline", ""),
        "confidence": round(max(ph, pd, pa), 2),
        "probs": {"home": round(ph, 2), "draw": round(pd, 2), "away": round(pa, 2)},
        "reasons": data.get("reasons", [])[:4],
        "model": model,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def predict_match(cfg, m):
    try:
        if cfg["provider"] == "gemini":
            return predict_gemini(cfg, m)
        return predict_claude(cfg, m)
    except Exception as e:
        print(f"[WARN] Prognose {m['id']}: {e}")
        return None


def predict_claude(cfg, m):
    payload = {
        "model": cfg["model"], "max_tokens": 700, "system": PRED_SYSTEM,
        "messages": [{"role": "user", "content": build_pred_prompt(m)}],
    }
    if cfg["use_web_search"]:
        payload["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
    headers = {"x-api-key": cfg["anthropic_key"], "anthropic-version": "2023-06-01"}
    try:
        resp = http_post_json_retry("https://api.anthropic.com/v1/messages", payload, headers=headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        if cfg["use_web_search"] and ("tool" in body.lower() or e.code == 400):
            payload.pop("tools", None)
            resp = http_post_json_retry("https://api.anthropic.com/v1/messages", payload, headers=headers)
        else:
            print(f"[WARN] Prognose {m['id']}: HTTP {e.code} {body[:160]}")
            return None
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    return finalize_prediction(parse_json_loose(text), cfg["model"])


def predict_gemini(cfg, m):
    base = (f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{cfg['model']}:generateContent?key={cfg['gemini_key']}")
    payload = {
        "system_instruction": {"parts": [{"text": PRED_SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": build_pred_prompt(m)}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 700},
    }
    if cfg["use_web_search"]:
        # Grounding mit Google Suche (aktuelle Form/Verletzungen). Achtung: Gratis-Kontingent
        # beachten; mit Tools kein erzwungenes JSON-Format -> wir parsen den Text robust.
        payload["tools"] = [{"google_search": {}}]
    else:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    try:
        resp = http_post_json_retry(base, payload, headers={})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        if cfg["use_web_search"]:  # ohne Tools erneut versuchen
            payload.pop("tools", None)
            payload["generationConfig"]["responseMimeType"] = "application/json"
            resp = http_post_json_retry(base, payload, headers={})
        else:
            print(f"[WARN] Prognose {m['id']}: HTTP {e.code} {body[:160]}")
            return None
    text = ""
    for cand in resp.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            text += part.get("text", "")
    return finalize_prediction(parse_json_loose(text), cfg["model"])


def parse_json_loose(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    # JSON aus dem Text herausschneiden
    i, j = text.find("{"), text.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(text[i:j + 1])
        except Exception:
            return None
    return None


# ----------------------------------------------------------------------------
# Zusammenbauen & Schreiben
# ----------------------------------------------------------------------------

def write_output(cfg, matches):
    for m in matches:
        m.pop("_oddsKey", None)
    matches.sort(key=lambda m: (m["dateLocal"], m.get("kickoff") or "z"))
    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "timezone": "Europe/Berlin",
        "isSample": False,
        "favoriteTeams": ["FC Bayern München", "Deutschland", "Bosnien"],
        "matches": matches,
    }
    out_path = os.path.abspath(cfg["output"])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[OK] {len(matches)} Spiele geschrieben -> {out_path}")


def main():
    cfg = load_config()
    print("[START] Spielplan-Updater")

    matches = fetch_fixtures(cfg)
    if matches is None:
        print("[STOP] Ohne Spielplan-Daten wird die vorhandene data.json nicht überschrieben.")
        sys.exit(0)
    if not matches:
        print("[STOP] Keine Spiele im Zeitfenster gefunden – data.json bleibt unverändert.")
        sys.exit(0)

    attach_odds(cfg, matches)
    determine_tv(cfg, matches, load_overrides())
    generate_predictions(cfg, matches)
    write_output(cfg, matches)


if __name__ == "__main__":
    main()

/* =========================================================
   Spielplan – App-Logik (reines JavaScript, kein Framework)

   Zeigt Fußballspiele tageweise an:
   - Heute zuerst, mit Pfeilen/Wischen durch die Tage
   - Lieblings-Mannschaften immer ganz oben
   - TV-Sender groß hervorgehoben (wichtigster Punkt)
   - Quoten + KI-Prognose
   - Teilen für WhatsApp, Erinnerung (Kalender), Live-Ergebnis, Offline
   ========================================================= */

"use strict";

/* ----------------- Konfiguration ----------------- */

// Reihenfolge der Wettbewerbe (Abschnitte) an einem Tag
const COMP_ORDER = ["WM", "EM", "Champions League", "Bundesliga", "DFB-Pokal"];
const COMP_ICON = {
  "WM": "🌍", "EM": "🇪🇺", "Champions League": "🏆", "Bundesliga": "🇩🇪", "DFB-Pokal": "🥇",
};
// Wettbewerbe, die im Teilen-Dialog IMMER angeboten werden (auch ohne aktuelle Spiele)
const SHARE_COMPS = ["Bundesliga", "Champions League", "DFB-Pokal", "WM", "EM"];

// Lieblings-Teams (Standard). Werden in den Einstellungen angezeigt.
// "aliases" fängt verschiedene Schreibweisen aus den Daten ab.
const FAVORITES = [
  { label: "FC Bayern München", emoji: "🔴", aliases: ["bayern münchen", "fc bayern", "bayern munich", "bayern"] },
  { label: "Deutschland", emoji: "🇩🇪", aliases: ["deutschland", "germany"] },
  { label: "Bosnien", emoji: "🇧🇦", aliases: ["bosnien", "bosnia", "bosna"] },
];

const WEEKDAYS = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];
const MONTHS = ["Jan.", "Feb.", "März", "April", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."];

/* ----------------- Zustand ----------------- */

const state = {
  data: null,
  byDate: new Map(),     // "YYYY-MM-DD" -> [matches]
  selectedDate: todayStr(),
  offline: false,
  autoJump: true,        // beim ersten Laden ggf. zum nächsten Spieltag springen
};

/* ----------------- Hilfsfunktionen Datum ----------------- */

function todayStr() {
  const d = new Date();
  return ymd(d);
}
function ymd(d) {
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
}
function pad(n) { return String(n).padStart(2, "0"); }

function addDays(dateStr, delta) {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + delta);
  return ymd(dt);
}
function formatWeekday(dateStr) {
  if (dateStr === todayStr()) return "Heute";
  if (dateStr === addDays(todayStr(), 1)) return "Morgen";
  if (dateStr === addDays(todayStr(), -1)) return "Gestern";
  const [y, m, d] = dateStr.split("-").map(Number);
  return WEEKDAYS[new Date(y, m - 1, d).getDay()];
}
function formatFull(dateStr) {
  const [y, m, d] = dateStr.split("-").map(Number);
  return `${d}. ${MONTHS[m - 1]} ${y}`;
}
function formatTime(iso) {
  const d = new Date(iso);
  return pad(d.getHours()) + ":" + pad(d.getMinutes()) + " Uhr";
}

/* ----------------- Daten laden ----------------- */

async function loadData() {
  try {
    const res = await fetch("./data.json?ts=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    state.data = await res.json();
    state.offline = false;
  } catch (e) {
    // Offline: Service Worker liefert ggf. die zuletzt gespeicherte Datei
    try {
      const res = await fetch("./data.json");
      state.data = await res.json();
    } catch (_) {
      state.data = state.data || { matches: [], generatedAt: null };
    }
    state.offline = true;
  }
  indexData();
  rearmReminders();
  // Beim ersten Laden: falls heute keine Spiele sind, zum nächsten Spieltag springen
  if (state.autoJump) {
    state.autoJump = false;
    jumpToNearestMatchday();
  }
  render();
  renderStatus();
  renderDataStamp();
}

// Springt auf den nächsten Tag (ab heute) mit Spielen, falls der aktuell gewählte
// Tag leer ist. So landet man immer auf echtem Inhalt statt einer leeren Seite.
function jumpToNearestMatchday() {
  if ((state.byDate.get(state.selectedDate) || []).length) return;
  const today = todayStr();
  const future = [...state.byDate.keys()].filter((d) => d >= today).sort();
  if (future.length) { state.selectedDate = future[0]; return; }
  // sonst: jüngster vergangener Tag mit Spielen
  const past = [...state.byDate.keys()].filter((d) => d < today).sort();
  if (past.length) state.selectedDate = past[past.length - 1];
}

function indexData() {
  state.byDate = new Map();
  const matches = (state.data && state.data.matches) || [];
  for (const m of matches) {
    m._fav = matchFavorite(m); // welcher Favorit (oder null)
    if (!state.byDate.has(m.dateLocal)) state.byDate.set(m.dateLocal, []);
    state.byDate.get(m.dateLocal).push(m);
  }
}

function matchFavorite(m) {
  const names = [(m.home && m.home.name) || "", (m.away && m.away.name) || ""].join(" ").toLowerCase();
  for (const f of FAVORITES) {
    if (f.aliases.some((a) => names.includes(a))) return f;
  }
  return null;
}

/* ----------------- Rendern: Kopf/Status ----------------- */

function renderHeader() {
  document.getElementById("dateWeekday").textContent = formatWeekday(state.selectedDate);
  document.getElementById("dateFull").textContent = formatFull(state.selectedDate);
  document.getElementById("todayBtn").classList.toggle("hidden", state.selectedDate === todayStr());
}

function renderStatus() {
  const bar = document.getElementById("statusBar");
  if (state.offline) {
    bar.textContent = "📴 Offline – zeige zuletzt geladene Daten" + stampSuffix();
    bar.className = "status-bar offline";
    bar.classList.remove("hidden");
  } else if (state.data && state.data.isSample) {
    bar.textContent = "ℹ️ Beispieldaten – echte Daten erscheinen, sobald der Updater mit API-Schlüsseln läuft.";
    bar.className = "status-bar";
    bar.classList.remove("hidden");
  } else {
    bar.classList.add("hidden");
  }
}
function stampSuffix() {
  if (!state.data || !state.data.generatedAt) return "";
  const d = new Date(state.data.generatedAt);
  return ` (Stand: ${pad(d.getDate())}.${pad(d.getMonth() + 1)}. ${pad(d.getHours())}:${pad(d.getMinutes())} Uhr)`;
}
function renderDataStamp() {
  const el = document.getElementById("dataStamp");
  if (!state.data || !state.data.generatedAt) { el.textContent = "Noch keine Daten geladen."; return; }
  const d = new Date(state.data.generatedAt);
  el.textContent = `Zuletzt aktualisiert: ${WEEKDAYS[d.getDay()]}, ${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} um ${pad(d.getHours())}:${pad(d.getMinutes())} Uhr`;
}

/* ----------------- Rendern: Tagesinhalt ----------------- */

function render() {
  renderHeader();
  const content = document.getElementById("content");
  content.innerHTML = "";

  const matches = (state.byDate.get(state.selectedDate) || []).slice();

  if (matches.length === 0) {
    content.innerHTML = `
      <div class="empty-day">
        <span class="emoji">📅</span>
        <strong>Keine Spiele an diesem Tag</strong>
        <p>Tippe auf die Pfeile oder wische, um andere Tage zu sehen.</p>
      </div>`;
    return;
  }

  // 1) Favoriten-Abschnitt (alle Spiele mit Lieblings-Team an diesem Tag)
  const favMatches = matches.filter((m) => m._fav);
  if (favMatches.length) {
    content.appendChild(renderSection("⭐ Meine Mannschaften", favMatches, "favorites", true));
  }

  // 2) Übrige Spiele nach Wettbewerb gruppiert
  const rest = matches.filter((m) => !m._fav);
  const byComp = groupBy(rest, "competition");
  const comps = Object.keys(byComp).sort(
    (a, b) => (COMP_ORDER.indexOf(a) + 1 || 99) - (COMP_ORDER.indexOf(b) + 1 || 99)
  );
  for (const comp of comps) {
    const icon = COMP_ICON[comp] || "⚽";
    content.appendChild(renderSection(`${icon} ${comp}`, sortMatches(byComp[comp]), "comp", false));
  }
}

function renderSection(title, matches, cls, isFav) {
  const sec = document.createElement("section");
  sec.className = "section " + (isFav ? "favorites" : "");
  const head = document.createElement("div");
  head.className = "section-header";
  head.innerHTML = `<span>${title}</span><span class="section-badge">${matches.length} ${matches.length === 1 ? "Spiel" : "Spiele"}</span>`;
  sec.appendChild(head);
  for (const m of sortMatches(matches)) sec.appendChild(renderMatch(m));
  return sec;
}

function sortMatches(arr) {
  return arr.slice().sort((a, b) => {
    // Live zuerst, dann nach Anstoßzeit, unbekannte Zeiten ans Ende
    const liveA = a.status === "live" ? 0 : 1;
    const liveB = b.status === "live" ? 0 : 1;
    if (liveA !== liveB) return liveA - liveB;
    const ta = a.kickoff ? new Date(a.kickoff).getTime() : Infinity;
    const tb = b.kickoff ? new Date(b.kickoff).getTime() : Infinity;
    return ta - tb;
  });
}

function groupBy(arr, key) {
  const out = {};
  for (const x of arr) { (out[x[key]] = out[x[key]] || []).push(x); }
  return out;
}

/* ----------------- Rendern: eine Spielkarte ----------------- */

function renderMatch(m) {
  const card = document.createElement("article");
  card.className = "match" + (m._fav ? " is-favorite" : "") + (m.status === "live" ? " is-live" : "");
  const p = (m.prediction && m.prediction.available) ? m.prediction : null;

  card.innerHTML =
    headHtml(m) + teamsHtml(m) + tvHtml(m) + footHtml(m, p) +
    (p ? predBodyHtml(m, p) : "");

  // Tippen auf die Fuß-Zeile klappt die KI-Prognose auf/zu
  const foot = card.querySelector(".m-foot.tappable");
  if (foot) foot.addEventListener("click", () => card.classList.toggle("open"));
  card.querySelector(".m-act-remind").addEventListener("click", (e) => { e.stopPropagation(); setReminder(m); });
  card.querySelector(".m-act-share").addEventListener("click", (e) => { e.stopPropagation(); shareText(matchToText(m), "Spiel teilen"); });
  return card;
}

function tn(t) { return (t && t.name) || "?"; }
function crestImg(t) {
  return (t && t.crest)
    ? `<img class="m-crest" src="${t.crest}" alt="" loading="lazy" onerror="this.style.display='none'">`
    : "";
}

function headHtml(m) {
  let status;
  if (m.status === "live") status = `<span class="live-pill"><span class="live-dot"></span>LIVE${m.minute ? " " + m.minute + "'" : ""}</span>`;
  else if (m.status === "finished") status = `<span class="m-time">Beendet</span>`;
  else if (m.kickoff && m.kickoffKnown) status = `<span class="m-time">${formatTime(m.kickoff)}</span>`;
  else status = `<span class="m-open">Zeit offen</span>`;
  const stage = m.competitionStage ? `<span class="m-stage"> · ${m.competitionStage}</span>` : "";
  return `<div class="m-head">
    <span class="m-comp">${COMP_ICON[m.competition] || "⚽"} ${m.competition}${stage}</span>
    <span class="m-head-right">${status}
      <button class="m-ic m-act-remind" type="button" aria-label="Erinnerung in den Kalender">⏰</button>
      <button class="m-ic m-act-share" type="button" aria-label="Dieses Spiel teilen">↗</button>
    </span>
  </div>`;
}

function teamsHtml(m) {
  const showScore = (m.status === "live" || m.status === "finished") &&
    m.home && m.away && m.home.score != null && m.away.score != null;
  const center = showScore ? `<span class="m-score">${m.home.score}:${m.away.score}</span>` : `<span class="m-dash">–</span>`;
  return `<div class="m-teams">
    <span class="m-team m-home">${crestImg(m.home)}<span class="m-tn">${tn(m.home)}</span></span>
    ${center}
    <span class="m-team m-away"><span class="m-tn">${tn(m.away)}</span>${crestImg(m.away)}</span>
  </div>`;
}

// Echte Free-TV-Sender (grün); alles andere = Pay (blau)
function isFreeChannel(name) {
  const n = (name || "").toLowerCase();
  if (n.includes("rtl+") || n.includes("rtl plus")) return false;
  return ["ard", "zdf", "das erste", "sat.1", "sat1", "nitro", "sport1", "rtl", "kika", "one"]
    .some((f) => n.includes(f));
}

function tvHtml(m) {
  const tv = m.tv || {};
  if (tv.known && tv.channels && tv.channels.length) {
    const chips = tv.channels.map((c) => `<span class="tv-chip ${isFreeChannel(c) ? "free" : ""}">${c}</span>`).join("");
    return `<div class="m-tv"><span class="m-tv-ic">📺</span><span class="tv-chips">${chips}</span>${tv.free ? `<span class="tv-free">frei</span>` : ""}</div>`;
  }
  return `<div class="m-tv unknown"><span class="m-tv-ic">📺</span><span class="m-open">Sender noch offen</span></div>`;
}

function footHtml(m, p) {
  const o = m.odds || {};
  const odds = o.known
    ? `<span class="m-odds">📊 ${fmt(o.home)} · ${fmt(o.draw)} · ${fmt(o.away)}</span>`
    : `<span class="m-odds muted">Quoten offen</span>`;
  const pred = p
    ? `<span class="m-pred"><span class="m-pred-tip">🤖 ${p.outcome}${p.scoreline ? " " + p.scoreline : ""}</span><span class="m-pred-conf">${Math.round((p.confidence || 0) * 100)}%</span><span class="m-chev">▾</span></span>`
    : "";
  return `<div class="m-foot${p ? " tappable" : ""}">${odds}${pred}</div>`;
}

function predBodyHtml(m, p) {
  const probs = p.probs || {};
  const bar = (label, val) => {
    const pct = Math.round((val || 0) * 100);
    return `<div class="pb-row"><span class="pb-lab">${label}</span><span class="pb-track"><span class="pb-fill" style="width:${pct}%"></span></span><span class="pb-val">${pct}%</span></div>`;
  };
  return `<div class="m-pred-body">
    <div class="pb-bars">${bar(tn(m.home), probs.home)}${bar("Remis", probs.draw)}${bar(tn(m.away), probs.away)}</div>
    <strong>Warum die KI das denkt:</strong>
    <ul class="pb-reasons">${(p.reasons || []).map((r) => `<li>${r}</li>`).join("")}</ul>
    <p class="pb-disc">⚠️ KI-Schätzung auf Basis von Internet-Recherche – keine Garantie.</p>
  </div>`;
}

/* ----------------- Texte für WhatsApp / Teilen ----------------- */

function matchToText(m) {
  const time = m.kickoffKnown && m.kickoff ? formatTime(m.kickoff) : "Uhrzeit noch offen";
  const home = m.home ? m.home.name : "?";
  const away = m.away ? m.away.name : "?";
  let t = `⚽ ${home} – ${away}\n${COMP_ICON[m.competition] || ""} ${m.competition}`;
  if (m.competitionStage) t += ` (${m.competitionStage})`;
  t += `\n📅 ${formatWeekday(m.dateLocal)}, ${formatFull(m.dateLocal)} · ${time}`;
  if (m.tv && m.tv.known && m.tv.channels && m.tv.channels.length) {
    t += `\n📺 ${m.tv.channels.join(", ")}${m.tv.free ? " (frei empfangbar)" : ""}`;
  } else {
    t += `\n📺 Sender noch offen`;
  }
  if ((m.status === "live" || m.status === "finished") && m.home && m.away && m.home.score != null) {
    t += `\n⚡ Stand: ${m.home.score}:${m.away.score}${m.status === "live" && m.minute ? " (" + m.minute + "')" : ""}`;
  }
  if (m.odds && m.odds.known) t += `\n💰 Quoten 1/X/2: ${fmt(m.odds.home)} / ${fmt(m.odds.draw)} / ${fmt(m.odds.away)}`;
  if (m.prediction && m.prediction.available) {
    t += `\n🤖 Tipp: ${m.prediction.outcome}${m.prediction.scoreline ? " " + m.prediction.scoreline : ""} (${Math.round((m.prediction.confidence || 0) * 100)}%)`;
  }
  return t;
}
function fmt(v) { return v != null ? v.toFixed(2) : "–"; }

function dayToText() {
  const matches = sortMatches((state.byDate.get(state.selectedDate) || []).slice());
  if (!matches.length) return `Keine Spiele am ${formatFull(state.selectedDate)}.`;
  const header = `📅 Spiele am ${formatWeekday(state.selectedDate)}, ${formatFull(state.selectedDate)}\n`;
  return header + "\n" + matches.map(matchToText).join("\n\n— — —\n\n");
}

function teamToText(fav) {
  const all = (state.data.matches || [])
    .filter((m) => matchFavoriteIs(m, fav))
    .filter((m) => m.dateLocal >= todayStr())
    .sort(sortByKickoff);
  if (!all.length) return `Aktuell keine kommenden Spiele für ${fav.label}.`;
  return `${fav.emoji} Kommende Spiele – ${fav.label}\n\n` + all.map(matchToText).join("\n\n— — —\n\n");
}

function compToText(comp) {
  const all = (state.data.matches || [])
    .filter((m) => m.competition === comp)
    .filter((m) => m.dateLocal >= todayStr())
    .sort(sortByKickoff);
  if (!all.length) return `Aktuell keine kommenden Spiele in ${comp}.`;
  return `${COMP_ICON[comp] || "🏆"} Kommende Spiele – ${comp}\n\n` + all.map(matchToText).join("\n\n— — —\n\n");
}

function sortByKickoff(a, b) {
  if (a.dateLocal !== b.dateLocal) return a.dateLocal < b.dateLocal ? -1 : 1;
  const ta = a.kickoff ? new Date(a.kickoff).getTime() : Infinity;
  const tb = b.kickoff ? new Date(b.kickoff).getTime() : Infinity;
  return ta - tb;
}
function matchFavoriteIs(m, fav) {
  const names = [(m.home && m.home.name) || "", (m.away && m.away.name) || ""].join(" ").toLowerCase();
  return fav.aliases.some((a) => names.includes(a));
}

/* ----------------- Teilen (Web Share / WhatsApp / Zwischenablage) ----------------- */

async function shareText(text, title) {
  text += "\n\n— erstellt mit der Spielplan-App";
  if (navigator.share) {
    try { await navigator.share({ title: title || "Spielplan", text }); return; }
    catch (e) { if (e && e.name === "AbortError") return; }
  }
  // Fallback: in Zwischenablage + Option WhatsApp
  try {
    await navigator.clipboard.writeText(text);
    toast("In Zwischenablage kopiert");
  } catch (_) {
    // Letzter Ausweg: WhatsApp-Link
    window.open("https://wa.me/?text=" + encodeURIComponent(text), "_blank");
  }
}

/* ----------------- Erinnerungen ----------------- */

const REMINDER_KEY = "spielplan_reminders";

function loadReminders() {
  try { return JSON.parse(localStorage.getItem(REMINDER_KEY) || "[]"); } catch (_) { return []; }
}
function saveReminders(list) { localStorage.setItem(REMINDER_KEY, JSON.stringify(list)); }

async function setReminder(m) {
  if (!m.kickoff || !m.kickoffKnown) { toast("Anstoßzeit steht noch nicht fest"); return; }
  const kickoff = new Date(m.kickoff).getTime();
  if (kickoff < Date.now()) { toast("Das Spiel hat bereits begonnen"); return; }

  // 1) Kalender-Eintrag erzeugen (zuverlässig – das Handy erinnert dann selbst)
  downloadICS(m);

  // 2) Zusätzlich Benachrichtigung versuchen (während App/SW aktiv)
  if ("Notification" in window) {
    let perm = Notification.permission;
    if (perm === "default") perm = await Notification.requestPermission();
    if (perm === "granted") {
      const fireAt = kickoff - 60 * 60 * 1000; // 60 Min vorher
      const list = loadReminders().filter((r) => r.id !== m.id);
      list.push({ id: m.id, fireAt, title: "Anpfiff in 1 Stunde", body: reminderBody(m) });
      saveReminders(list);
      armReminder({ fireAt, title: "Anpfiff in 1 Stunde", body: reminderBody(m), tag: m.id });
    }
  }
  toast("📅 Im Kalender gespeichert – dein Handy erinnert dich");
}

function reminderBody(m) {
  const tv = m.tv && m.tv.known && m.tv.channels ? " · " + m.tv.channels.join(", ") : "";
  return `${m.home ? m.home.name : "?"} – ${m.away ? m.away.name : "?"}${tv}`;
}

function armReminder(r) {
  if (navigator.serviceWorker && navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage({ type: "schedule-reminder", ...r });
  }
}
function rearmReminders() {
  const now = Date.now();
  const list = loadReminders().filter((r) => r.fireAt > now);
  saveReminders(list);
  for (const r of list) armReminder({ ...r, tag: r.id });
}

function downloadICS(m) {
  const dt = new Date(m.kickoff);
  const start = icsStamp(dt);
  const end = icsStamp(new Date(dt.getTime() + 105 * 60 * 1000)); // ~105 Min
  const home = m.home ? m.home.name : "?";
  const away = m.away ? m.away.name : "?";
  const tv = m.tv && m.tv.known && m.tv.channels ? m.tv.channels.join(", ") : "Sender offen";
  const summary = `⚽ ${home} – ${away}`;
  const desc = `${m.competition}${m.competitionStage ? " – " + m.competitionStage : ""}\\nTV: ${tv}`;
  const ics = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Spielplan//DE", "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    "UID:" + m.id + "@spielplan",
    "DTSTAMP:" + icsStamp(new Date()),
    "DTSTART:" + start, "DTEND:" + end,
    "SUMMARY:" + summary,
    "DESCRIPTION:" + desc,
    "LOCATION:" + tv,
    "BEGIN:VALARM", "TRIGGER:-PT60M", "ACTION:DISPLAY", "DESCRIPTION:Anpfiff in 1 Stunde", "END:VALARM",
    "END:VEVENT", "END:VCALENDAR",
  ].join("\r\n");
  const blob = new Blob([ics], { type: "text/calendar" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${home}-${away}.ics`.replace(/[^\wäöüÄÖÜß.\- ]/g, "");
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
function icsStamp(d) {
  return d.getUTCFullYear() + pad(d.getUTCMonth() + 1) + pad(d.getUTCDate()) + "T" +
    pad(d.getUTCHours()) + pad(d.getUTCMinutes()) + pad(d.getUTCSeconds()) + "Z";
}

/* ----------------- Toast ----------------- */
let toastTimer = null;
function toast(msg) {
  let el = document.querySelector(".toast");
  if (el) el.remove();
  el = document.createElement("div");
  el.className = "toast";
  el.textContent = msg;
  document.body.appendChild(el);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.remove(), 2800);
}

/* ----------------- Teilen-Auswahl-Dialog ----------------- */

function openShareSheet() {
  const sheet = document.getElementById("shareSheet");
  const opts = document.getElementById("shareOptions");
  opts.innerHTML = "";
  const today = todayStr();
  const all = (state.data && state.data.matches) || [];
  const countUpcoming = (pred) => all.filter((m) => m.dateLocal >= today && pred(m)).length;

  // 1) Der aktuell angezeigte Tag (falls Spiele vorhanden)
  const dayMatches = (state.byDate.get(state.selectedDate) || []).length;
  if (dayMatches) {
    const lbl = state.selectedDate === today ? "Alle Spiele heute" : `Alle Spiele am ${formatFull(state.selectedDate)}`;
    addShareOption(opts, "📅", lbl, dayMatches, () => shareText(dayToText(), "Spiele"));
  }
  // 2) Lieblings-Mannschaften – IMMER anzeigen (alle Wettbewerbe zusammen)
  for (const f of FAVORITES) {
    const n = countUpcoming((m) => matchFavoriteIs(m, f));
    addShareOption(opts, f.emoji, f.label, n, n ? () => shareText(teamToText(f), f.label) : null);
  }
  // 3) Wettbewerbe – IMMER anzeigen (Bundesliga, Champions League, DFB-Pokal, WM, EM)
  for (const c of SHARE_COMPS) {
    const n = countUpcoming((m) => m.competition === c);
    addShareOption(opts, COMP_ICON[c], c, n, n ? () => shareText(compToText(c), c) : null);
  }
  showSheet(sheet);
}

// Ein Tipp -> Dialog schließen und sofort die Teilen-Leiste des Handys öffnen.
// count = Anzahl kommender Spiele; onClick = null bedeutet "derzeit keine Spiele".
function addShareOption(container, icon, title, count, onClick) {
  const b = document.createElement("button");
  b.className = "share-option" + (count ? "" : " empty");
  const sub = count ? `${count} ${count === 1 ? "Spiel" : "Spiele"}` : "derzeit keine Spiele";
  b.innerHTML = `<span class="so-icon">${icon}</span><span class="so-txt"><strong>${title}</strong><span class="so-sub">${sub}</span></span><span class="so-arrow">↗</span>`;
  b.addEventListener("click", () => {
    hideSheet(document.getElementById("shareSheet"));
    if (onClick) onClick();
    else toast(`Aktuell keine kommenden Spiele: ${title}`);
  });
  container.appendChild(b);
}

/* ----------------- Einstellungen ----------------- */

function initSettings() {
  // Große Schrift
  const big = localStorage.getItem("spielplan_bigtext") === "1";
  document.documentElement.dataset.bigtext = big ? "true" : "false";
  const bigToggle = document.getElementById("bigTextToggle");
  bigToggle.checked = big;
  bigToggle.addEventListener("change", () => {
    document.documentElement.dataset.bigtext = bigToggle.checked ? "true" : "false";
    localStorage.setItem("spielplan_bigtext", bigToggle.checked ? "1" : "0");
  });

  // Benachrichtigungen
  const notifyToggle = document.getElementById("notifyToggle");
  notifyToggle.checked = ("Notification" in window) && Notification.permission === "granted";
  notifyToggle.addEventListener("change", async () => {
    if (notifyToggle.checked && "Notification" in window) {
      const perm = await Notification.requestPermission();
      notifyToggle.checked = perm === "granted";
      if (perm !== "granted") toast("Benachrichtigungen wurden nicht erlaubt");
    }
  });

  // Favoriten-Liste anzeigen
  const favList = document.getElementById("favList");
  favList.innerHTML = FAVORITES.map((f) => `<div class="fav-item"><span>${f.emoji}</span><span>${f.label}</span></div>`).join("");
}

/* ----------------- Sheets öffnen/schließen ----------------- */
function showSheet(el) { el.classList.remove("hidden"); }
function hideSheet(el) { el.classList.add("hidden"); }

/* ----------------- Navigation ----------------- */

function goDay(delta) {
  state.selectedDate = addDays(state.selectedDate, delta);
  render();
}
function goToday() { state.selectedDate = todayStr(); render(); }

function initDatePicker() {
  // Tippen auf das Datum öffnet einen nativen Datumswähler zum Springen
  const input = document.createElement("input");
  input.type = "date";
  input.style.position = "absolute";
  input.style.opacity = "0";
  input.style.pointerEvents = "none";
  document.body.appendChild(input);
  document.getElementById("currentDate").addEventListener("click", () => {
    input.value = state.selectedDate;
    input.showPicker ? input.showPicker() : input.click();
  });
  input.addEventListener("change", () => { if (input.value) { state.selectedDate = input.value; render(); } });
}

function initSwipe() {
  const main = document.getElementById("content");
  let x0 = null, y0 = null;
  main.addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; }, { passive: true });
  main.addEventListener("touchend", (e) => {
    if (x0 == null) return;
    const dx = e.changedTouches[0].clientX - x0;
    const dy = e.changedTouches[0].clientY - y0;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.6) goDay(dx < 0 ? 1 : -1);
    x0 = y0 = null;
  }, { passive: true });
}

/* ----------------- Start ----------------- */

function init() {
  // Service Worker registrieren (Offline + Erinnerungen).
  // Mit ?nosw in der Adresse lässt er sich zum Testen abschalten.
  if ("serviceWorker" in navigator && !location.search.includes("nosw")) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }

  initSettings();
  initDatePicker();
  initSwipe();

  // Knöpfe verdrahten
  document.getElementById("prevDay").addEventListener("click", () => goDay(-1));
  document.getElementById("nextDay").addEventListener("click", () => goDay(1));
  document.getElementById("todayBtn").addEventListener("click", goToday);
  document.getElementById("settingsBtn").addEventListener("click", () => showSheet(document.getElementById("settingsSheet")));
  document.getElementById("refreshBtn").addEventListener("click", () => { toast("Aktualisiere…"); loadData(); });
  document.getElementById("exportBtn").addEventListener("click", openShareSheet);
  document.querySelectorAll("[data-close-sheet]").forEach((el) =>
    el.addEventListener("click", () => { hideSheet(document.getElementById("settingsSheet")); hideSheet(document.getElementById("shareSheet")); })
  );

  document.getElementById("loading").remove();
  loadData();

  // Live-Aktualisierung: solange die App offen ist, alle 60 Sek. neu laden
  setInterval(() => { if (document.visibilityState === "visible") loadData(); }, 60 * 1000);
  // Beim Wiederöffnen der App immer auf "heute" springen (nicht auf einem alten Tag hängen bleiben)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      state.selectedDate = todayStr();
      state.autoJump = true;
      loadData();
    }
  });
}

document.addEventListener("DOMContentLoaded", init);

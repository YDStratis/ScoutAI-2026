/* Scout.AI dashboard frontend.
 * Ports app.py orchestration + ui_helpers renderers to the browser. All values
 * come from the backend (/api/*) which calls the same deterministic tools —
 * nothing here computes tactical scores. Missing data is shown honestly. */

const ACCENT = "#16e0a4";
const MUTED = "#8aa0c0";
const RISK_COLORS = {
  high: "#ff4d4f", medium: "#ffb020", manageable: "#4aa3ff", advantage: "#16e0a4",
};

// (left%, top%) per formation, matched 1:1 to the backend FORMATIONS slot order.
const PITCH_COORDS = {
  "4-3-3":   [[50,90],[83,71],[61,76],[39,76],[17,71],[50,57],[69,47],[31,47],[83,24],[50,15],[17,24]],
  "4-2-3-1": [[50,90],[83,71],[61,76],[39,76],[17,71],[62,56],[38,56],[80,30],[50,38],[20,30],[50,15]],
  "3-5-2":   [[50,90],[69,76],[50,79],[31,76],[87,54],[66,49],[50,55],[34,49],[13,54],[60,17],[40,17]],
  "4-4-2":   [[50,90],[83,71],[61,76],[39,76],[17,71],[83,45],[61,50],[39,50],[17,45],[60,17],[40,17]],
};

const $ = (id) => document.getElementById(id);

// --- small helpers --------------------------------------------------------- //
function esc(x) {
  if (x === null || x === undefined || x === "") x = "—";
  return String(x).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function riskBadge(level) {
  const color = RISK_COLORS[level] || MUTED;
  return `<span class="risk" style="background:${color}">${esc(level || "n/a")}</span>`;
}
function statusBadge(label, ok, detail) {
  const cls = ok ? "ok" : "off";
  const txt = detail ? `${label} · ${detail}` : label;
  return `<span class="badge ${cls}"><span class="dot"></span>${esc(txt)}</span>`;
}
function num(x, suffix = "") {
  return (x === null || x === undefined) ? "—" : `${esc(x)}${suffix}`;
}

let COVERED = new Set();
let LAST = { analysisId: null, analysis: null, briefing: null, optimize: false };

// --- renderers (port of ui_helpers) --------------------------------------- //
function playerRisk(p) {
  const wm = p.worst_matchup;
  const score = wm ? wm.score : null;
  if (score !== null && score !== undefined && score < 45) return "high";
  if (p.flags && p.flags.length) return "medium";
  return "advantage";
}

function renderPitch(lineup, evalPlayers, opponent) {
  const formation = lineup.formation || "4-3-3";
  const coords = PITCH_COORDS[formation] || PITCH_COORDS["4-3-3"];
  const players = lineup.players || [];
  const evalByName = {};
  (evalPlayers || []).forEach((p) => { evalByName[p.player] = p; });

  const marks = players.slice(0, coords.length).map((slot, i) => {
    const [left, top] = coords[i];
    const name = slot.player_name || slot.player || "—";
    const short = name && name !== "—" ? name.split(/\s+/).pop() : "—";
    const pos = slot.position || "";
    const cls = opponent ? "pmark opp" : "pmark";
    let rk = ACCENT, formLine = "";
    const ev = evalByName[name];
    if (ev && !opponent) {
      rk = RISK_COLORS[playerRisk(ev)] || ACCENT;
      if (ev.form_score !== null && ev.form_score !== undefined)
        formLine = `<div class="fm">form ${esc(ev.form_score)}</div>`;
    }
    return `<div class="${cls}" style="left:${left}%;top:${top}%;--rk:${rk}">` +
      `<div class="disc">${esc(pos)}</div>` +
      `<div class="nm">${esc(short)}</div>${formLine}</div>`;
  }).join("");

  const tag = opponent ? "Opponent XI" : "Your XI";
  const prov = lineup.provisional ? "provisional (built from roster)" : "saved lineup";
  return `<div class="pitch"><div class="goalbox top"></div>` +
    `<div class="goalbox bot"></div>${marks}</div>` +
    `<div class="caption">${tag} · ${esc(formation)} · ${esc(prov)}</div>`;
}

function renderTiles(tiles) {
  const cells = tiles.map(([k, v, s]) =>
    `<div class="tile"><div class="k">${esc(k)}</div>` +
    `<div class="v">${esc(v)}<small>${s ? esc(s) : ""}</small></div></div>`).join("");
  return `<div class="tiles">${cells}</div>`;
}

function renderMatchupTable(matchups) {
  if (!matchups || !matchups.length)
    return `<div class="notice info">Data unavailable. Run importer or add lineup/player attributes.</div>`;
  const rows = matchups.map((m) =>
    "<tr>" +
    `<td>${esc(m.zone)}</td>` +
    `<td><b>${esc(m.our_player)}</b></td>` +
    `<td>${esc(m.opponent_player)}</td>` +
    `<td>${esc(m.matchup_score)}</td>` +
    `<td>${riskBadge(m.risk_level)}</td>` +
    `<td>${esc(m.reason)}</td>` +
    `<td>${esc(m.tactical_action)}</td>` +
    "</tr>").join("");
  return '<table class="mu"><thead><tr>' +
    "<th>Zone</th><th>Our Player</th><th>Opponent</th><th>Score</th>" +
    "<th>Risk</th><th>Tactical Note</th><th>Recommended Action</th>" +
    `</tr></thead><tbody>${rows}</tbody></table>`;
}

function panel(title, bodyHtml) {
  return `<div class="panel"><h4>${esc(title)}</h4>${bodyHtml}</div>`;
}

// --- main views ------------------------------------------------------------ //
function defaultIdx(options, preferred) {
  for (const p of preferred) { const i = options.indexOf(p); if (i >= 0) return i; }
  return 0;
}

function fillSelect(sel, options, labelFn, selectedIdx) {
  sel.innerHTML = options.map((o, i) =>
    `<option value="${esc(o)}"${i === selectedIdx ? " selected" : ""}>${esc(labelFn(o))}</option>`
  ).join("");
}

function teamLabel(name) {
  return COVERED.has(name) ? `${name} ✓` : `${name} (no form data)`;
}

async function bootstrap() {
  let statusData;
  try {
    statusData = await fetch("/api/status").then((r) => r.json());
  } catch (e) {
    $("boot").className = "notice error";
    $("boot").textContent = "Cannot reach backend. Is the server running?";
    return;
  }

  const st = statusData.status;
  const mongo = st.mongo || {}, adk = st.adk || {};
  $("badges").innerHTML =
    statusBadge("MongoDB Atlas", !!mongo.ok, mongo.ok ? (mongo.db || "") : "offline") +
    statusBadge("ADK Agent", !!adk.ok, adk.ok ? `${adk.tools || 0} tools` : "tools-only");

  if (!mongo.ok) {
    $("boot").className = "notice error";
    $("boot").innerHTML = `MongoDB Atlas unreachable: ${esc(mongo.error)}<br>` +
      `Set MONGODB_URI in ScoutAI-2026/.env, then reload.`;
    return;
  }

  const data = await fetch("/api/teams").then((r) => r.json());
  const teams = data.teams || [];
  COVERED = new Set(data.covered || []);
  if (!teams.length) {
    $("boot").className = "notice warn";
    $("boot").textContent =
      "No teams found in MongoDB. Run the BALLDONTLIE importer, then reload.";
    return;
  }

  // Defaults: prefer teams with full match-stat coverage (fully-populated first load).
  const coveredSorted = [...COVERED].sort();
  const teamSel = $("team"), oppSel = $("opponent"), formSel = $("formation");
  fillSelect(teamSel, teams, teamLabel,
    defaultIdx(teams, [...coveredSorted, "South Korea", "Brazil"]));

  function refreshOpponents() {
    const team = teamSel.value;
    const opts = teams.filter((t) => t !== team);
    const list = opts.length ? opts : teams;
    const prefOpp = coveredSorted.filter((c) => c !== team);
    fillSelect(oppSel, list, teamLabel,
      defaultIdx(list, [...prefOpp, "Canada", "France"]));
  }
  refreshOpponents();
  teamSel.addEventListener("change", refreshOpponents);

  // Formation dropdown matches the three the Streamlit app offered.
  formSel.innerHTML = ["4-3-3", "4-2-3-1", "3-5-2"].map((f) =>
    `<option value="${f}">${f}</option>`).join("");

  $("boot").style.display = "none";
  $("app").style.display = "block";

  $("loadBtn").addEventListener("click", () => runAnalysis(false));
  $("optimizeBtn").addEventListener("click", () => runAnalysis(true));
  $("saveBtn").addEventListener("click", saveRecommendation);
}

async function runAnalysis(optimize) {
  const team = $("team").value, opponent = $("opponent").value;
  const formation = $("formation").value, goal = $("goal").value;
  const btn = optimize ? $("optimizeBtn") : $("loadBtn");
  const original = btn.textContent;
  btn.disabled = true; $("loadBtn").disabled = true; $("optimizeBtn").disabled = true;
  btn.innerHTML = `<span class="spinner"></span>Reading MongoDB…`;

  try {
    const res = await fetch("/api/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team, opponent, formation, goal, optimize }),
    }).then((r) => r.json());

    LAST = {
      analysisId: res.analysis_id, analysis: res.analysis,
      briefing: res.briefing, optimize,
    };
    renderResults();
    if (optimize && res.analysis.ok) {
      const rec = (res.analysis.optimization || {}).recommended_formation;
      if (rec) toast(`Optimizer recommends ${rec}.`);
    }
  } catch (e) {
    $("results").innerHTML = `<div class="notice error">Analysis failed: ${esc(e.message)}</div>`;
  } finally {
    btn.innerHTML = original;
    btn.disabled = false; $("loadBtn").disabled = false; $("optimizeBtn").disabled = false;
  }
}

function renderResults() {
  const { analysis, briefing, optimize } = LAST;
  const out = [];
  $("saveBtn").disabled = true;

  (analysis.errors || []).forEach((err) =>
    out.push(`<div class="notice warn">${esc(err)}</div>`));

  if (!analysis.ok) {
    out.push(`<div class="notice info">Tip: run ` +
      `<code>python agent/seed_coach_demo_data.py</code> or the BALLDONTLIE importer ` +
      `if lineups/match stats are missing.</div>`);
    $("results").innerHTML = out.join("");
    return;
  }

  const ev = analysis.evaluation, mu = analysis.matchups, opt = analysis.optimization;
  const team = analysis.team, opponent = analysis.opponent;

  // Data-coverage banner (honest fallback explanation).
  const missing = [team, opponent].filter((t) => !COVERED.has(t));
  if (missing.length) {
    out.push(`<div class="notice info">📊 <b>Limited match-stat coverage</b> for ` +
      missing.map((m) => `<b>${esc(m)}</b>`).join(" and ") +
      ` — recent form, ratings and attribute-based matchup edges fall back to neutral ` +
      `defaults, so weak-link / missing-key-player detection may show fewer (or no) ` +
      `results. Teams marked <b>✓</b> have full match-stat coverage (e.g. South Korea vs Canada).</div>`);
  }

  // Formation optimizer tiles.
  if (optimize && opt && opt.ranking && opt.ranking.length) {
    const best = opt.ranking[0], comp = best.components || {};
    out.push(renderTiles([
      ["Recommended Formation", opt.recommended_formation, ""],
      ["Formation Score", num(best.formation_score), "/100"],
      ["Avg Form", num(comp.lineup_form_average), ""],
      ["Matchup Avg", num(comp.matchup_average), ""],
      ["Weak Links", (best.weak_links || []).length, ""],
      ["Lineup Score", num(ev.lineup_score), "/100"],
    ]));
  }

  // Pitch (ours) + opponent.
  let oppHtml;
  const oppLineup = analysis.opponent_lineup;
  if (oppLineup) {
    oppHtml = renderPitch(oppLineup, null, true);
    const risk = mu.highest_risk;
    if (risk) {
      oppHtml += panel("Key opponent threat",
        `<p><b>${esc(risk.opponent_player)}</b> in ${esc(risk.zone)} — ` +
        `${riskBadge(risk.risk_level)} (duel score ${esc(risk.matchup_score)}).</p>`);
    }
  } else {
    oppHtml = `<div class="notice info">Opponent lineup data unavailable.</div>`;
  }
  out.push(`<h4 class="section">Starting XI</h4>` +
    `<div class="grid-2 grid-pitch">` +
    `<div>${renderPitch(analysis.our_lineup, ev.players, false)}</div>` +
    `<div><h4 class="section" style="margin-top:0">Opponent</h4>${oppHtml}</div></div>`);

  // Missing key player + agent recommendation.
  out.push(`<div class="grid-2 grid-rec">` +
    `<div>${renderWeakLink(ev, analysis.replacement)}</div>` +
    `<div>${renderBriefing(briefing)}</div></div>`);

  // Matchup table.
  out.push(`<h4 class="section">Matchup Analysis</h4>` + renderMatchupTable(mu.matchups || []));
  if (mu.lineup_provisional) {
    out.push(`<div class="caption">Lineups are provisional (granular positions derived ` +
      `from coarse G/D/M/F roster data). Player identities are real BALLDONTLIE data.</div>`);
  }

  // Formation comparison detail.
  if (opt && opt.ranking && opt.ranking.length) {
    out.push(renderFormationComparison(opt.ranking));
  }

  // MongoDB trace.
  out.push(renderTrace(analysis, null));

  $("results").innerHTML = out.join("");
  $("saveBtn").disabled = false;
}

function renderWeakLink(ev, rep) {
  const weak = ev.weak_links || [];
  rep = rep || {};
  if (!weak.length)
    return panel("Missing Key Player / Weak Link",
      `<p style="color:#16e0a4;margin:0">No weak link flagged in this XI.</p>`);
  const w = weak[0];
  let body = `<p style="margin:0 0 .4rem 0"><b>${esc(w.player)}</b> (${esc(w.position)})</p>` +
    `<p style="color:#8aa0c0;font-size:.82rem;margin:0 0 .6rem 0">` +
    (w.flags || []).map((f) => "• " + esc(f)).join("<br>") + `</p>`;
  if (rep && !("error" in rep) && rep.recommended) {
    const r = rep.recommended, imp = rep.matchup_improvement;
    body += `<p style="margin:.4rem 0 0 0">Recommended replacement: ` +
      `<b style="color:${ACCENT}">${esc(r.name)}</b> ` +
      `(form ${esc(r.form_score)}, role fit ${esc(r.role_fit)}).</p>`;
    if (imp) {
      const delta = imp.delta >= 0 ? `+${imp.delta}` : `${imp.delta}`;
      body += `<p style="color:#8aa0c0;font-size:.82rem;margin:.2rem 0 0 0">` +
        `Matchup vs ${esc(imp.vs_defender)}: ${esc(imp.current_matchup_score)} → ` +
        `${esc(imp.new_matchup_score)} (${delta}).</p>`;
    }
  } else if (rep && "error" in rep) {
    body += `<p style="color:#8aa0c0;font-size:.82rem">Replacement: ${esc(rep.error)}</p>`;
  }
  return panel("Missing Key Player / Weak Link", body);
}

function renderBriefing(b) {
  const rows = [
    ["Executive decision", b.executive_decision],
    ["Recommended formation", b.recommended_formation],
    ["Weak link", b.weak_link],
    ["Biggest risk", b.biggest_risk],
    ["Biggest advantage", b.biggest_advantage],
    ["Recommended substitution", b.recommended_substitution],
    ["Tactical adjustment", b.tactical_adjustment],
  ];
  const body = rows.map(([k, v]) =>
    `<p style="margin:0 0 .5rem 0"><span style="color:#8aa0c0;font-size:.68rem;` +
    `letter-spacing:.1em;text-transform:uppercase">${esc(k)}</span><br>${esc(v)}</p>`
  ).join("");
  return panel("Agent Recommendation", body);
}

function renderFormationComparison(ranking) {
  const compKeys = [...new Set(ranking.flatMap((r) => Object.keys(r.components || {})))];
  const head = ["Formation", "Score", ...compKeys.map((k) =>
    k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())), "Weak links"];
  const body = ranking.map((r) => {
    const cells = [r.formation, r.formation_score,
      ...compKeys.map((k) => (r.components || {})[k]), (r.weak_links || []).length];
    return `<tr>${cells.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`;
  }).join("");
  return `<details><summary>Formation comparison detail</summary>` +
    `<table><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>` +
    `<tbody>${body}</tbody></table></details>`;
}

function renderTrace(analysis, saved) {
  const ev = analysis.evaluation || {}, mu = analysis.matchups || {}, opt = analysis.optimization || {};
  const mem = analysis.memory || {};
  const cols = new Set();
  [ev, mu, opt].forEach((d) =>
    ((d.source || {}).collections || []).forEach((c) => cols.add(c)));
  const src = [...cols].sort().filter(Boolean);
  let html = `<details ${saved ? "open" : ""}><summary>🛢 MongoDB Trace</summary>`;
  html += `<p><b>Collections queried:</b> ` +
    (src.map((c) => `<code>${esc(c)}</code>`).join(", ") || "—") + `</p>`;
  const memList = (mem.memories || []).map((m) => `<code>${esc(m.memory_id)}</code>`).join(", ") || "—";
  html += `<p><b>Memory items used:</b> ${esc(mem.count || 0)} — ${memList}</p>`;
  if (saved) {
    html += `<p><b>Recommendation id:</b> <code>${esc(saved.recommendation_id)}</code> ` +
      `in <code>${esc(saved.collection)}</code></p>`;
    if (saved.matchup_report_id)
      html += `<p><b>Matchup report id:</b> <code>${esc(saved.matchup_report_id)}</code></p>`;
    if (saved.run_id)
      html += `<p><b>Agent run id:</b> <code>${esc(saved.run_id)}</code> in <code>coach_agent_runs</code></p>`;
  } else {
    html += `<p class="muted">Press "Save Recommendation" to persist a document and see its id here.</p>`;
  }
  return html + `</details>`;
}

async function saveRecommendation() {
  if (!LAST.analysisId) return;
  const btn = $("saveBtn"), original = btn.textContent;
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>Saving…`;
  try {
    const res = await fetch("/api/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: LAST.analysisId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "save failed");
    }
    const data = await res.json();
    toast(`Saved · recommendation id ${data.saved.recommendation_id}`);
    // Re-render the trace expanded with the saved ids.
    const traceEl = document.querySelector("details:last-of-type");
    if (traceEl) traceEl.outerHTML = renderTrace(LAST.analysis, data.saved);
  } catch (e) {
    toast(`Save failed: ${e.message}`, true);
  } finally {
    btn.innerHTML = original; btn.disabled = false;
  }
}

// --- toast ----------------------------------------------------------------- //
function toast(msg, isError) {
  const t = document.createElement("div");
  t.textContent = msg;
  t.style.cssText =
    `position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:50;` +
    `background:${isError ? "#7a2c2c" : "#121a2b"};border:1px solid ${isError ? "#ff4d4f" : ACCENT};` +
    `color:#e8eef7;padding:.7rem 1.1rem;border-radius:8px;font-size:.9rem;` +
    `box-shadow:0 6px 24px rgba(0,0,0,.5)`;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

bootstrap();

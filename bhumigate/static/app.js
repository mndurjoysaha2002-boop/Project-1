"use strict";
/* BhumiGate dashboard. Plain JS, no dependencies, no innerHTML: every value from the
   server is inserted with textContent, so nothing can inject markup. */

const T = {
  bn: {
    sub: "প্রি-রেজিস্ট্রেশন জালিয়াতি গেট", synth: "সব তথ্য কৃত্রিম (ডামি)। কোনো প্রকৃত ব্যক্তি বা জমির রেকর্ড নেই।",
    tab_gate: "গেট: দলিল যাচাই", tab_queue: "সতর্কতা তালিকা", tab_parcel: "দাগ ও দুই খাতা", tab_mut: "নামজারি আবেদন",
    tab_ledger: "ট্যাম্পার-প্রমাণ খাতা", tab_eval: "মূল্যায়ন", tab_rings: "চক্র শনাক্তকরণ",
    deeds: "দলিল", plots: "দাগ", blocked: "স্থগিত", held: "আটক", clear: "ছাড়",
    scen: "উদাহরণ দলিল (রেজিস্ট্রেশনের মুহূর্তে পুনরায় চালানো)", draft: "খসড়া দলিল", check: "দলিল যাচাই করুন",
    parcel: "দাগ নং", seller: "বিক্রেতার পরিচয় টোকেন", buyer: "ক্রেতার পরিচয় টোকেন", area: "পরিমাণ", unit: "একক",
    reg_date: "নিবন্ধনের তারিখ", exec_date: "সম্পাদনের তারিখ", type: "দলিলের ধরন", sale: "বিক্রয়", hiba: "হেবা",
    broker: "দালাল", writer: "দলিল লেখক", witnesses: "সাক্ষী (কমা দিয়ে)",
    empty_gate: "বাঁ দিক থেকে একটি উদাহরণ বেছে নিন, অথবা খসড়া দলিলের তথ্য দিয়ে যাচাই করুন।",
    BLOCK: "নিবন্ধন স্থগিত", HOLD: "যাচাইয়ের জন্য আটক", CLEAR: "অগ্রসর করা যায়",
    score: "ঝুঁকি স্কোর", baseline_miss: "শুধু খতিয়ান দেখলে এটি ধরা পড়ত না।", baseline_hit: "শুধু খতিয়ান দেখলেও এটি ধরা পড়ত।",
    two: "একই দাগ, দুই খাতা", reg: "সাব-রেজিস্ট্রি খাতা (আইন মন্ত্রণালয়)", ac: "এসি (ল্যান্ড) খতিয়ান (ভূমি মন্ত্রণালয়)",
    differ: "বিক্রেতার হাতে রেজিস্ট্রি অনুযায়ী {a} শতাংশ, খতিয়ান অনুযায়ী {b} শতাংশ। এই ফাঁকেই দ্বৈত বিক্রি লুকিয়ে থাকে।",
    same: "বিক্রেতার হাতে দুই খাতাতেই {a} শতাংশ; অমিল নেই।", dec: "শতাংশ",
    alerts: "সতর্কতা", none_alerts: "কোনো সতর্কতা নেই।", note: "কেস নোট", note_tpl: "টেমপ্লেট", note_llm: "এলএলএম-পরিমার্জিত",
    steps: "অনুসন্ধানের ধাপ", seal: "সিল করা খাতার অবস্থান", officer: "কর্মকর্তার সিদ্ধান্ত (মানুষই চূড়ান্ত)",
    confirm_block: "স্থগিত নিশ্চিত করুন", release: "ছাড় দিন", request_documents: "আরও কাগজ চান", note_ph: "মন্তব্য (ঐচ্ছিক)",
    saved: "সিদ্ধান্ত সংরক্ষিত", last_dec: "সর্বশেষ সিদ্ধান্ত",
    q_dec: "সব সিদ্ধান্ত", q_code: "সব ধরন", q_search: "দলিল/দাগ/নাম খুঁজুন", q_total: "মোট {n}টি", q_open: "খুলুন",
    cols_deed: "দলিল", cols_parcel: "দাগ", cols_date: "তারিখ", cols_seller: "বিক্রেতা", cols_buyer: "ক্রেতা", cols_area: "পরিমাণ",
    cols_dec: "সিদ্ধান্ত", cols_alerts: "সতর্কতা", cols_label: "কৃত্রিম লেবেল",
    p_search: "দাগ বা মৌজা খুঁজুন (যেমন DHK-SAV)", p_facts: "দাগের তথ্য", p_timeline: "হস্তান্তরের ক্রম",
    p_reg_now: "সাব-রেজিস্ট্রি খাতা অনুযায়ী এখন", p_ac_now: "এসি (ল্যান্ড) খতিয়ান অনুযায়ী এখন",
    mutation: "নামজারি", applicant: "আবেদনকারী", cited: "উল্লিখিত দলিল", none_cited: "কোনো দলিল উল্লেখ নেই",
    ledger_head: "খাতার শেষ হ্যাশ", ledger_ok: "অখণ্ড: হ্যাশ-শৃঙ্খল ও দুই অফিসের স্বাক্ষর মিলেছে", entries: "এন্ট্রি",
    d_edit: "১. সিল করা দলিলের পরিমাণ চুপিসারে বদলানো", d_del: "২. খাত থেকে একটি এন্ট্রি মুছে ফেলা",
    d_copy: "৩. কাগজের নকলে পরিমাণ বদলানো হয়েছে কি?", d_insider: "৪. ভেতরের লোক প্রথম বিক্রি মুছে দিলে",
    run: "চালান", deed_id: "দলিল আইডি", new_area: "নকলে লেখা পরিমাণ",
    r_ok: "অক্ষত", r_bad: "ধরা পড়েছে", authentic: "আসল: সিল করা রেকর্ডের সঙ্গে হুবহু মিলেছে", forged: "অমিল: নকল বদলানো",
    changed: "বদলানো ঘর", sealed: "সিল করা মান", presented: "নকলের মান",
    insider_a: "রেকর্ড অক্ষত থাকলে দ্বিতীয় দলিলের সিদ্ধান্ত", insider_b: "প্রথম বিক্রি মুছে ফেললে একই দলিলের সিদ্ধান্ত",
    insider_c: "খাতার অখণ্ডতা যাচাই", insider_note: "মুছে ফেললে গেট দ্বৈত বিক্রি দেখতে পায় না, কিন্তু খাতার হ্যাশ-শৃঙ্খল ভাঙা ধরা পড়ে।",
    pos: "অবস্থান", reason: "কারণ",
    e_warn: "এই সংখ্যাগুলো কৃত্রিম ডেটার ওপর, যেখানে জালিয়াতির ধরন ও হার আমরাই ঠিক করেছি। এগুলো দেখায় পদ্ধতিটি কাজ করে, বাস্তব রেকর্ডে নির্ভুলতা নয়। তুলনার 'বেসলাইন' হলো শুধু এসি (ল্যান্ড) খতিয়ান দেখা, যা একটি মডেলিং সিদ্ধান্ত।",
    e_type: "জালিয়াতির ধরন", e_gate: "গেট ধরেছে", e_base: "শুধু খতিয়ান", e_block: "স্থগিত করেছে",
    e_overall: "সামগ্রিক", e_recall: "জালিয়াতি ধরার হার", e_fp: "বৈধ দলিলে ভুল সতর্কতা", e_prec: "নির্ভুলতা (১% জালিয়াতি ধরলে)",
    e_lag: "নামজারির ফাঁকে (লাগ উইন্ডো) দ্বৈত বিক্রি", e_inside: "ফাঁকের ভেতরে", e_outside: "ফাঁকের বাইরে",
    e_sens: "সংবেদনশীলতা: ফাঁকের ভেতরের দ্বৈত বিক্রির ধারণাকৃত অংশ বদলালে", e_share: "ফাঁকের ভেতরের অংশ", e_mut: "নামজারি গেট", e_ring: "চক্র আবিষ্কার",
    r_none: "কোনো চক্র পাওয়া যায়নি।", r_hub: "কেন্দ্রীয় ব্যক্তি", r_members: "সদস্য", r_blocked: "স্থগিত দলিল", r_deeds: "দলিল", r_rate: "স্থগিতের হার",
    err: "ত্রুটি", loading: "লোড হচ্ছে…", mode: "ইংরেজি",
  },
  en: {
    sub: "Pre-registration fraud gate", synth: "All data is synthetic (dummy). No real person or land record is used.",
    tab_gate: "Gate: check a deed", tab_queue: "Alert queue", tab_parcel: "Plot and two ledgers", tab_mut: "Mutation applications",
    tab_ledger: "Tamper-proof ledger", tab_eval: "Evaluation", tab_rings: "Ring detection",
    deeds: "deeds", plots: "plots", blocked: "blocked", held: "held", clear: "clear",
    scen: "Example deeds (replayed at the moment of registration)", draft: "Draft deed", check: "Check deed",
    parcel: "Plot ID", seller: "Seller identity token", buyer: "Buyer identity token", area: "Area", unit: "Unit",
    reg_date: "Registration date", exec_date: "Execution date", type: "Deed type", sale: "Sale", hiba: "Hiba (gift)",
    broker: "Broker", writer: "Deed writer", witnesses: "Witnesses (comma separated)",
    empty_gate: "Pick an example on the left, or fill in a draft deed and check it.",
    BLOCK: "Block registration", HOLD: "Hold for review", CLEAR: "Clear to proceed",
    score: "Risk score", baseline_miss: "A khatian-only check would have missed this.", baseline_hit: "A khatian-only check would also have flagged this.",
    two: "One plot, two ledgers", reg: "Sub-registry ledger (Law Ministry)", ac: "AC Land khatian (Land Ministry)",
    differ: "The seller holds {a} decimals per the registry but {b} per the khatian. Double sales hide in this gap.",
    same: "The seller holds {a} decimals in both ledgers; no mismatch.", dec: "decimals",
    alerts: "Alerts", none_alerts: "No alerts.", note: "Case note", note_tpl: "template", note_llm: "LLM-polished",
    steps: "Investigation steps", seal: "Position in the sealed ledger", officer: "Officer decision (a human always decides)",
    confirm_block: "Confirm block", release: "Release", request_documents: "Request documents", note_ph: "Comment (optional)",
    saved: "Decision saved", last_dec: "Latest decision",
    q_dec: "All decisions", q_code: "All types", q_search: "Search deed, plot or name", q_total: "{n} in total", q_open: "Open",
    cols_deed: "Deed", cols_parcel: "Plot", cols_date: "Date", cols_seller: "Seller", cols_buyer: "Buyer", cols_area: "Area",
    cols_dec: "Decision", cols_alerts: "Alerts", cols_label: "Synthetic label",
    p_search: "Search plot or mouza (e.g. DHK-SAV)", p_facts: "Plot facts", p_timeline: "Transfer history",
    p_reg_now: "Per the sub-registry ledger now", p_ac_now: "Per the AC Land khatian now",
    mutation: "Mutation", applicant: "Applicant", cited: "Deed cited", none_cited: "No deed cited",
    ledger_head: "Ledger head hash", ledger_ok: "Intact: hash chain and both office signatures verify", entries: "entries",
    d_edit: "1. Quietly change the area on a sealed deed", d_del: "2. Delete one entry from the ledger",
    d_copy: "3. Was the paper copy altered?", d_insider: "4. An insider deletes the first sale",
    run: "Run", deed_id: "Deed ID", new_area: "Area written on the copy",
    r_ok: "Intact", r_bad: "Caught", authentic: "Authentic: identical to the sealed record", forged: "Mismatch: the copy was altered",
    changed: "Changed field", sealed: "Sealed value", presented: "Value on the copy",
    insider_a: "Decision on the second deed with intact records", insider_b: "Decision on the same deed after the first sale is deleted",
    insider_c: "Ledger integrity check", insider_note: "After the deletion the gate cannot see the double sale, but the broken hash chain exposes the deletion.",
    pos: "Position", reason: "Reason",
    e_warn: "These numbers come from synthetic data whose fraud patterns and rates we chose ourselves. They show that the mechanism works, not how accurate it would be on real records. The baseline is a khatian-only check, which is a modelling choice.",
    e_type: "Fraud type", e_gate: "Gate caught", e_base: "Khatian only", e_block: "Blocked",
    e_overall: "Overall", e_recall: "Fraud recall", e_fp: "False alerts on legitimate deeds", e_prec: "Precision (at 1% fraud prevalence)",
    e_lag: "Double sales inside the mutation lag window", e_inside: "Inside the window", e_outside: "Outside the window",
    e_sens: "Sensitivity: varying the assumed share of double sales inside the window", e_share: "Share inside window", e_mut: "Mutation gate", e_ring: "Ring discovery",
    r_none: "No ring found.", r_hub: "Hub", r_members: "Members", r_blocked: "Blocked deeds", r_deeds: "deeds", r_rate: "block rate",
    err: "Error", loading: "Loading…", mode: "বাংলা",
  },
};
const FRAUD_LABEL = {
  DOUBLE_SALE: ["একই জমি দুইবার বিক্রি", "Double sale"], CHAIN_BREAK: ["মালিকানার ধারাবাহিকতা নেই", "Broken chain"],
  IMPERSONATION: ["ছদ্মবেশী বিক্রেতা", "Look-alike seller"], OVERSELL: ["মালিকানার বেশি বিক্রি", "Oversell"],
  ANACHRONISM: ["মালিক হওয়ার আগে দলিল", "Executed before owning"], RAPID_FLIP: ["দ্রুত হাতবদল", "Rapid flipping"],
  KHAS_LAND_SALE: ["খাস জমি বিক্রি", "Khas land sale"], PENDING_CASE: ["মামলাধীন জমি", "Pending case"],
};
const GLYPH = { BLOCK: "✕", HOLD: "!", CLEAR: "✓" };
const TABS = ["gate", "queue", "parcel", "mut", "ledger", "eval", "rings"];

let lang = "bn", tab = "gate", scenarios = [], summary = null;
let gateState = { draft: null, result: null, scenario: null, officerId: null };
try { lang = localStorage.getItem("lang") || "bn"; } catch (e) { /* storage blocked: fine */ }

const t = (k, vars) => { let s = (T[lang][k] ?? T.en[k] ?? k); for (const v in (vars || {})) s = s.replace("{" + v + "}", vars[v]); return s; };
const L = (pair) => pair[lang === "bn" ? 0 : 1];
const digits = (s) => lang === "bn" ? String(s).replace(/\d/g, d => "০১২৩৪৫৬৭৮৯"[d]) : String(s);
const num = (x, p = 2) => digits((+x).toFixed(p).replace(/\.?0+$/, ""));
const pct = (x) => digits(Math.round(x * 100)) + "%";

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else if (k === "style") {   // via the CSSOM, so the strict CSP (no inline style attributes) still holds
      for (const decl of String(v).split(";")) { const i = decl.indexOf(":"); if (i > 0) el.style.setProperty(decl.slice(0, i).trim(), decl.slice(i + 1).trim()); }
    }
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(String(c)));
  return el;
}

async function api(path, body) {
  const res = await fetch(path, body ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : undefined);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
function toast(msg) {
  const el = h("div", { class: "toast", role: "status" }, msg);
  document.body.append(el); setTimeout(() => el.remove(), 3200);
}
const fail = (e) => toast(t("err") + ": " + e.message);

/* ---------- shell ---------- */
function renderShell() {
  document.documentElement.lang = lang;
  document.getElementById("brandSub").textContent = t("sub");
  document.getElementById("synthNote").textContent = t("synth");
  document.getElementById("langBtn").textContent = t("mode");
  document.getElementById("themeBtn").textContent = "◐";
  document.getElementById("themeBtn").setAttribute("aria-label", "theme");
  const tabs = document.getElementById("tabs");
  tabs.replaceChildren(...TABS.map(id => h("button", {
    class: "tab", role: "tab", "aria-selected": id === tab, onclick: () => { tab = id; render(); },
  }, t("tab_" + id))));
  renderMain();
}
function render() { renderShell(); }

function topBar(title) {
  const s = summary;
  return h("div", { class: "top" }, h("h1", {}, title),
    s && h("div", { class: "stats" },
      h("span", {}, h("b", {}, digits(s.deeds)), " " + t("deeds")),
      h("span", {}, h("b", {}, digits(s.parcels)), " " + t("plots")),
      h("span", {}, h("b", {}, digits(s.decisions.BLOCK)), " " + t("blocked")),
      h("span", {}, h("b", {}, digits(s.decisions.HOLD)), " " + t("held")),
      h("span", {}, h("b", {}, digits(s.decisions.CLEAR)), " " + t("clear"))));
}

function renderMain() {
  const main = document.getElementById("main");
  main.replaceChildren(topBar(t("tab_" + tab)));
  const view = { gate: viewGate, queue: viewQueue, parcel: viewParcel, mut: viewMut, ledger: viewLedger, eval: viewEval, rings: viewRings }[tab];
  const box = h("div", {}, h("p", { class: "muted" }, t("loading")));
  main.append(box);
  Promise.resolve(view(box)).catch(fail);
}

/* ---------- shared pieces ---------- */
const badge = (d) => h("span", { class: "badge " + d }, GLYPH[d] + " " + t(d));
function bars(two, sellerPid) {
  const mk = (cls, holders) => {
    const total = Math.max(two.parcel_total, holders.reduce((a, x) => a + x.area, 0), 0.01);
    return h("div", { class: "bar " + cls }, holders.map(x => h("div", {
      class: "seg" + (x.pid === sellerPid ? " me" : ""), style: `flex:0 0 ${(x.area / total * 100).toFixed(2)}%`,
      title: x.name + " — " + num(x.area) + " " + t("dec"),
    }, (x.area / total > 0.14) ? x.name + " " + num(x.area) : "")));
  };
  const a = two.seller_registry, b = two.seller_ac_land, differs = Math.abs(a - b) > 0.06;
  return h("div", { class: "twin" },
    h("div", {}, h("div", { class: "lbl reg" }, h("span", {}, t("reg")), h("span", {}, num(two.parcel_total) + " " + t("dec"))), mk("reg", two.registry)),
    h("div", {}, h("div", { class: "lbl ac" }, h("span", {}, t("ac"))), mk("ac", two.ac_land)),
    h("div", { class: "gap-note" + (differs ? "" : " same") }, differs ? t("differ", { a: num(a), b: num(b) }) : t("same", { a: num(a) })));
}

function renderCase(c, officerId) {
  const sevClass = (s) => s >= 70 ? "hi" : s >= 30 ? "mid" : "lo";
  const real = c.alerts.filter(a => a.code !== "PENDING_MUTATION" || c.alerts.length === 1);
  const out = h("div", { class: "stack" },
    h("div", { class: "verdict " + c.decision },
      h("div", { class: "glyph", "aria-hidden": "true" }, GLYPH[c.decision]),
      h("div", {}, h("div", { class: "word" }, t(c.decision)),
        h("div", { class: "muted" }, c.baseline_flag ? t("baseline_hit") : t("baseline_miss"))),
      h("div", { class: "score" }, t("score"), h("br"), h("b", {}, digits(c.score) + "/" + digits(100)),
        h("div", { class: "meter" }, h("i", { style: `width:${c.score}%` })))),
    h("div", { class: "panel" }, h("h2", {}, t("two")), bars(c.two_ledgers, c.deed.seller)),
    h("div", { class: "panel" }, h("h2", {}, t("alerts")),
      c.alerts.length ? c.alerts.map(a => h("div", { class: "alert " + sevClass(a.severity) },
        h("span", { class: "sev" }, digits(a.severity)), h("div", { class: "t" }, lang === "bn" ? a.title_bn : a.title_en),
        h("div", {}, lang === "bn" ? a.text_bn : a.text_en))) : h("p", { class: "muted" }, t("none_alerts"))),
    h("div", { class: "panel" }, h("h2", {}, t("note"), h("span", { class: "tag" }, c.note_source === "llm" ? t("note_llm") : t("note_tpl"))),
      h("div", { class: "note" }, lang === "bn" ? c.note_bn : c.note_en),
      h("h3", {}, t("steps")),
      h("ol", { class: "steps" }, c.steps.map(s => h("li", {}, h("span", { class: "tool" }, s.tool), lang === "bn" ? s.summary_bn : s.summary_en))),
      c.ledger && h("p", { class: "muted" }, t("seal") + ": #" + digits(c.ledger.index), " ", h("span", { class: "mono" }, c.ledger.entry_hash.slice(0, 16) + "…"))));
  if (officerId) out.append(officerPanel(officerId, c.officer));
  return out;
}

function officerPanel(id, last) {
  const note = h("input", { placeholder: t("note_ph"), "aria-label": t("note_ph"), maxlength: 300 });
  const status = h("p", { class: "muted" }, last ? t("last_dec") + ": " + t(last.action) + " (" + last.at.replace("T", " ").replace("+00:00", " UTC") + ")" : "");
  const act = (action) => async () => {
    try { const r = await api("/api/officer", { deed_id: id, action, note: note.value, officer: "demo-officer" }); status.textContent = t("saved") + ": " + t(r.action); }
    catch (e) { fail(e); }
  };
  return h("div", { class: "panel" }, h("h2", {}, t("officer")),
    h("div", { class: "officer" }, note,
      h("button", { class: "btn", type: "button", onclick: act("confirm_block") }, t("confirm_block")),
      h("button", { class: "btn alt", type: "button", onclick: act("request_documents") }, t("request_documents")),
      h("button", { class: "btn alt", type: "button", onclick: act("release") }, t("release"))), status);
}

/* ---------- gate ---------- */
async function viewGate(box) {
  if (!scenarios.length) scenarios = await api("/api/scenarios");
  const f = {};
  const field = (key, label, extra = {}) => {
    const input = extra.options
      ? h("select", { name: key }, extra.options.map(([v, l]) => h("option", { value: v }, l)))
      : h("input", { name: key, type: extra.type || "text", step: extra.step, autocomplete: "off" });
    f[key] = input; return h("label", {}, label, input);
  };
  const resultBox = h("div", {}, h("div", { class: "empty" }, t("empty_gate")));
  const chips = h("div", { class: "chips", role: "group", "aria-label": t("scen") });
  const form = h("form", { class: "draft", onsubmit: (e) => { e.preventDefault(); run(); } },
    field("parcel_id", t("parcel")), field("seller", t("seller")), field("buyer", t("buyer")),
    h("div", { class: "row" }, field("area", t("area"), { type: "number", step: "0.01" }),
      field("unit", t("unit"), { options: [["decimal", "শতাংশ"], ["katha", "কাঠা"], ["bigha", "বিঘা"], ["acre", "একর"], ["sqft", "বর্গফুট"]] })),
    h("div", { class: "row" }, field("reg_date", t("reg_date"), { type: "date" }), field("exec_date", t("exec_date"), { type: "date" })),
    field("deed_type", t("type"), { options: [["sale", t("sale")], ["hiba", t("hiba")]] }),
    h("div", { class: "row" }, field("broker", t("broker")), field("writer", t("writer"))),
    field("witnesses", t("witnesses")),
    h("button", { class: "btn", type: "submit", id: "runBtn" }, t("check")));

  const fill = (d) => { for (const k in f) f[k].value = k === "witnesses" ? (d.witnesses || []).join(", ") : (d[k] ?? ""); };
  const collect = () => {
    const d = {}; for (const k in f) d[k] = f[k].value;
    d.witnesses = d.witnesses.split(",").map(s => s.trim()).filter(Boolean);
    if (gateState.replay) d.replay_of = gateState.replay;
    return d;
  };
  async function run() {
    const btn = document.getElementById("runBtn"); btn.disabled = true;
    try {
      const c = await api("/api/gate", collect());
      gateState.result = c;
      resultBox.replaceChildren(renderCase(c, gateState.replay || null));
    } catch (e) { fail(e); } finally { btn.disabled = false; }
  }
  scenarios.forEach(s => chips.append(h("button", {
    class: "chip", type: "button", "aria-pressed": gateState.scenario === s.id,
    onclick: (ev) => { gateState.scenario = s.id; gateState.replay = s.draft.replay_of; fill(s.draft); gateState.draft = s.draft;
      [...chips.children].forEach(c => c.setAttribute("aria-pressed", "false")); ev.currentTarget.setAttribute("aria-pressed", "true"); run(); },
  }, lang === "bn" ? s.label_bn : s.label_en)));
  form.addEventListener("input", () => { if (gateState.replay && gateState.draft) { /* edits keep the replay position */ } });

  if (gateState.draft) { fill(gateState.draft); if (gateState.result) resultBox.replaceChildren(renderCase(gateState.result, gateState.replay || null)); }
  box.replaceChildren(
    h("p", { class: "muted" }, t("scen")), chips,
    h("div", { class: "cols" }, h("div", { class: "panel" }, h("h2", {}, t("draft")), form), resultBox));
}

/* ---------- queue ---------- */
async function viewQueue(box) {
  const codes = Object.keys(summary.alert_codes);
  const sel = h("select", { "aria-label": t("q_dec") }, h("option", { value: "" }, t("q_dec")), ["BLOCK", "HOLD"].map(d => h("option", { value: d }, t(d))));
  const csel = h("select", { "aria-label": t("q_code") }, h("option", { value: "" }, t("q_code")), codes.map(c => h("option", { value: c }, c)));
  const q = h("input", { placeholder: t("q_search"), "aria-label": t("q_search") });
  const body = h("div", {});
  async function load() {
    const p = new URLSearchParams({ decision: sel.value, code: csel.value, q: q.value, limit: 40 });
    const r = await api("/api/queue?" + p);
    body.replaceChildren(h("p", { class: "muted" }, t("q_total", { n: digits(r.total) })),
      h("div", { class: "scroll" }, h("table", {},
        h("thead", {}, h("tr", {}, ["cols_deed", "cols_parcel", "cols_date", "cols_seller", "cols_buyer", "cols_area", "cols_dec", "cols_alerts", "cols_label"].map(k => h("th", {}, t(k))))),
        h("tbody", {}, r.rows.map(x => h("tr", { class: "click", tabindex: 0, onclick: () => openCase(x.deed_id), onkeydown: (e) => { if (e.key === "Enter") openCase(x.deed_id); } },
          h("td", { class: "mono id" }, x.deed_id), h("td", { class: "mono id" }, x.parcel_id), h("td", { class: "id" }, digits(x.reg_date)),
          h("td", {}, x.seller_name), h("td", {}, x.buyer_name), h("td", {}, num(x.area)),
          h("td", {}, badge(x.decision), " ", digits(x.score)), h("td", { class: "mono codes" }, x.codes.join(", ")),
          h("td", { class: "mono muted" }, x.synthetic_label || "—")))))));
  }
  [sel, csel].forEach(e => e.addEventListener("change", () => load().catch(fail)));
  let timer; q.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => load().catch(fail), 250); });
  box.replaceChildren(h("div", { class: "filters" }, sel, csel, q), body);
  await load();
}
async function openCase(id) {
  try {
    const c = await api("/api/deed/" + encodeURIComponent(id));
    const d = c.deed;
    gateState = { draft: { parcel_id: d.parcel_id, seller: d.seller, buyer: d.buyer, area: d.area, unit: "decimal", deed_type: d.deed_type,
      reg_date: d.reg_date, exec_date: d.exec_date, broker: d.broker, writer: d.writer, witnesses: d.witnesses }, result: c, scenario: null, replay: id };
    tab = "gate"; render();
  } catch (e) { fail(e); }
}

/* ---------- parcel ---------- */
async function viewParcel(box) {
  const q = h("input", { placeholder: t("p_search"), "aria-label": t("p_search"), value: gateState.parcelQ || "" });
  const list = h("div", {}), view = h("div", {});
  const show = async (id) => {
    const r = await api("/api/parcel/" + encodeURIComponent(id)); const p = r.parcel;
    const mk = (cls, hs) => h("div", { class: "bar " + cls }, hs.map(x => h("div", { class: "seg", style: `flex:0 0 ${(x.area / p.total_area * 100).toFixed(2)}%`, title: x.name + " " + num(x.area) },
      x.area / p.total_area > 0.14 ? x.name + " " + num(x.area) : "")));
    view.replaceChildren(h("div", { class: "panel stack" },
      h("h2", {}, t("p_facts") + ": " + p.parcel_id),
      h("dl", { class: "kv" }, [["Mouza", p.mouza], ["Upazila", p.upazila], ["Survey", p.survey + " / " + digits(p.khatian_no)], ["Dag", digits(p.dag_no)],
        [t("area"), num(p.total_area) + " " + t("dec")], ["Class", p.land_class], ["Case", p.case_filed ? digits(p.case_filed) : "—"]].flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])),
      h("div", { class: "twin" }, h("div", { class: "lbl reg" }, t("p_reg_now")), mk("reg", r.registry_holders),
        h("div", { class: "lbl ac" }, t("p_ac_now")), mk("ac", r.ac_land_holders)),
      h("h3", {}, t("p_timeline")),
      h("div", { class: "scroll" }, h("table", {}, h("thead", {}, h("tr", {}, ["cols_deed", "cols_date", "cols_seller", "cols_buyer", "cols_area", "cols_dec", "mutation"].map(k => h("th", {}, t(k))))),
        h("tbody", {}, r.timeline.map(d => h("tr", { class: "click", tabindex: 0, onclick: () => openCase(d.deed_id) },
          h("td", { class: "mono" }, d.deed_id), h("td", {}, digits(d.reg_date)), h("td", {}, d.seller_name), h("td", {}, d.buyer_name), h("td", {}, num(d.area)),
          h("td", {}, badge(d.decision)), h("td", {}, d.mut_status + (d.mut_date ? " " + digits(d.mut_date) : "")))))))));
  };
  const search = async () => {
    gateState.parcelQ = q.value; if (!q.value.trim()) { list.replaceChildren(); return; }
    const rows = await api("/api/parcels?q=" + encodeURIComponent(q.value));
    list.replaceChildren(h("div", { class: "chips" }, rows.map(r => h("button", { class: "chip", type: "button", onclick: () => show(r.parcel_id).catch(fail) }, r.parcel_id + " · " + digits(r.deeds) + " " + t("deeds")))));
  };
  let timer; q.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => search().catch(fail), 250); });
  box.replaceChildren(h("div", { class: "filters" }, q), list, view);
  if (gateState.result) show(gateState.result.deed.parcel_id).catch(() => {});
}

/* ---------- mutation applications ---------- */
async function viewMut(box) {
  const r = await api("/api/mutations");
  box.replaceChildren(h("p", { class: "muted" }, t("q_total", { n: digits(r.total) })),
    h("div", { class: "stack" }, r.rows.slice(0, 25).map(m => h("div", { class: "panel" },
      h("div", {}, badge(m.decision), " ", h("span", { class: "mono" }, m.app_id + " · " + m.parcel_id), " ", h("span", { class: "tag" }, m.synthetic_label || "")),
      h("p", {}, t("applicant") + ": " + m.applicant_name + " · " + num(m.area) + " " + t("dec") + " · " + digits(m.applied_date) + " · " + (m.cited_deed || t("none_cited"))),
      m.alerts.map(a => h("div", { class: "alert hi" }, h("div", { class: "t" }, lang === "bn" ? a.title_bn : a.title_en), h("div", {}, lang === "bn" ? a.text_bn : a.text_en)))))));
}

/* ---------- ledger ---------- */
async function viewLedger(box) {
  if (!scenarios.length) scenarios = await api("/api/scenarios");
  const led = await api("/api/ledger");
  const deedId = h("input", { value: scenarios[0].draft.replay_of, "aria-label": t("deed_id"), class: "mono" });
  const newArea = h("input", { value: "99", type: "number", "aria-label": t("new_area") });
  const out = { edit: h("div", {}), del: h("div", {}), copy: h("div", {}), insider: h("div", {}) };
  const verdict = (v) => v.ok ? h("p", { class: "res-ok" }, "✓ " + t("r_ok"))
    : h("div", {}, h("p", { class: "res-bad" }, "✕ " + t("r_bad")), h("p", {}, t("pos") + ": #" + digits(v.first_bad_index) + " — " + t("reason") + ": " + v.reason));
  const tam = (kind, slot) => async () => { const r = await api("/api/tamper", { kind, deed_id: deedId.value.trim() }); slot.replaceChildren(verdict(r.verification)); };
  const copy = async () => {
    const r = await api("/api/verify_copy", { deed_id: deedId.value.trim(), changes: { area: (+newArea.value).toFixed(4) } });
    out.copy.replaceChildren(r.authentic ? h("p", { class: "res-ok" }, "✓ " + t("authentic"))
      : h("div", {}, h("p", { class: "res-bad" }, "✕ " + t("forged")), h("p", {}, t("changed") + ": " + r.changed_fields.join(", ") + " — " + t("sealed") + ": " + num(r.sealed.area) + " → " + t("presented") + ": " + num(r.presented.area))));
  };
  const insider = async () => {
    const r = await api("/api/insider", {});
    out.insider.replaceChildren(h("dl", { class: "kv" },
      h("dt", {}, t("insider_a")), h("dd", {}, badge(r.with_intact_records.decision), " " + r.second_deed),
      h("dt", {}, t("insider_b")), h("dd", {}, badge(r.after_first_sale_deleted.decision)),
      h("dt", {}, t("insider_c")), h("dd", {}, verdict(r.ledger_check))), h("p", { class: "muted" }, t("insider_note")));
  };
  const demo = (title, ...kids) => h("div", { class: "demo" }, h("h3", {}, title), ...kids);
  const go = (fn) => h("button", { class: "btn", type: "button", onclick: () => fn().catch(fail) }, t("run"));
  box.replaceChildren(
    h("div", { class: "panel" }, h("p", { class: led.status.ok ? "res-ok" : "res-bad" }, (led.status.ok ? "✓ " + t("ledger_ok") : "✕") + " — " + digits(led.entries) + " " + t("entries")),
      h("p", { class: "muted" }, t("ledger_head") + ": ", h("span", { class: "mono" }, led.head))),
    h("p", {}, h("label", {}, t("deed_id") + " ", deedId)),
    demo(t("d_edit"), go(tam("edit", out.edit)), out.edit),
    demo(t("d_del"), go(tam("delete", out.del)), out.del),
    demo(t("d_copy"), h("label", {}, t("new_area") + " ", newArea), " ", go(copy), out.copy),
    demo(t("d_insider"), go(insider), out.insider));
}

/* ---------- evaluation ---------- */
async function viewEval(box) {
  const r = await api("/api/eval"), o = r.overall;
  const row = (name, v) => h("tr", {}, h("td", {}, name), h("td", {}, digits(v.n)),
    h("td", {}, h("span", { class: "hbar g", style: `width:${v.gate_alert_recall * 120}px` }), " " + pct(v.gate_alert_recall)),
    h("td", {}, h("span", { class: "hbar b", style: `width:${v.baseline_recall * 120}px` }), " " + pct(v.baseline_recall)),
    h("td", {}, pct(v.gate_block_recall)));
  const lag = r.lag_window;
  box.replaceChildren(h("div", { class: "warn" }, t("e_warn")),
    h("div", { class: "panel stack" },
      h("p", { class: "muted" }, digits(r.dataset.n_parcels) + " " + t("plots") + ", " + digits(r.dataset.deeds) + " " + t("deeds") + ", seed " + r.dataset.seed),
      h("div", { class: "scroll" }, h("table", {}, h("thead", {}, h("tr", {}, [t("e_type"), "n", t("e_gate"), t("e_base"), t("e_block")].map(x => h("th", {}, x)))),
        h("tbody", {}, Object.entries(r.per_type).map(([k, v]) => row(L(FRAUD_LABEL[k] || [k, k]), v))))),
      h("h3", {}, t("e_overall")),
      h("dl", { class: "kv" }, h("dt", {}, t("e_recall")), h("dd", {}, "gate " + pct(o.gate.alert_recall) + " · baseline " + pct(o.baseline.alert_recall)),
        h("dt", {}, t("e_fp")), h("dd", {}, "gate " + pct(o.gate.false_alert_rate) + " · baseline " + pct(o.baseline.false_alert_rate)),
        h("dt", {}, t("e_prec")), h("dd", {}, "gate " + pct(o.gate.precision_at_1pct_prevalence) + " · baseline " + pct(o.baseline.precision_at_1pct_prevalence))),
      h("h3", {}, t("e_lag")),
      h("dl", { class: "kv" }, h("dt", {}, t("e_inside") + " (n=" + digits(lag.inside_lag_window.n) + ")"), h("dd", {}, "gate " + pct(lag.inside_lag_window.gate_recall) + " · baseline " + pct(lag.inside_lag_window.baseline_recall)),
        h("dt", {}, t("e_outside") + " (n=" + digits(lag.outside_lag_window.n) + ")"), h("dd", {}, "gate " + pct(lag.outside_lag_window.gate_recall) + " · baseline " + pct(lag.outside_lag_window.baseline_recall))),
      h("h3", {}, t("e_sens")),
      h("table", {}, h("thead", {}, h("tr", {}, [t("e_share"), "n", "gate", "baseline"].map(x => h("th", {}, x)))),
        h("tbody", {}, r.sensitivity_in_window_share.map(s => h("tr", {}, h("td", {}, pct(s.in_window_share)), h("td", {}, digits(s.n)), h("td", {}, pct(s.gate_recall)), h("td", {}, pct(s.baseline_recall)))))),
      h("h3", {}, t("e_mut")), h("p", {}, pct(r.mutation_gate.alert_recall) + " / " + digits(r.mutation_gate.fraud_apps) + " · " + t("e_fp") + " " + pct(r.mutation_gate.false_alert_rate)),
      h("h3", {}, t("e_ring")), h("p", {}, digits(r.ring_discovery.true_found) + "/" + digits(r.ring_discovery.true_ring_members) + " · " + digits(r.ring_discovery.false_suspects) + " false"),
      h("ul", { class: "muted" }, r.caveats.map(c => h("li", {}, c)))));
}

/* ---------- rings ---------- */
async function viewRings(box) {
  const r = await api("/api/rings");
  box.replaceChildren(r.clusters.length ? h("div", { class: "stack" }, r.clusters.map(c => h("div", { class: "panel" },
    h("h2", {}, t("r_hub") + ": " + c.hub.name), h("p", {}, t("r_blocked") + ": " + digits(c.blocked_deeds)),
    h("div", { class: "scroll" }, h("table", {}, h("thead", {}, h("tr", {}, [t("r_members"), "", t("r_deeds"), t("r_blocked"), t("r_rate")].map(x => h("th", {}, x)))),
      h("tbody", {}, c.members.map(m => h("tr", {}, h("td", {}, m.name), h("td", {}, m.role_bn), h("td", {}, digits(m.deeds)), h("td", {}, digits(m.blocked_deeds)), h("td", {}, pct(m.block_rate))))))))))
    : h("div", { class: "empty" }, t("r_none")));
}

/* ---------- boot ---------- */
document.getElementById("langBtn").addEventListener("click", () => { lang = lang === "bn" ? "en" : "bn"; try { localStorage.setItem("lang", lang); } catch (e) { } render(); });
document.getElementById("themeBtn").addEventListener("click", () => {
  const r = document.documentElement, dark = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  r.dataset.theme = dark ? "light" : "dark";
});
(async () => { try { summary = await api("/api/summary"); } catch (e) { fail(e); } render(); })();

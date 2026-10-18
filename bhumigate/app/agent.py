"""Investigator agent: turns detector evidence into a case note for the officer.

Design rule: the language model never decides anything. Decisions come from the
deterministic detectors (detectors.py + gate.py). This module only

  1. runs a fixed sequence of tools over the records (the "investigation"),
     and records each call so the officer can see what was looked at;
  2. writes the note in Bangla and English from templates, using only numbers
     that come straight from the evidence;
  3. optionally asks an LLM to polish the Bangla wording, if ANTHROPIC_API_KEY
     is set. The polish step is off by default, falls back silently to the
     template on any error, and never changes the decision. It only ever sees
     synthetic data.

So the demo works with no internet and no API key.
"""

from __future__ import annotations

import json
import os
import urllib.request

from .units import bn_num

ROLE_BN = {"broker": "দালাল", "writer": "দলিল লেখক", "witness": "সাক্ষী"}
ROLE_EN = {"broker": "broker", "writer": "deed writer", "witness": "witness"}

TITLES = {
    "KHAS_ACQUIRED": ("খাস/অধিগৃহীত জমি", "Khas / acquired land"),
    "DOUBLE_SALE": ("একই জমি দ্বিতীয়বার বিক্রি", "Double sale"),
    "IMPERSONATION": ("ছদ্মবেশী বিক্রেতা (নামের মিল)", "Look-alike seller"),
    "AREA_EXCEEDS_PARCEL": ("দাগের চেয়ে বড় দলিল", "Deed larger than the plot"),
    "CHAIN_BREAK": ("মালিকানার ধারাবাহিকতা নেই", "Broken ownership chain"),
    "ANACHRONISM": ("মালিক হওয়ার আগেই দলিল সম্পাদন", "Executed before the seller owned the land"),
    "PENDING_CASE": ("জমিতে চলমান মামলা", "Pending case on the plot"),
    "RAPID_FLIP": ("দ্রুত হাতবদল", "Rapid flipping"),
    "OVERSELL": ("মালিকানার চেয়ে বেশি বিক্রি", "Selling more than ever owned"),
    "PENDING_MUTATION": ("পূর্বের নামজারি অমীমাংসিত (তথ্য)", "Earlier mutation still pending (info)"),
    "RING_LINK": ("সন্দেহভাজন চক্রের সংশ্লিষ্টতা", "Linked to a suspect ring"),
    "MUTATION_WITHOUT_DEED": ("দলিল ছাড়া নামজারি আবেদন", "Mutation application with no deed"),
    "MUTATION_AREA_EXCEEDS_DEED": ("দলিলের চেয়ে বেশি জমির নামজারি", "Mutation larger than the deed"),
}

DECISION_BN = {"BLOCK": "নিবন্ধন স্থগিত", "HOLD": "যাচাইয়ের জন্য আটকানো", "CLEAR": "অগ্রসর করা যায়"}
DECISION_EN = {"BLOCK": "Block registration", "HOLD": "Hold for review", "CLEAR": "Clear to proceed"}
ACTION_BN = {
    "BLOCK": "সাব-রেজিস্ট্রার ও এসি (ল্যান্ড) যৌথভাবে কাগজপত্র ও সরেজমিন যাচাই না করা পর্যন্ত নিবন্ধন স্থগিত রাখুন।",
    "HOLD": "অতিরিক্ত কাগজপত্র চেয়ে নিয়ে যাচাই করুন; যাচাই শেষে নিবন্ধন করুন বা বাতিল করুন।",
    "CLEAR": "কোনো উল্লেখযোগ্য অসঙ্গতি পাওয়া যায়নি; স্বাভাবিক প্রক্রিয়ায় এগোন।",
}
ACTION_EN = {
    "BLOCK": "Keep registration on hold until the Sub-Registrar and AC (Land) have jointly checked the papers and the site.",
    "HOLD": "Ask for additional documents and verify; then register or reject after review.",
    "CLEAR": "No significant inconsistency found; proceed normally.",
}
DISCLAIMER_BN = "এটি সিদ্ধান্ত-সহায়ক টুল; মালিকানা নির্ধারণ করে না। চূড়ান্ত সিদ্ধান্ত কর্মকর্তার।"
DISCLAIMER_EN = "Decision support only; it does not determine ownership. The final decision rests with the officer."


def _num(x) -> str:
    return f"{float(x):.2f}".rstrip("0").rstrip(".")


def bn(x) -> str:
    """A number in Bangla digits."""
    return bn_num(_num(x))


def bnd(text) -> str:
    """Any text (dates, ids with digits) in Bangla digits."""
    return bn_num(str(text))


# ---- one template per alert code: evidence -> (bangla, english) -------------

def _double_sale(e):
    prior = e.get("prior_sales") or []
    last = prior[-1] if prior else None
    who_bn = f" (দলিল {last['deed_id']}, {bnd(last['reg_date'])}, ক্রেতা: {last['buyer_name']})" if last else ""
    who_en = f" (deed {last['deed_id']}, {last['reg_date']}, buyer: {last['buyer_name']})" if last else ""
    b = (f"বিক্রেতা এই দাগের {bn(e['already_sold'])} শতাংশ আগেই বিক্রি করেছেন{who_bn}। "
         f"সাব-রেজিস্ট্রি রেকর্ডে এখন তাঁর হাতে {bn(e['remaining_in_registry'])} শতাংশ আছে, "
         f"অথচ এই দলিলে {bn(e['requested'])} শতাংশ বিক্রির প্রস্তাব।")
    en = (f"The seller already sold {_num(e['already_sold'])} decimals of this plot{who_en}. "
          f"The registry shows {_num(e['remaining_in_registry'])} decimals left, "
          f"but this deed offers {_num(e['requested'])}.")
    if e.get("hidden_from_ac_land"):
        b += (f" আগের বিক্রির নামজারি এখনো না হওয়ায় এসি (ল্যান্ড) খতিয়ানে বিক্রেতার নামে "
              f"{bn(e['ac_land_still_shows'])} শতাংশ দেখাচ্ছে; শুধু খতিয়ান দেখলে এটি ধরা পড়ত না।")
        en += (f" Because the earlier sale is not yet mutated, the AC Land khatian still shows "
               f"{_num(e['ac_land_still_shows'])} decimals in the seller's name; a khatian-only check would miss this.")
    return b, en


def _impersonation(e):
    b = (f"বিক্রেতার নাম ({e['seller_name']}, পিতা: {e['seller_father']}) রেকর্ডে থাকা মালিক "
         f"{e['owner_name']} (পিতা: {e['owner_father']}) এর সঙ্গে প্রায় হুবহু মেলে "
         f"(নাম {bn(e['name_similarity'] * 100)}%, পিতার নাম {bn(e['father_similarity'] * 100)}%) "
         f"কিন্তু পরিচয় টোকেন ভিন্ন। প্রকৃত মালিকের হাতে এখনো {bn(e['owner_holding'])} শতাংশ আছে।")
    en = (f"The seller's name ({e['seller_name']}, father {e['seller_father']}) nearly matches the recorded owner "
          f"{e['owner_name']} (father {e['owner_father']}) — name {e['name_similarity'] * 100:.0f}%, "
          f"father's name {e['father_similarity'] * 100:.0f}% — but the identity token is different. "
          f"The real owner still holds {_num(e['owner_holding'])} decimals.")
    return b, en


def _chain_break(e):
    owners = e.get("recorded_owners") or []
    lst_bn = ", ".join(f"{o['name']} ({bn(o['area'])} শতাংশ)" for o in owners[:3]) or "—"
    lst_en = ", ".join(f"{o['name']} ({_num(o['area'])} dec)" for o in owners[:3]) or "—"
    return (f"বিক্রেতা {e['seller_name']} এই দাগের খতিয়ানে বা কোনো পূর্ববর্তী দলিলে মালিক হিসেবে নেই। "
            f"রেকর্ডে থাকা মালিক: {lst_bn}।",
            f"Seller {e['seller_name']} appears neither in the khatian nor in any earlier deed for this plot. "
            f"Recorded holders: {lst_en}.")


def _oversell(e):
    return (f"বিক্রেতা এই দাগে সর্বমোট {bn(e['ever_acquired'])} শতাংশের মালিক হয়েছিলেন, "
            f"কিন্তু দলিলে {bn(e['requested'])} শতাংশ ({bn(e['excess_pct'])}% বেশি) বিক্রির কথা আছে।",
            f"The seller only ever acquired {_num(e['ever_acquired'])} decimals of this plot, "
            f"but the deed sells {_num(e['requested'])} ({e['excess_pct']:.1f}% more).")


def _flip(e):
    sh_bn = " একই দালাল বা দলিল লেখক একাধিক দলিলে আছেন।" if e.get("shared_intermediary") else ""
    sh_en = " The same broker or deed writer appears on more than one of these deeds." if e.get("shared_intermediary") else ""
    return (f"{bn(e['window_days'])} দিনের মধ্যে এই দাগে {bn(e['transfers_in_window'])}টি হস্তান্তর "
            f"({', '.join(e['deeds'])}).{sh_bn}",
            f"{e['transfers_in_window']} transfers of this plot within {e['window_days']} days "
            f"({', '.join(e['deeds'])}).{sh_en}")


TEMPLATES = {
    "KHAS_ACQUIRED": lambda e: (
        f"এই দাগ সরকারি {('খাস' if e['land_class'] == 'khas' else 'অধিগৃহীত')} জমি হিসেবে রেকর্ডভুক্ত; ব্যক্তিগত বিক্রি বৈধ নয়।",
        f"This plot is recorded as {e['land_class']} (state) land; a private sale is not valid."),
    "DOUBLE_SALE": _double_sale,
    "IMPERSONATION": _impersonation,
    "AREA_EXCEEDS_PARCEL": lambda e: (
        f"দলিলে {bn(e['requested'])} শতাংশ লেখা, অথচ পুরো দাগটিই {bn(e['parcel_total'])} শতাংশ।",
        f"The deed states {_num(e['requested'])} decimals, but the whole plot is {_num(e['parcel_total'])}."),
    "CHAIN_BREAK": _chain_break,
    "ANACHRONISM": lambda e: (
        f"দলিল সম্পাদনের তারিখ {bnd(e['exec_date'])}, কিন্তু বিক্রেতা জমির মালিক হয়েছেন {bnd(e['seller_acquired_on'])} "
        f"তারিখে ({bn(e['days_before'])} দিন পরে)।",
        f"The deed was executed on {e['exec_date']} but the seller acquired the land on "
        f"{e['seller_acquired_on']} ({e['days_before']} days later)."),
    "PENDING_CASE": lambda e: (
        f"এই দাগে {bnd(e['case_filed'])} তারিখে মামলা হয়েছে; দলিল নিবন্ধনের সময় ({bn(e['days_since_filing'])} দিন পর) মামলা চলমান।",
        f"A case was filed on this plot on {e['case_filed']}; it was still pending at registration "
        f"({e['days_since_filing']} days later)."),
    "RAPID_FLIP": _flip,
    "OVERSELL": _oversell,
    "PENDING_MUTATION": lambda e: (
        f"বিক্রেতার কেনা জমির নামজারি এখনো বাকি: রেজিস্ট্রিতে {bn(e['registry_holding'])} শতাংশ, "
        f"খতিয়ানে {bn(e['ac_land_shows'])} শতাংশ। এটি স্বাভাবিক বিলম্ব হতে পারে; শুধু তথ্য হিসেবে দেখানো হলো।",
        f"The seller's own purchase is not yet mutated: registry {_num(e['registry_holding'])} decimals, "
        f"khatian {_num(e['ac_land_shows'])}. This can be ordinary delay; shown for information only."),
    "RING_LINK": lambda e: (
        "এই দলিলে " + ", ".join(f"{ROLE_BN.get(s['role'], s['role'])} {s['name']}" for s in e["suspects"])
        + " আছেন, যাঁরা একাধিক দাগের স্থগিত দলিলে বারবার এসেছেন। "
        + {"escalated_to_block": "এ কারণে সতর্কতা স্থগিতে উন্নীত হয়েছে।",
           "watchlist_only": "শুধু নজরদারির তালিকায় রাখা হলো, আটকানো হয়নি।",
           "corroborates": "এটি অন্যান্য সতর্কতাকে সমর্থন করে।"}[e["effect"]],
        "This deed involves " + ", ".join(f"{ROLE_EN.get(s['role'], s['role'])} {s['name']}" for s in e["suspects"])
        + ", who keep appearing on blocked deeds across plots. "
        + {"escalated_to_block": "This raised the alert to a block.",
           "watchlist_only": "Added to the watch list only; not held.",
           "corroborates": "This corroborates the other alerts."}[e["effect"]]),
    "MUTATION_WITHOUT_DEED": lambda e: (
        f"আবেদনকারী {e['applicant_name']} {bn(e['claimed_area'])} শতাংশের নামজারি চেয়েছেন, "
        f"কিন্তু তাঁর নামে এই দাগে কোনো নিবন্ধিত দলিল সাব-রেজিস্ট্রি খাতায় নেই।",
        f"Applicant {e['applicant_name']} asks to mutate {_num(e['claimed_area'])} decimals, "
        f"but the sub-registry ledger has no registered deed in their name for this plot."),
    "MUTATION_AREA_EXCEEDS_DEED": lambda e: (
        f"নামজারিতে {bn(e['claimed_area'])} শতাংশ চাওয়া হয়েছে, কিন্তু নিবন্ধিত দলিলে {bn(e['deed_area'])} শতাংশ ({bn(e['excess_pct'])}% কম)।",
        f"Mutation asks for {_num(e['claimed_area'])} decimals but the registered deed covers {_num(e['deed_area'])} "
        f"({e['excess_pct']:.1f}% less)."),
}


def explain_alerts(alerts) -> list:
    """Alert objects -> dicts with Bangla and English titles and sentences."""
    out = []
    for a in alerts:
        title = TITLES.get(a.code, (a.code, a.code))
        tpl = TEMPLATES.get(a.code)
        text_bn, text_en = tpl(a.evidence) if tpl else ("", "")
        out.append({"code": a.code, "severity": a.severity,
                    "title_bn": title[0], "title_en": title[1],
                    "text_bn": text_bn, "text_en": text_en, "evidence": a.evidence})
    return out


# ---- the investigation: a fixed sequence of tool calls ----------------------

def investigate(world, deed, result, key) -> dict:
    """Run the tools, build the note. `result` is the GateResult for `deed`."""
    state = world.state
    steps = []

    hist = state.deeds_before(deed.parcel_id, key)
    steps.append({"tool": "get_registry_history", "args": {"parcel_id": deed.parcel_id},
                  "summary_bn": f"সাব-রেজিস্ট্রি খাতায় এই দাগে আগের {bn(len(hist))}টি দলিল পাওয়া গেছে",
                  "summary_en": f"{len(hist)} earlier deed(s) found in the sub-registry ledger for this plot"})

    ac = state.ac_view(deed.parcel_id, deed.reg_date)
    steps.append({"tool": "get_ac_land_record", "args": {"parcel_id": deed.parcel_id, "on": deed.reg_date.isoformat()},
                  "summary_bn": f"এসি (ল্যান্ড) খতিয়ানে {bn(len(ac))} জন মালিক দেখাচ্ছে",
                  "summary_en": f"AC Land khatian shows {len(ac)} holder(s) on that date"})

    n_real = sum(1 for a in result.alerts if a.code not in ("PENDING_MUTATION",))
    steps.append({"tool": "run_detectors", "args": {"deed_id": deed.deed_id},
                  "summary_bn": f"নির্ধারিত নিয়মগুলো চালানো হয়েছে; {bn(n_real)}টি সতর্কতা",
                  "summary_en": f"deterministic rules run; {n_real} alert(s)"})

    hits = [a for a in result.alerts if a.code == "RING_LINK"]
    steps.append({"tool": "check_intermediary_ring", "args": {"intermediaries": len(deed.intermediaries())},
                  "summary_bn": "দালাল/লেখক/সাক্ষীর সঙ্গে সন্দেহভাজন চক্রের সংযোগ পাওয়া গেছে" if hits
                  else "সন্দেহভাজন চক্রের সঙ্গে সংযোগ পাওয়া যায়নি",
                  "summary_en": "link to a suspect ring found" if hits else "no link to a suspect ring"})

    alerts = explain_alerts(result.alerts)
    dec = result.decision
    lines_bn = [f"সিদ্ধান্ত: {DECISION_BN[dec]} (ঝুঁকি স্কোর {bn(result.score)}/১০০)"]
    lines_en = [f"Decision: {DECISION_EN[dec]} (risk score {result.score}/100)"]
    for a in alerts:
        lines_bn.append(f"• {a['title_bn']}: {a['text_bn']}")
        lines_en.append(f"• {a['title_en']}: {a['text_en']}")
    lines_bn += ["", "করণীয়: " + ACTION_BN[dec], DISCLAIMER_BN]
    lines_en += ["", "Next step: " + ACTION_EN[dec], DISCLAIMER_EN]
    note_bn, note_en = "\n".join(lines_bn), "\n".join(lines_en)

    source, polished = "template", None
    if dec != "CLEAR":
        polished = polish_with_llm(note_bn)
    if polished:
        note_bn, source = polished, "llm"
    steps.append({"tool": "draft_case_note", "args": {"language": "bn"},
                  "summary_bn": "টেমপ্লেট থেকে নোট লেখা হয়েছে" if source == "template" else "এলএলএম দিয়ে ভাষা পরিমার্জিত",
                  "summary_en": "note written from templates" if source == "template" else "wording polished by an LLM"})

    return {"alerts": alerts, "steps": steps, "note_bn": note_bn, "note_en": note_en, "note_source": source}


# ---- optional LLM polish (off unless ANTHROPIC_API_KEY is set) -------------

def polish_with_llm(note_bn: str, timeout: float = 15.0):
    """Ask an LLM to smooth the Bangla wording. Returns None on any problem.

    Not exercised by the tests or the default demo (needs a key and internet).
    The prompt forbids adding or changing facts; the structured alerts shown
    next to the note are the source of truth either way.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    body = json.dumps({
        "model": os.environ.get("LLM_MODEL", "claude-haiku-5-5"),
        "max_tokens": 900,
        "messages": [{"role": "user", "content":
                      "নিচের সরকারি কেস-নোটের বাংলা ভাষা সহজ ও স্পষ্ট করুন। কোনো সংখ্যা, নাম, তারিখ বা তথ্য "
                      "যোগ, বাদ বা পরিবর্তন করবেন না। কাঠামো ও বুলেট একই রাখুন। শুধু নোটটি ফেরত দিন।\n\n" + note_bn}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        # guard: every digit-run in the original must survive the polish
        import re
        if text and set(re.findall(r"[০-৯]+", note_bn)) <= set(re.findall(r"[০-৯]+", text)):
            return text
    except Exception:
        pass
    return None

"""Evaluation on synthetic data with known fraud labels.

READ THIS BEFORE QUOTING ANY NUMBER:
These numbers come from synthetic data whose fraud patterns and rates were
chosen by us. They show that the mechanism works and how it behaves, not how
accurate it would be on real Bangladeshi records. In particular the baseline's
weakness on double-sales depends directly on the assumed share of double-sales
made inside the mutation-lag window (see the sensitivity table).

The comparison baseline is an "owner-of-record" check against the AC Land
(mutation) view only: a modelling choice, not a measurement of any live system.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

from .gate import check_deed, check_mutation
from .generator import FRAUD_TYPES, generate
from .rings import apply_escalation, find_suspects

# alert codes that count as "correctly explained" for each injected fraud type
ACCEPT = {
    "DOUBLE_SALE": {"DOUBLE_SALE"},
    "CHAIN_BREAK": {"CHAIN_BREAK", "IMPERSONATION"},
    "IMPERSONATION": {"IMPERSONATION", "CHAIN_BREAK"},
    "OVERSELL": {"OVERSELL", "AREA_EXCEEDS_PARCEL"},
    "ANACHRONISM": {"ANACHRONISM"},
    "RAPID_FLIP": {"RAPID_FLIP"},
    "KHAS_LAND_SALE": {"KHAS_ACQUIRED"},
    "PENDING_CASE": {"PENDING_CASE"},
}


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - m) / d, 3), round((c + m) / d, 3)]


def rate(k, n):
    return round(k / n, 3) if n else 0.0


def run_pipeline(state):
    """Stage 1 (rules) then stage 2 (ring escalation). Returns (results, stage1_decisions, suspects)."""
    results = {d.deed_id: check_deed(state, d) for d in state.deeds}
    stage1 = {k: r.decision for k, r in results.items()}
    suspects = find_suspects(state, results)
    for d in state.deeds:
        apply_escalation(state, d, results[d.deed_id], suspects)
    return results, stage1, suspects


def precision_at(tpr: float, fpr: float, prevalence: float) -> float:
    den = tpr * prevalence + fpr * (1 - prevalence)
    return round(tpr * prevalence / den, 3) if den else 0.0


def evaluate(state, sensitivity: bool = True) -> dict:
    results, stage1, suspects = run_pipeline(state)

    # ---- deed gate vs baseline --------------------------------------------
    per_type = {}
    for t in FRAUD_TYPES:
        if t == "MUTATION_MISMATCH":
            continue
        ds = [d for d in state.deeds if d.truth == t]
        n = len(ds)
        alert = sum(1 for d in ds if results[d.deed_id].decision != "CLEAR")
        block = sum(1 for d in ds if results[d.deed_id].decision == "BLOCK")
        expl = sum(1 for d in ds if results[d.deed_id].codes & ACCEPT[t])
        base = sum(1 for d in ds if results[d.deed_id].baseline_flag)
        per_type[t] = {
            "n": n,
            "gate_alert_recall": rate(alert, n), "gate_alert_ci": wilson(alert, n),
            "gate_block_recall": rate(block, n),
            "gate_correctly_explained": rate(expl, n),
            "baseline_recall": rate(base, n), "baseline_ci": wilson(base, n),
        }

    fraud = [d for d in state.deeds if d.truth]
    legit = [d for d in state.deeds if not d.truth]
    f_alert = sum(1 for d in fraud if results[d.deed_id].decision != "CLEAR")
    f_block = sum(1 for d in fraud if results[d.deed_id].decision == "BLOCK")
    f_base = sum(1 for d in fraud if results[d.deed_id].baseline_flag)
    l_alert = sum(1 for d in legit if results[d.deed_id].decision != "CLEAR")
    l_block = sum(1 for d in legit if results[d.deed_id].decision == "BLOCK")
    l_alert1 = sum(1 for d in legit if stage1[d.deed_id] != "CLEAR")
    l_block1 = sum(1 for d in legit if stage1[d.deed_id] == "BLOCK")
    l_base = sum(1 for d in legit if results[d.deed_id].baseline_flag)
    f_block1 = sum(1 for d in fraud if stage1[d.deed_id] == "BLOCK")

    tpr, fpr = rate(f_alert, len(fraud)), rate(l_alert, len(legit))
    btpr, bfpr = rate(f_base, len(fraud)), rate(l_base, len(legit))
    overall = {
        "fraud_deeds": len(fraud), "legit_deeds": len(legit),
        "gate": {
            "alert_recall": tpr, "alert_recall_ci": wilson(f_alert, len(fraud)),
            "block_recall": rate(f_block, len(fraud)),
            "false_alert_rate": fpr, "false_alert_ci": wilson(l_alert, len(legit)),
            "false_block_rate": rate(l_block, len(legit)),
            "measured_precision_alert": rate(f_alert, f_alert + l_alert),
            "measured_block_precision": rate(f_block, f_block + l_block),
            "precision_at_1pct_prevalence": precision_at(tpr, fpr, 0.01),
            "precision_at_3pct_prevalence": precision_at(tpr, fpr, 0.03),
        },
        "baseline": {
            "alert_recall": btpr, "alert_recall_ci": wilson(f_base, len(fraud)),
            "false_alert_rate": bfpr, "false_alert_ci": wilson(l_base, len(legit)),
            "measured_precision_alert": rate(f_base, f_base + l_base),
            "precision_at_1pct_prevalence": precision_at(btpr, bfpr, 0.01),
            "precision_at_3pct_prevalence": precision_at(btpr, bfpr, 0.03),
        },
    }

    ring_effect = {
        "stage1_block_precision": rate(f_block1, f_block1 + l_block1),
        "stage2_block_precision": rate(f_block, f_block + l_block),
        "stage1_block_recall": rate(f_block1, len(fraud)),
        "stage2_block_recall": rate(f_block, len(fraud)),
        "stage1_false_alert_rate": rate(l_alert1, len(legit)),
        "stage2_false_alert_rate": rate(l_alert, len(legit)),
    }

    # ---- lag window analysis (double sale) --------------------------------
    ds = [d for d in state.deeds if d.truth == "DOUBLE_SALE"]
    lag = {}
    for name, flag in (("inside_lag_window", True), ("outside_lag_window", False)):
        sub = [d for d in ds if d.truth_meta.get("in_window") is flag]
        lag[name] = {
            "n": len(sub),
            "gate_recall": rate(sum(1 for d in sub if results[d.deed_id].decision != "CLEAR"), len(sub)),
            "baseline_recall": rate(sum(1 for d in sub if results[d.deed_id].baseline_flag), len(sub)),
        }
    hidden = sum(1 for d in ds if any(a.code == "DOUBLE_SALE" and a.evidence.get("hidden_from_ac_land")
                                      for a in results[d.deed_id].alerts))
    lag["double_sales_hidden_from_ac_land_view"] = {"n": hidden, "of": len(ds)}

    # ---- mutation gate ------------------------------------------------------
    m_fraud = [m for m in state.mutation_apps if m.truth]
    m_legit = [m for m in state.mutation_apps if not m.truth]
    mres = {m.app_id: check_mutation(state, m) for m in state.mutation_apps}
    m_tp = sum(1 for m in m_fraud if mres[m.app_id].decision != "CLEAR")
    m_fp = sum(1 for m in m_legit if mres[m.app_id].decision != "CLEAR")
    mutation = {
        "fraud_apps": len(m_fraud), "legit_apps": len(m_legit),
        "alert_recall": rate(m_tp, len(m_fraud)), "alert_recall_ci": wilson(m_tp, len(m_fraud)),
        "false_alert_rate": rate(m_fp, len(m_legit)),
        "note": "No baseline row: the model assumes AC Land has no live link to the deed ledger.",
    }

    # ---- ring discovery -------------------------------------------------------
    truth_ring = set(state.meta.get("ring_intermediaries", []))
    found = {k[1] for k in suspects}
    ring = {
        "true_ring_members": len(truth_ring),
        "suspects_found": len(found),
        "true_found": len(found & truth_ring),
        "false_suspects": len(found - truth_ring),
        "recall": rate(len(found & truth_ring), len(truth_ring)),
        "precision": rate(len(found & truth_ring), len(found)),
    }

    out = {
        "dataset": {k: state.meta[k] for k in ("seed", "n_parcels", "fraud_share", "in_window_share")}
                   | {"deeds": len(state.deeds), "mutation_apps": len(state.mutation_apps),
                      "injected": state.meta["injected"]},
        "per_type": per_type, "overall": overall, "ring_effect": ring_effect,
        "lag_window": lag, "mutation_gate": mutation, "ring_discovery": ring,
        "caveats": [
            "Synthetic data with fraud patterns and rates chosen by the authors; not real-world accuracy.",
            "Baseline is a modelling choice (owner-of-record check on the AC Land view), not a live system.",
            "Fraud prevalence is stylised for measurement; use the precision-at-prevalence figures for realism.",
            "Inheritance by unrecorded heirs, power-of-attorney deeds and OCR of scanned records are not modelled.",
        ],
    }
    if sensitivity:
        out["sensitivity_in_window_share"] = sensitivity_table()
    return out


def sensitivity_table(shares=(0.25, 0.5, 0.75, 1.0), n_parcels=1500, seed=7):
    rows = []
    for s in shares:
        st = generate(n_parcels=n_parcels, seed=seed, in_window_share=s)
        results = {d.deed_id: check_deed(st, d) for d in st.deeds}
        ds = [d for d in st.deeds if d.truth == "DOUBLE_SALE"]
        g = sum(1 for d in ds if results[d.deed_id].decision != "CLEAR")
        b = sum(1 for d in ds if results[d.deed_id].baseline_flag)
        rows.append({"in_window_share": s, "n": len(ds),
                     "gate_recall": rate(g, len(ds)), "baseline_recall": rate(b, len(ds))})
    return rows


def format_report(r: dict) -> str:
    L = []
    ds = r["dataset"]
    L.append(f"Dataset: {ds['n_parcels']} plots, {ds['deeds']} deeds, seed {ds['seed']} (SYNTHETIC)")
    L.append("")
    L.append(f"{'fraud type':<16}{'n':>4}  {'gate':>6}  {'block':>6}  {'explained':>9}  {'baseline':>8}")
    for t, v in r["per_type"].items():
        L.append(f"{t:<16}{v['n']:>4}  {v['gate_alert_recall']:>6.0%}  {v['gate_block_recall']:>6.0%}  "
                 f"{v['gate_correctly_explained']:>9.0%}  {v['baseline_recall']:>8.0%}")
    o = r["overall"]
    L.append("")
    L.append(f"Overall recall      gate {o['gate']['alert_recall']:.1%}  baseline {o['baseline']['alert_recall']:.1%}")
    L.append(f"False alert rate    gate {o['gate']['false_alert_rate']:.1%}  baseline {o['baseline']['false_alert_rate']:.1%}")
    L.append(f"Precision @1% prev  gate {o['gate']['precision_at_1pct_prevalence']:.1%}  baseline {o['baseline']['precision_at_1pct_prevalence']:.1%}")
    l = r["lag_window"]
    L.append("")
    L.append(f"Double-sale inside lag window: n={l['inside_lag_window']['n']} gate {l['inside_lag_window']['gate_recall']:.0%} baseline {l['inside_lag_window']['baseline_recall']:.0%}")
    L.append(f"Double-sale outside window:    n={l['outside_lag_window']['n']} gate {l['outside_lag_window']['gate_recall']:.0%} baseline {l['outside_lag_window']['baseline_recall']:.0%}")
    m = r["mutation_gate"]
    L.append("")
    L.append(f"Mutation gate: recall {m['alert_recall']:.0%} ({m['fraud_apps']} fraud apps), false alerts {m['false_alert_rate']:.1%}")
    g = r["ring_discovery"]
    L.append(f"Ring discovery: found {g['true_found']}/{g['true_ring_members']} true members, {g['false_suspects']} false suspects")
    e = r["ring_effect"]
    L.append(f"Ring escalation: block precision {e['stage1_block_precision']:.1%} -> {e['stage2_block_precision']:.1%}, "
             f"block recall {e['stage1_block_recall']:.1%} -> {e['stage2_block_recall']:.1%}")
    return "\n".join(L)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    state = generate(n_parcels=n, seed=42)
    res = evaluate(state)
    print(format_report(res))
    print("\nSensitivity (double-sale recall vs assumed in-window share):")
    for row in res["sensitivity_in_window_share"]:
        print(f"  in_window={row['in_window_share']:.2f}  n={row['n']}  gate={row['gate_recall']:.0%}  baseline={row['baseline_recall']:.0%}")
    out = Path(__file__).resolve().parent.parent / "data" / "eval.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"\nwritten: {out}")

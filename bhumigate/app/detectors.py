"""Deterministic, explainable fraud detectors.

Every alert carries machine-readable evidence, so a human officer can see
exactly why a deed was held. There is no black box here, and no LLM: the
language model (see agent.py) only rewrites this evidence into prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .models import GOV, Deed, MutationApp
from .namematch import similarity
from .state import TOL_ABS, TOL_REL, LandState, allowed

FLIP_WINDOW_DAYS = 14
FLIP_MIN_TRANSFERS = 3
NAME_SIM = 0.85
FATHER_SIM = 0.80

# severity of each alert (0-100); decision thresholds live in scoring.py
SEV = {
    "KHAS_ACQUIRED": 95,
    "DOUBLE_SALE": 92,
    "IMPERSONATION": 90,
    "AREA_EXCEEDS_PARCEL": 90,
    "CHAIN_BREAK": 85,
    "ANACHRONISM": 80,
    "PENDING_CASE": 60,
    "RAPID_FLIP": 55,
    "PENDING_MUTATION": 10,   # informational only
}


@dataclass
class Alert:
    code: str
    severity: int
    evidence: dict = field(default_factory=dict)

    def to_dict(self):
        return {"code": self.code, "severity": self.severity, "evidence": self.evidence}


def _deed_ref(state: LandState, d: Deed) -> dict:
    return {
        "deed_id": d.deed_id,
        "seller": d.seller,
        "seller_name": state.name(d.seller),
        "buyer": d.buyer,
        "buyer_name": state.name(d.buyer),
        "area": round(d.area, 2),
        "reg_date": d.reg_date.isoformat(),
        "mut_status": d.mut_status,
        "mut_date": d.mut_date.isoformat() if d.mut_date else None,
    }


def deed_key(deed: Deed) -> tuple:
    return (deed.reg_date, deed.seq)


def baseline_flag(state: LandState, deed: Deed, key=None) -> bool:
    """What an owner-of-record check against the AC Land (mutation) view alone would flag.

    This is a modelling choice used only as the comparison baseline in the
    evaluation: it knows the khatian, the khas/pending-case flags and the NID
    token of the recorded owner, but it cannot see deeds that are registered
    and not yet mutated.
    """
    parcel = state.parcels[deed.parcel_id]
    if parcel.land_class != "private":
        return True
    if parcel.case_filed and parcel.case_filed <= deed.reg_date:
        return True
    ac = state.ac_view(deed.parcel_id, deed.reg_date)
    h_ac = ac.get(deed.seller, 0.0)
    if h_ac <= 0:
        return True
    if deed.area > allowed(h_ac):
        return True
    if deed.area > allowed(parcel.total_area):
        return True
    return False


def run_deed_detectors(state: LandState, deed: Deed, key=None):
    """Run all detectors on a deed. Returns (alerts, context)."""
    key = key or deed_key(deed)
    parcel = state.parcels[deed.parcel_id]
    tv = state.title_replay(deed.parcel_id, key)
    ac = state.ac_view(deed.parcel_id, deed.reg_date)

    seller = deed.seller
    h_reg = tv.holdings.get(seller, 0.0)
    acquired = tv.acquired.get(seller, 0.0)
    h_ac = ac.get(seller, 0.0)

    alerts: list[Alert] = []

    # 1. khas / acquired land can't be sold by a private person
    if parcel.land_class != "private":
        alerts.append(Alert("KHAS_ACQUIRED", SEV["KHAS_ACQUIRED"], {
            "land_class": parcel.land_class,
        }))

    # 2. title checks on the seller
    if acquired <= 0:
        best = None
        for pid in tv.acquired:
            if pid == GOV or pid == seller:
                continue
            ns = similarity(state.name(seller), state.name(pid))
            fs = similarity(state.father(seller), state.father(pid))
            if best is None or (ns + fs) > (best[1] + best[2]):
                best = (pid, ns, fs)
        if best and best[1] >= NAME_SIM and best[2] >= FATHER_SIM:
            alerts.append(Alert("IMPERSONATION", SEV["IMPERSONATION"], {
                "seller_name": state.name(seller),
                "seller_father": state.father(seller),
                "owner": best[0],
                "owner_name": state.name(best[0]),
                "owner_father": state.father(best[0]),
                "name_similarity": round(best[1], 2),
                "father_similarity": round(best[2], 2),
                "owner_holding": round(tv.holdings.get(best[0], 0.0), 2),
            }))
        else:
            alerts.append(Alert("CHAIN_BREAK", SEV["CHAIN_BREAK"], {
                "seller_name": state.name(seller),
                "recorded_owners": [
                    {"pid": p, "name": state.name(p), "area": round(a, 2)}
                    for p, a in tv.holdings.items() if a > 0
                ],
            }))
    elif deed.area > allowed(acquired):
        excess = deed.area / acquired - 1
        alerts.append(Alert("OVERSELL", int(min(95, 60 + excess * 100)), {
            "requested": round(deed.area, 2),
            "ever_acquired": round(acquired, 2),
            "excess_pct": round(excess * 100, 1),
        }))
    elif deed.area > allowed(h_reg):
        prior = [_deed_ref(state, d) for d in tv.sales.get(seller, [])]
        alerts.append(Alert("DOUBLE_SALE", SEV["DOUBLE_SALE"], {
            "requested": round(deed.area, 2),
            "remaining_in_registry": round(h_reg, 2),
            "already_sold": round(tv.sold.get(seller, 0.0), 2),
            "prior_sales": prior,
            "ac_land_still_shows": round(h_ac, 2),
            "hidden_from_ac_land": h_ac > 0 and deed.area <= allowed(h_ac),
        }))

    # 3. deed larger than the whole plot
    if deed.area > allowed(parcel.total_area):
        alerts.append(Alert("AREA_EXCEEDS_PARCEL", SEV["AREA_EXCEEDS_PARCEL"], {
            "requested": round(deed.area, 2),
            "parcel_total": round(parcel.total_area, 2),
        }))

    # 4. executed before the seller owned the land
    if acquired > 0 and seller in tv.acq_date and deed.exec_date < tv.acq_date[seller]:
        alerts.append(Alert("ANACHRONISM", SEV["ANACHRONISM"], {
            "exec_date": deed.exec_date.isoformat(),
            "seller_acquired_on": tv.acq_date[seller].isoformat(),
            "days_before": (tv.acq_date[seller] - deed.exec_date).days,
        }))

    # 5. rapid successive transfers on the same plot
    recent = [d for d in state.deeds_before(deed.parcel_id, key)
              if 0 <= (deed.reg_date - d.reg_date).days <= FLIP_WINDOW_DAYS]
    chain = recent + [deed]
    if len(chain) >= FLIP_MIN_TRANSFERS:
        brokers = [d.broker for d in chain if d.broker]
        writers = [d.writer for d in chain if d.writer]
        shared = (len(set(brokers)) < len(brokers)) or (len(set(writers)) < len(writers))
        alerts.append(Alert("RAPID_FLIP", SEV["RAPID_FLIP"] + (15 if shared else 0), {
            "transfers_in_window": len(chain),
            "window_days": FLIP_WINDOW_DAYS,
            "deeds": [d.deed_id for d in chain],
            "shared_intermediary": shared,
        }))

    # 6. transfer while a case is pending on the plot
    if parcel.case_filed and parcel.case_filed <= deed.reg_date:
        alerts.append(Alert("PENDING_CASE", SEV["PENDING_CASE"], {
            "case_filed": parcel.case_filed.isoformat(),
            "days_since_filing": (deed.reg_date - parcel.case_filed).days,
        }))

    # 7. informational: seller's own purchase is registered but not yet mutated
    if acquired > 0 and h_reg > 0 and h_ac + TOL_ABS < h_reg * (1 - TOL_REL):
        pending = [_deed_ref(state, d) for d in tv.acq_deeds.get(seller, [])
                   if d.mut_status != "applied" or (d.mut_date and d.mut_date > deed.reg_date)]
        if pending:
            alerts.append(Alert("PENDING_MUTATION", SEV["PENDING_MUTATION"], {
                "registry_holding": round(h_reg, 2),
                "ac_land_shows": round(h_ac, 2),
                "pending_deeds": pending,
            }))

    alerts.sort(key=lambda a: -a.severity)
    context = {
        "parcel_total": round(parcel.total_area, 2),
        "land_class": parcel.land_class,
        "seller_registry_holding": round(h_reg, 2),
        "seller_ac_land_holding": round(h_ac, 2),
        "seller_ever_acquired": round(acquired, 2),
        "registry_view": {p: round(a, 2) for p, a in tv.holdings.items() if a > 1e-9},
        "ac_land_view": ac,
    }
    return alerts, context


def run_mutation_detectors(state: LandState, app: MutationApp):
    """Cross-check a mutation application against the sub-registry deed ledger."""
    alerts: list[Alert] = []
    deeds = [d for d in state.deeds_up_to(app.parcel_id, app.applied_date) if d.buyer == app.applicant]
    if not deeds:
        alerts.append(Alert("MUTATION_WITHOUT_DEED", 90, {
            "applicant": app.applicant,
            "applicant_name": state.name(app.applicant),
            "claimed_area": round(app.area, 2),
            "registered_deeds_to_applicant": 0,
        }))
    else:
        total = sum(d.area for d in deeds)
        if app.area > allowed(total):
            alerts.append(Alert("MUTATION_AREA_EXCEEDS_DEED", 80, {
                "claimed_area": round(app.area, 2),
                "deed_area": round(total, 2),
                "excess_pct": round((app.area / total - 1) * 100, 1),
                "deeds": [d.deed_id for d in deeds],
            }))
    alerts.sort(key=lambda a: -a.severity)
    return alerts

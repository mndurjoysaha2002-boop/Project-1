"""World state: parcels, people, the sub-registry deed ledger and the AC Land mutation record.

Two separate views of "who owns what" are kept on purpose, because that split
(sub-registry under the Law Ministry, AC Land under the Land Ministry) is the
gap that double-selling exploits:

* registry view  - replay of the root khatian + every deed registered so far.
* AC Land view   - root khatian + only those mutations AC Land has approved so far.
                   It lags the registry view by the mutation delay.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .models import GOV, SURVEY_DATE, Deed, MutationApp, Parcel, Person

TOL_REL = 0.01   # 1% relative tolerance on areas (rounding / unit conversion)
TOL_ABS = 0.05   # 0.05 decimal absolute tolerance


def allowed(area: float) -> float:
    """Largest area that is acceptable for a recorded holding of `area`."""
    return area * (1 + TOL_REL) + TOL_ABS


@dataclass
class TitleView:
    holdings: dict = field(default_factory=dict)    # pid -> area currently held
    acquired: dict = field(default_factory=dict)    # pid -> total area ever acquired
    sold: dict = field(default_factory=dict)        # pid -> total area sold
    acq_date: dict = field(default_factory=dict)    # pid -> date of first acquisition
    sales: dict = field(default_factory=dict)       # pid -> [Deed, ...] sold by pid
    acq_deeds: dict = field(default_factory=dict)   # pid -> [Deed, ...] acquired by pid


class LandState:
    def __init__(self, parcels, people, deeds, mutation_apps=None, meta=None):
        self.parcels = {p.parcel_id: p for p in parcels}
        self.people = {p.pid: p for p in people}
        self.deeds = sorted(deeds, key=lambda d: (d.reg_date, d.seq))
        self.by_id = {d.deed_id: d for d in self.deeds}
        self.by_parcel = defaultdict(list)
        for d in self.deeds:
            self.by_parcel[d.parcel_id].append(d)
        self.mutation_apps = list(mutation_apps or [])
        self.meta = meta or {}
        self.simulate_mutations()

    # ---- name helpers -------------------------------------------------
    def name(self, pid: str) -> str:
        if pid == GOV:
            return "সরকার (খাস/অধিগৃহীত)"
        p = self.people.get(pid)
        return p.name_bn if p else pid

    def father(self, pid: str) -> str:
        p = self.people.get(pid)
        return p.father_bn if p else ""

    # ---- registry view ------------------------------------------------
    def deeds_before(self, parcel_id: str, key: tuple) -> list:
        """Deeds registered strictly before `key` = (reg_date, seq)."""
        return [d for d in self.by_parcel.get(parcel_id, []) if (d.reg_date, d.seq) < key]

    def title_replay(self, parcel_id: str, key: tuple) -> TitleView:
        parcel = self.parcels[parcel_id]
        tv = TitleView()
        for pid, area in parcel.root_owners:
            tv.holdings[pid] = tv.holdings.get(pid, 0.0) + area
            tv.acquired[pid] = tv.acquired.get(pid, 0.0) + area
            tv.acq_date.setdefault(pid, SURVEY_DATE)
        for d in self.deeds_before(parcel_id, key):
            tv.holdings[d.seller] = max(0.0, tv.holdings.get(d.seller, 0.0) - d.area)
            tv.sold[d.seller] = tv.sold.get(d.seller, 0.0) + d.area
            tv.sales.setdefault(d.seller, []).append(d)
            tv.holdings[d.buyer] = tv.holdings.get(d.buyer, 0.0) + d.area
            tv.acquired[d.buyer] = tv.acquired.get(d.buyer, 0.0) + d.area
            tv.acq_date.setdefault(d.buyer, d.reg_date)
            tv.acq_deeds.setdefault(d.buyer, []).append(d)
        return tv

    # ---- AC Land (mutation) view ---------------------------------------
    def simulate_mutations(self):
        """Decide, per parcel and in order of approval date, which mutations AC Land applies.

        AC Land only sees its own khatian: a mutation is applied if the seller
        holds enough area *in the AC Land record at that moment*, otherwise it
        is recorded as a conflict.
        """
        for pid, deeds in self.by_parcel.items():
            parcel = self.parcels[pid]
            ac = defaultdict(float)
            for owner, area in parcel.root_owners:
                ac[owner] += area
            events = []
            for d in deeds:
                if d.mut_lag is None:
                    d.mut_status, d.mut_date = "none", None
                    continue
                d.mut_date = date.fromordinal(d.reg_date.toordinal() + d.mut_lag)
                events.append(d)
            for d in sorted(events, key=lambda x: (x.mut_date, x.seq)):
                if ac[d.seller] + TOL_ABS >= d.area * (1 - TOL_REL):
                    moved = min(d.area, ac[d.seller])
                    ac[d.seller] -= moved
                    ac[d.buyer] += d.area
                    d.mut_status = "applied"
                else:
                    d.mut_status = "conflict"

    def ac_view(self, parcel_id: str, on: date) -> dict:
        parcel = self.parcels[parcel_id]
        ac = defaultdict(float)
        for owner, area in parcel.root_owners:
            ac[owner] += area
        applied = [d for d in self.by_parcel.get(parcel_id, [])
                   if d.mut_status == "applied" and d.mut_date is not None and d.mut_date <= on]
        for d in sorted(applied, key=lambda x: (x.mut_date, x.seq)):
            moved = min(d.area, ac[d.seller])
            ac[d.seller] -= moved
            ac[d.buyer] += d.area
        return {k: round(v, 4) for k, v in ac.items() if v > 1e-9}

    def deeds_up_to(self, parcel_id: str, on: date) -> list:
        return [d for d in self.by_parcel.get(parcel_id, []) if d.reg_date <= on]

    # ---- copies for tamper demos ----------------------------------------
    def without_deed(self, deed_id: str) -> "LandState":
        """A copy of the state in which one registered deed has been deleted."""
        import copy
        deeds = [copy.copy(d) for d in self.deeds if d.deed_id != deed_id]
        return LandState(list(self.parcels.values()), list(self.people.values()),
                         deeds, self.mutation_apps, self.meta)

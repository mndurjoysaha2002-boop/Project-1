"""Core data model. Everything here is synthetic.

A person is identified by a pseudonymous token (a stand-in for a hashed NID).
The system never stores or needs a real NID number.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

GOV = "GOV"  # the State, as recorded owner of khas / acquired land
SURVEY_DATE = date(2000, 1, 1)  # nominal date of the root survey record


@dataclass
class Person:
    pid: str
    name_bn: str
    father_bn: str = ""
    role: str = "citizen"  # citizen | broker | writer | witness


@dataclass
class Parcel:
    parcel_id: str
    district: str
    upazila: str
    mouza: str
    survey: str          # CS | SA | RS | BS
    khatian_no: str
    dag_no: str
    total_area: float    # decimals
    land_class: str = "private"   # private | khas | acquired
    case_filed: Optional[date] = None
    root_owners: list = field(default_factory=list)  # [(pid, area_decimals)]


@dataclass
class Deed:
    deed_id: str
    parcel_id: str
    deed_type: str       # sale | hiba
    seller: str
    buyer: str
    area: float          # decimals, as declared in the deed
    exec_date: date
    reg_date: date
    sub_registry: str = ""
    broker: str = ""
    writer: str = ""
    witnesses: list = field(default_factory=list)
    seq: int = 0
    # mutation (AC Land) side, filled by the mutation simulation
    mut_lag: Optional[int] = None     # days until mutation approved; None = never filed
    mut_status: str = "none"          # none | applied | conflict
    mut_date: Optional[date] = None
    # ground truth, used only by the evaluation (never read by the detectors)
    truth: Optional[str] = None
    truth_meta: dict = field(default_factory=dict)

    def payload(self) -> dict:
        """Canonical fields that the registry seals (hashes + signs)."""
        return {
            "deed_id": self.deed_id,
            "parcel_id": self.parcel_id,
            "deed_type": self.deed_type,
            "seller": self.seller,
            "buyer": self.buyer,
            "area": f"{self.area:.4f}",
            "exec_date": self.exec_date.isoformat(),
            "reg_date": self.reg_date.isoformat(),
            "sub_registry": self.sub_registry,
            "broker": self.broker,
            "writer": self.writer,
            "witnesses": list(self.witnesses),
        }

    def intermediaries(self) -> list:
        out = []
        if self.broker:
            out.append(("broker", self.broker))
        if self.writer:
            out.append(("writer", self.writer))
        out.extend(("witness", w) for w in self.witnesses if w)
        return out


@dataclass
class MutationApp:
    app_id: str
    parcel_id: str
    applicant: str
    area: float
    applied_date: date
    deed_id: Optional[str] = None  # deed the applicant cites
    truth: Optional[str] = None
    truth_meta: dict = field(default_factory=dict)


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

"""Service layer: everything the dashboard and API need, as plain Python functions.

No web framework in here, so it is easy to test and to wrap in FastAPI, Flask
or anything else later. All data is synthetic (see generator.py).
"""

from __future__ import annotations

import copy
import threading
from datetime import date, datetime, timezone

from . import agent
from .detectors import deed_key
from .evaluate import ACCEPT, evaluate, run_pipeline
from .gate import check_deed, check_mutation
from .generator import END, generate
from .ledger import RegistryLedger
from .models import GOV, Deed
from .rings import apply_escalation, build_graph, clusters
from .units import UNIT_BN, to_decimal

DEFAULT_PARCELS = 3000
DEFAULT_SEED = 42
DRAFT_SEQ = 10 ** 9          # a brand-new deed is registered after every existing one
MAX_TEXT = 64


class World:
    def __init__(self, n_parcels: int = DEFAULT_PARCELS, seed: int = DEFAULT_SEED):
        self.state = generate(n_parcels=n_parcels, seed=seed)
        self.results, self.stage1, self.suspects = run_pipeline(self.state)
        self.graph = build_graph(self.state, self.results, self.suspects)
        self.clusters = clusters(self.state, self.graph, self.suspects)
        self.mut_results = {m.app_id: check_mutation(self.state, m) for m in self.state.mutation_apps}
        self.ledger = RegistryLedger()
        for d in self.state.deeds:           # state.deeds is already sorted by registration order
            self.ledger.append(d.deed_id, d.payload())
        self.ledger_status = self.ledger.verify()
        self.officer: dict = {}              # deed_id -> latest officer decision
        self.audit: list = []                # append-only log of officer decisions
        self._eval = None
        self._lock = threading.Lock()

    # ---- small helpers --------------------------------------------------
    def person(self, pid: str) -> dict:
        return {"pid": pid, "name": self.state.name(pid)}

    def deed_dict(self, d: Deed) -> dict:
        s = self.state
        return {
            "deed_id": d.deed_id, "parcel_id": d.parcel_id, "deed_type": d.deed_type,
            "seller": d.seller, "seller_name": s.name(d.seller), "seller_father": s.father(d.seller),
            "buyer": d.buyer, "buyer_name": s.name(d.buyer),
            "area": d.area, "exec_date": d.exec_date.isoformat(), "reg_date": d.reg_date.isoformat(),
            "sub_registry": d.sub_registry,
            "broker": d.broker, "broker_name": s.name(d.broker) if d.broker else "",
            "writer": d.writer, "writer_name": s.name(d.writer) if d.writer else "",
            "witnesses": list(d.witnesses), "witness_names": [s.name(w) for w in d.witnesses],
            "mut_status": d.mut_status, "mut_date": d.mut_date.isoformat() if d.mut_date else None,
            "synthetic_label": d.truth,   # ground truth of the synthetic data; shown in demo only
        }

    def _holders(self, view: dict) -> list:
        return [{"pid": p, "name": self.state.name(p), "area": round(a, 2)}
                for p, a in sorted(view.items(), key=lambda kv: -kv[1]) if a > 1e-9]

    # ---- summary ---------------------------------------------------------
    def summary(self) -> dict:
        counts = {"BLOCK": 0, "HOLD": 0, "CLEAR": 0}
        codes: dict = {}
        watch = 0
        for r in self.results.values():
            counts[r.decision] += 1
            if r.decision == "CLEAR" and "RING_LINK" in r.codes:
                watch += 1
            for c in r.codes - {"PENDING_MUTATION", "RING_LINK"}:
                codes[c] = codes.get(c, 0) + 1
        m_flagged = sum(1 for r in self.mut_results.values() if r.decision != "CLEAR")
        meta = self.state.meta
        return {
            "synthetic": True,
            "parcels": len(self.state.parcels), "deeds": len(self.state.deeds),
            "mutation_apps": len(self.state.mutation_apps), "people": len(self.state.people),
            "decisions": counts, "alert_codes": dict(sorted(codes.items(), key=lambda kv: -kv[1])),
            "mutation_flagged": m_flagged, "watchlist": watch,
            "ring_suspects": len(self.suspects),
            "ledger": {"entries": len(self.ledger.entries), "ok": self.ledger_status["ok"],
                       "head": self.ledger_status.get("head", "")},
            "seed": meta["seed"], "fraud_share": meta["fraud_share"], "in_window_share": meta["in_window_share"],
        }

    def evaluation(self) -> dict:
        with self._lock:
            if self._eval is None:
                self._eval = evaluate(self.state)
            return self._eval

    # ---- queue -------------------------------------------------------------
    def queue(self, decision: str = "", code: str = "", q: str = "", limit: int = 40, offset: int = 0) -> dict:
        rows = []
        for d in self.state.deeds:
            r = self.results[d.deed_id]
            if r.decision == "CLEAR":
                continue
            if decision and r.decision != decision:
                continue
            if code and code not in r.codes:
                continue
            if q and q.lower() not in (d.deed_id + d.parcel_id + self.state.name(d.seller)
                                       + self.state.name(d.buyer)).lower():
                continue
            rows.append((r.score, d, r))
        rows.sort(key=lambda t: (-t[0], t[1].deed_id))
        total = len(rows)
        out = []
        for score, d, r in rows[offset: offset + limit]:
            out.append({
                "deed_id": d.deed_id, "parcel_id": d.parcel_id, "reg_date": d.reg_date.isoformat(),
                "seller_name": self.state.name(d.seller), "buyer_name": self.state.name(d.buyer),
                "area": d.area, "decision": r.decision, "score": score,
                "codes": sorted(r.codes - {"PENDING_MUTATION"}),
                "officer": self.officer.get(d.deed_id, {}).get("action"),
                "synthetic_label": d.truth,
            })
        return {"total": total, "rows": out}

    # ---- one deed, in full ---------------------------------------------------
    def deed_case(self, deed_id: str) -> dict:
        d = self.state.by_id.get(deed_id)
        if d is None:
            raise KeyError(deed_id)
        r = self.results[deed_id]
        inv = agent.investigate(self, d, r, deed_key(d))
        entry = self.ledger.find(deed_id)
        return self._case_payload(d, r, inv, entry)

    def _case_payload(self, d: Deed, r, inv: dict, entry) -> dict:
        ctx = r.context
        return {
            "deed": self.deed_dict(d),
            "decision": r.decision, "score": r.score, "stage": r.stage,
            "baseline_flag": r.baseline_flag,
            "alerts": inv["alerts"], "steps": inv["steps"],
            "note_bn": inv["note_bn"], "note_en": inv["note_en"], "note_source": inv["note_source"],
            "two_ledgers": {
                "registry": self._holders(ctx["registry_view"]),
                "ac_land": self._holders(ctx["ac_land_view"]),
                "seller_registry": ctx["seller_registry_holding"],
                "seller_ac_land": ctx["seller_ac_land_holding"],
                "parcel_total": ctx["parcel_total"],
            },
            "ledger": ({"index": entry["index"], "entry_hash": entry["entry_hash"],
                        "prev_hash": entry["prev_hash"],
                        "signed_by": ["Sub-Registry", "AC Land"]} if entry else None),
            "officer": self.officer.get(d.deed_id),
        }

    # ---- the gate: check a draft deed -----------------------------------------
    def check_draft(self, body: dict) -> dict:
        s = self.state
        parcel_id = _text(body, "parcel_id")
        if parcel_id not in s.parcels:
            raise ValueError("unknown parcel_id (this prototype only knows its synthetic parcels)")
        seller = _text(body, "seller")
        if not seller:
            raise ValueError("seller is required")
        try:
            area = to_decimal(float(body.get("area", 0)), body.get("unit", "decimal"))
        except (TypeError, ValueError):
            raise ValueError("area must be a number and unit one of: " + ", ".join(UNIT_BN))
        if not (0 < area < 1e6):
            raise ValueError("area must be positive")
        reg = _date(body.get("reg_date"), default=date.fromordinal(END.toordinal() + 1))
        exe = _date(body.get("exec_date"), default=reg)
        deed_type = body.get("deed_type", "sale")
        if deed_type not in ("sale", "hiba"):
            raise ValueError("deed_type must be sale or hiba")
        replay = body.get("replay_of")
        orig = s.by_id.get(replay) if replay else None
        seq = orig.seq if orig else DRAFT_SEQ
        d = Deed(deed_id="DRAFT" if not orig else f"DRAFT-{orig.deed_id}", parcel_id=parcel_id,
                 deed_type=deed_type, seller=seller, buyer=_text(body, "buyer") or "DRAFT-BUYER",
                 area=round(area, 2), exec_date=exe, reg_date=reg,
                 sub_registry=s.parcels[parcel_id].upazila + " সাব-রেজিস্ট্রি অফিস",
                 broker=_text(body, "broker"), writer=_text(body, "writer"),
                 witnesses=[w for w in (body.get("witnesses") or []) if isinstance(w, str)][:4], seq=seq)
        key = (reg, seq)
        r = check_deed(s, d, key)
        apply_escalation(s, d, r, self.suspects)
        inv = agent.investigate(self, d, r, key)
        return self._case_payload(d, r, inv, None)

    # ---- demo scenarios (real synthetic deeds, replayed as drafts) -------------
    def scenarios(self) -> list:
        s, res = self.state, self.results

        def first(pred):
            return next((d for d in s.deeds if pred(d)), None)

        def accepted(d, t):
            r = res[d.deed_id]
            return r.decision != "CLEAR" and bool(r.codes & ACCEPT[t])

        picks = [
            ("clean", "বৈধ সাধারণ বিক্রি", "Ordinary legitimate sale",
             first(lambda d: d.truth is None and res[d.deed_id].decision == "CLEAR" and not res[d.deed_id].alerts
                   and d.mut_status == "applied" and d.deed_type == "sale")),
            ("pending_mutation", "বৈধ পুনঃবিক্রি — আগের নামজারি বাকি", "Legitimate resale, earlier mutation pending",
             first(lambda d: d.truth is None and res[d.deed_id].decision == "CLEAR"
                   and "PENDING_MUTATION" in res[d.deed_id].codes)),
            ("double_sale", "একই জমি দ্বিতীয়বার বিক্রি — নামজারির আগেই", "Double sale before the first is mutated",
             first(lambda d: d.truth == "DOUBLE_SALE" and d.truth_meta.get("in_window") and accepted(d, "DOUBLE_SALE")
                   and any(a.evidence.get("hidden_from_ac_land") for a in res[d.deed_id].alerts if a.code == "DOUBLE_SALE"))),
            ("impersonation", "মালিকের নামের সঙ্গে প্রায় মিল — ছদ্মবেশী বিক্রেতা", "Look-alike seller",
             first(lambda d: d.truth == "IMPERSONATION" and not d.truth_meta.get("strong_variation")
                   and accepted(d, "IMPERSONATION"))),
            ("chain_break", "বিক্রেতার কোনো মালিকানা নেই", "Seller with no title at all",
             first(lambda d: d.truth == "CHAIN_BREAK" and accepted(d, "CHAIN_BREAK"))),
            ("oversell", "মালিকানার চেয়ে বেশি জমি বিক্রি", "Selling more than owned",
             first(lambda d: d.truth == "OVERSELL" and d.truth_meta.get("excess", 0) > 0.1 and accepted(d, "OVERSELL"))),
            ("khas", "খাস/অধিগৃহীত জমি বিক্রি", "Sale of khas / acquired land",
             first(lambda d: d.truth == "KHAS_LAND_SALE" and accepted(d, "KHAS_LAND_SALE"))),
            ("flip", "কয়েক দিনে বারবার হাতবদল", "Rapid flipping",
             first(lambda d: d.truth == "RAPID_FLIP" and accepted(d, "RAPID_FLIP")
                   and d.truth_meta.get("hop", 0) >= 3)),
            ("case", "মামলা চলমান জমির বিক্রি", "Sale while a case is pending",
             first(lambda d: d.truth == "PENDING_CASE" and accepted(d, "PENDING_CASE"))),
            ("anachronism", "মালিক হওয়ার আগেই দলিল সম্পাদন", "Executed before the seller owned the land",
             first(lambda d: d.truth == "ANACHRONISM" and accepted(d, "ANACHRONISM"))),
        ]
        out = []
        for sid, bn_label, en_label, d in picks:
            if d is None:
                continue
            out.append({"id": sid, "label_bn": bn_label, "label_en": en_label,
                        "expected": res[d.deed_id].decision,
                        "draft": {"parcel_id": d.parcel_id, "seller": d.seller, "buyer": d.buyer,
                                  "area": d.area, "unit": "decimal", "deed_type": d.deed_type,
                                  "reg_date": d.reg_date.isoformat(), "exec_date": d.exec_date.isoformat(),
                                  "broker": d.broker, "writer": d.writer, "witnesses": list(d.witnesses),
                                  "replay_of": d.deed_id}})
        return out

    # ---- a parcel, with both ledgers ----------------------------------------------
    def parcel(self, parcel_id: str) -> dict:
        s = self.state
        p = s.parcels.get(parcel_id)
        if p is None:
            raise KeyError(parcel_id)
        tv = s.title_replay(parcel_id, (date.max, DRAFT_SEQ))
        ac = s.ac_view(parcel_id, date.max)
        timeline = []
        for d in s.by_parcel.get(parcel_id, []):
            r = self.results[d.deed_id]
            row = self.deed_dict(d)
            row.update({"decision": r.decision, "score": r.score, "codes": sorted(r.codes - {"PENDING_MUTATION"})})
            timeline.append(row)
        return {
            "parcel": {"parcel_id": p.parcel_id, "district": p.district, "upazila": p.upazila, "mouza": p.mouza,
                       "survey": p.survey, "khatian_no": p.khatian_no, "dag_no": p.dag_no,
                       "total_area": p.total_area, "land_class": p.land_class,
                       "case_filed": p.case_filed.isoformat() if p.case_filed else None},
            "root_owners": [{"pid": pid, "name": s.name(pid), "area": a} for pid, a in p.root_owners],
            "registry_holders": self._holders(tv.holdings),
            "ac_land_holders": self._holders(ac),
            "timeline": timeline,
        }

    def find_parcels(self, q: str, limit: int = 12) -> list:
        q = q.strip().lower()
        out = []
        for p in self.state.parcels.values():
            if q in p.parcel_id.lower() or q in p.mouza.lower():
                out.append({"parcel_id": p.parcel_id, "mouza": p.mouza, "upazila": p.upazila,
                            "deeds": len(self.state.by_parcel.get(p.parcel_id, []))})
                if len(out) >= limit:
                    break
        return out

    # ---- flagged mutation applications ----------------------------------------------
    def mutations(self, limit: int = 40) -> dict:
        rows = []
        for m in self.state.mutation_apps:
            r = self.mut_results[m.app_id]
            if r.decision == "CLEAR":
                continue
            rows.append({"app_id": m.app_id, "parcel_id": m.parcel_id,
                         "applicant_name": self.state.name(m.applicant), "area": m.area,
                         "applied_date": m.applied_date.isoformat(), "cited_deed": m.deed_id,
                         "decision": r.decision, "score": r.score,
                         "alerts": agent.explain_alerts(r.alerts), "synthetic_label": m.truth})
        rows.sort(key=lambda x: (-x["score"], x["app_id"]))
        return {"total": len(rows), "rows": rows[:limit]}

    # ---- rings ---------------------------------------------------------------------------
    def rings(self) -> dict:
        return {
            "suspects": sorted(self.suspects.values(), key=lambda x: -x["blocked_deeds"]),
            "clusters": [{"blocked_deeds": c["blocked_deeds"], "hub": c["hub"],
                          "members": [{**m, "role_bn": agent.ROLE_BN.get(m["role"], m["role"])} for m in c["members"]]}
                         for c in self.clusters],
        }

    # ---- tamper-evidence demos --------------------------------------------------------------
    def tamper(self, kind: str, deed_id: str) -> dict:
        """Damage a *copy* of the ledger and show that verification catches it."""
        entries = copy.deepcopy(self.ledger.entries)
        idx = next((i for i, e in enumerate(entries) if e["deed_id"] == deed_id), None)
        if idx is None:
            raise KeyError(deed_id)
        if kind == "edit":
            before = entries[idx]["payload"]["area"]
            entries[idx]["payload"]["area"] = f"{float(before) + 1:.4f}"
            what = {"field": "area", "before": before, "after": entries[idx]["payload"]["area"]}
        elif kind == "delete":
            what = {"removed_deed": entries[idx]["deed_id"]}
            del entries[idx]
        else:
            raise ValueError("kind must be edit or delete")
        return {"kind": kind, "tampered": what, "verification": self.ledger.verify(entries),
                "untouched_ledger_ok": self.ledger_status["ok"]}

    def verify_copy(self, deed_id: str, changes: dict) -> dict:
        """Is a presented paper copy of a deed identical to the sealed record?"""
        d = self.state.by_id.get(deed_id)
        if d is None:
            raise KeyError(deed_id)
        payload = dict(d.payload())
        for k, v in (changes or {}).items():
            if k in payload and isinstance(v, (str, int, float)):
                payload[k] = str(v)
        return self.ledger.verify_deed(deed_id, payload)

    def insider_demo(self) -> dict:
        """An insider deletes the first sale so the second looks clean. The ledger exposes it."""
        d2 = next((d for d in self.state.deeds if d.truth == "DOUBLE_SALE"
                   and d.truth_meta.get("in_window") and self.results[d.deed_id].decision == "BLOCK"), None)
        if d2 is None:
            raise KeyError("no double-sale in this dataset")
        first_id = d2.truth_meta["first_deed"]
        st2 = self.state.without_deed(first_id)
        r2 = check_deed(st2, st2.by_id[d2.deed_id])
        t = self.tamper("delete", first_id)
        return {
            "second_deed": d2.deed_id, "first_deed": first_id,
            "with_intact_records": {"decision": self.results[d2.deed_id].decision,
                                    "codes": sorted(self.results[d2.deed_id].codes)},
            "after_first_sale_deleted": {"decision": r2.decision, "codes": sorted(r2.codes)},
            "ledger_check": t["verification"],
        }

    # ---- human in the loop ---------------------------------------------------------------------
    def officer_decision(self, deed_id: str, action: str, note: str, who: str) -> dict:
        if deed_id not in self.state.by_id:
            raise KeyError(deed_id)
        if action not in ("confirm_block", "release", "request_documents"):
            raise ValueError("action must be confirm_block, release or request_documents")
        rec = {"deed_id": deed_id, "action": action, "note": (note or "")[:300], "officer": (who or "officer")[:40],
               "machine_decision": self.results[deed_id].decision,
               "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        with self._lock:
            self.officer[deed_id] = rec
            self.audit.append(rec)
        return rec


def _text(body: dict, key: str) -> str:
    v = body.get(key, "")
    if not isinstance(v, str):
        raise ValueError(f"{key} must be text")
    return v.strip()[:MAX_TEXT]


def _date(v, default: date) -> date:
    if not v:
        return default
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        raise ValueError("dates must be YYYY-MM-DD")

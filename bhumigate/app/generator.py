"""Synthetic land-record generator with labelled fraud.

EVERYTHING GENERATED HERE IS DUMMY DATA. Names are random combinations from
small lists, identity tokens are random hashes, plot numbers are invented.
Nothing is derived from, or resembles, a real person's record.

The generator builds a timeline per plot (honest transfers, with realistic
noise), then injects labelled fraud of nine kinds. The labels are used only by
the evaluation; the detectors never see them.

ASSUMPTIONS (all adjustable, all stated, none measured from real data):
  * mutation delay: log-normal, median 35 days, clipped to 5-240 days, and 8% of
    buyers never file. The median is loosely informed by the official 28-working-day
    e-Mutation target; actual delays are unknown to us.
  * in_window_share: share of double-sales made while the first sale is still
    un-mutated. This is a parameter, not a finding. The evaluation shows how
    the baseline's recall depends on it.
  * fraud prevalence is stylised (default 15% of plots) so each type has enough
    samples to measure. Real prevalence is far lower; see evaluate.py.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from datetime import date, timedelta

from .models import GOV, SURVEY_DATE, Deed, MutationApp, Parcel, Person
from .state import LandState

START = date(2022, 1, 1)
LEGIT_END = date(2026, 5, 31)
END = date(2026, 9, 30)

FRAUD_TYPES = [
    "DOUBLE_SALE", "CHAIN_BREAK", "IMPERSONATION", "OVERSELL", "ANACHRONISM",
    "RAPID_FLIP", "KHAS_LAND_SALE", "PENDING_CASE", "MUTATION_MISMATCH",
]

MALE_FIRST = ["আব্দুল", "রহিম", "করিম", "জসিম", "সালাম", "মোস্তফা", "হাসান", "হোসেন", "ফারুক",
              "শফিক", "নজরুল", "আলমগীর", "মাহবুব", "রফিক", "জাহাঙ্গীর", "বাবুল", "সোহেল",
              "কামাল", "শাহিন", "মিজান", "আনোয়ার", "সাইফুল", "তারেক", "মনির", "ইমরান"]
FEMALE_FIRST = ["ফাতেমা", "আয়েশা", "রহিমা", "সালমা", "নাসরিন", "শিরিন", "রোকেয়া", "হালিমা",
                "জাহানারা", "মমতাজ", "রেহানা", "পারভীন", "শাহানা", "নাজমা", "সুলতানা"]
SURNAMES = ["মিয়া", "খান", "শেখ", "চৌধুরী", "হোসেন", "আহমেদ", "ইসলাম", "রহমান", "সরকার",
            "মোল্লা", "তালুকদার", "ভূঁইয়া", "প্রধান", "হক", "উদ্দিন"]
MOUZA_STEMS = ["কাজীপাড়া", "বাড়িয়া", "চরপাড়া", "নয়াপাড়া", "মধ্যপাড়া", "দক্ষিণগাঁও", "উত্তরগাঁও",
               "বেলতলী", "শিমুলতলী", "কালিকাপুর", "রামপুর", "হরিপুর", "ফুলবাড়ী", "নতুনহাট"]
PLACES = [
    ("ঢাকা", "DHK", [("সাভার", "SAV"), ("কেরানীগঞ্জ", "KER")]),
    ("গাজীপুর", "GAZ", [("শ্রীপুর", "SRP"), ("কালিয়াকৈর", "KLK")]),
    ("যশোর", "JSR", [("সদর", "SDR"), ("ঝিকরগাছা", "JHK")]),
    ("কুমিল্লা", "CUM", [("সদর দক্ষিণ", "SDK"), ("দেবিদ্বার", "DEB")]),
]


def generate(n_parcels: int = 1500, seed: int = 42, fraud_share: float = 0.15,
             in_window_share: float = 0.75, legit_burst_share: float = 0.015,
             ring_broker_share: float = 0.65) -> LandState:
    rng = random.Random(seed)
    people: dict[str, Person] = {}
    counters = {"person": 0, "deed": 0}

    # ---- people ---------------------------------------------------------
    def male_name():
        return f"মোঃ {rng.choice(MALE_FIRST)} {rng.choice(SURNAMES)}"

    def new_person(role="citizen") -> Person:
        counters["person"] += 1
        pid = "T" + hashlib.sha1(f"{seed}:{counters['person']}".encode()).hexdigest()[:10].upper()
        if rng.random() < 0.7:
            name = male_name()
        else:
            name = f"মোছাঃ {rng.choice(FEMALE_FIRST)} বেগম"
        p = Person(pid, name, male_name(), role)
        people[pid] = p
        return p

    def make_pro(prefix, n, role):
        out = []
        for i in range(1, n + 1):
            pid = f"{prefix}{i:03d}"
            p = Person(pid, male_name(), "", role)
            people[pid] = p
            out.append(pid)
        return out

    brokers = make_pro("B", 40, "broker")
    writers = make_pro("W", 25, "writer")
    witnesses = make_pro("S", 80, "witness")
    ring_brokers, norm_brokers = brokers[:4], brokers[4:]
    ring_writers, norm_writers = writers[:2], writers[2:]
    ring_witnesses, norm_witnesses = witnesses[:3], witnesses[3:]
    ring_ids = set(ring_brokers + ring_writers + ring_witnesses)

    def intermediaries(fraud: bool, broker_p=None):
        pb = (broker_p if broker_p is not None else ring_broker_share) if fraud else 0.02
        pw = 0.5 if fraud else 0.02
        ps = 0.5 if fraud else 0.02
        broker = rng.choice(ring_brokers) if rng.random() < pb else rng.choice(norm_brokers)
        writer = rng.choice(ring_writers) if rng.random() < pw else rng.choice(norm_writers)
        w = []
        while len(w) < 2:
            c = rng.choice(ring_witnesses) if rng.random() < ps else rng.choice(norm_witnesses)
            if c not in w:
                w.append(c)
        return broker, writer, w

    # ---- helpers ----------------------------------------------------------
    def d_add(d: date, days: int) -> date:
        return d + timedelta(days=days)

    def sample_lag():
        return int(min(240, max(5, rng.lognormvariate(math.log(35), 0.7))))

    def mut_lag_for(fraud: bool):
        if fraud:
            return sample_lag() if rng.random() < 0.6 else None
        return None if rng.random() < 0.08 else sample_lag()

    def new_deed(parcel, seller, buyer, area, reg_date, exec_date, fraud=False,
                 truth=None, meta=None, deed_type=None, intermed=None, lag="auto") -> Deed:
        counters["deed"] += 1
        n = counters["deed"]
        broker, writer, w = intermed or intermediaries(fraud)
        return Deed(
            deed_id=f"D{n:06d}", parcel_id=parcel.parcel_id,
            deed_type=deed_type or ("hiba" if rng.random() < 0.10 else "sale"),
            seller=seller, buyer=buyer, area=round(area, 2),
            exec_date=exec_date, reg_date=reg_date,
            sub_registry=f"{parcel.upazila} সাব-রেজিস্ট্রি অফিস",
            broker=broker, writer=writer, witnesses=w, seq=n,
            mut_lag=mut_lag_for(fraud) if lag == "auto" else lag,
            truth=truth, truth_meta=meta or {},
        )

    def make_parcel(i: int, inject):
        dname, dcode, upz = rng.choice(PLACES)
        uname, ucode = rng.choice(upz)
        mouza_no = rng.randint(1, 120)
        dag = rng.randint(100, 4999)
        total = round(min(300.0, max(3.0, rng.lognormvariate(math.log(14), 0.8))), 2)
        survey = rng.choices(["RS", "BS", "SA", "CS"], [0.6, 0.15, 0.15, 0.1])[0]
        land_class, owners = "private", []
        if inject == "KHAS_LAND_SALE":
            land_class = rng.choice(["khas", "acquired"])
            owners = [(GOV, total)]
        else:
            n_own = rng.choices([1, 2, 3, 4], [0.4, 0.3, 0.2, 0.1])[0]
            shares = [rng.random() + 0.25 for _ in range(n_own)]
            areas = [round(total * s / sum(shares), 2) for s in shares]
            areas[-1] = round(total - sum(areas[:-1]), 2)
            owners = [(new_person().pid, a) for a in areas if a > 0]
        return Parcel(
            parcel_id=f"{dcode}-{ucode}-{mouza_no:03d}-{dag}", district=dname, upazila=uname,
            mouza=f"{rng.choice(MOUZA_STEMS)}-{mouza_no}", survey=survey,
            khatian_no=str(rng.randint(1, 1800)), dag_no=str(dag), total_area=total,
            land_class=land_class, root_owners=owners,
        )

    def legit_chain(parcel, k, force_last_fraction=None):
        holders = defaultdict(float)
        acq = {}
        for pid, a in parcel.root_owners:
            holders[pid] += a
            acq[pid] = SURVEY_DATE
        t = d_add(START, rng.randint(0, 700))
        out = []
        for j in range(k):
            cands = [(p, h) for p, h in holders.items() if h >= 0.5 and p != GOV]
            if not cands:
                break
            seller = rng.choices([c[0] for c in cands], weights=[c[1] for c in cands])[0]
            h = holders[seller]
            if force_last_fraction is not None and j == k - 1:
                f = 1.0 if rng.random() < 0.4 else rng.uniform(force_last_fraction, 1.0)
            else:
                f = 1.0 if rng.random() < 0.35 else rng.uniform(0.3, 1.0)
            if h * f < 0.5:
                f = 1.0
            area = max(0.3, round(h * f * (1 + rng.gauss(0, 0.004)), 2))
            if j > 0:
                t = d_add(t, rng.randint(20, 400))
            if t > LEGIT_END:
                break
            others = [p for p in holders if p != seller and holders[p] > 0 and p != GOV]
            buyer = rng.choice(others) if (others and rng.random() < 0.10) else new_person().pid
            exec_d = max(acq[seller], d_add(t, -rng.randint(0, 5)))
            deed = new_deed(parcel, seller, buyer, area, t, exec_d)
            out.append(deed)
            holders[seller] = max(0.0, h - area)
            holders[buyer] += area
            acq.setdefault(buyer, t)
        last = out[-1].reg_date if out else d_add(START, rng.randint(50, 400))
        return out, holders, acq, last

    def burst(parcel, holders, acq, last, n_hops, fraud):
        cands = [(p, h) for p, h in holders.items() if h >= 1.0 and p != GOV]
        if not cands:
            return []
        seller = max(cands, key=lambda c: c[1])[0]
        area = holders[seller]
        t = d_add(last, rng.randint(20, 200))
        if t > END - timedelta(days=15):
            t = END - timedelta(days=15)
        out = []
        for i in range(n_hops):
            if i > 0:
                t = d_add(t, rng.randint(1, 4))
            buyer = new_person().pid
            a = max(0.3, round(area * (1 + rng.gauss(0, 0.002)), 2))
            exec_d = max(acq[seller], d_add(t, -rng.randint(0, 2)))
            is_fraud = fraud and i >= 2
            deed = new_deed(parcel, seller, buyer, a, t, exec_d, fraud=fraud,
                            truth="RAPID_FLIP" if is_fraud else None,
                            meta={"burst_member": True, "hop": i + 1, "fraud_burst": fraud},
                            intermed=intermediaries(fraud, broker_p=0.7), deed_type="sale")
            out.append(deed)
            acq[buyer] = t
            seller, area = buyer, a
        return out

    # ---- plan: which plots get which injected fraud -----------------------
    n_inject = int(n_parcels * fraud_share)
    plan = [FRAUD_TYPES[i % len(FRAUD_TYPES)] for i in range(n_inject)] + [None] * (n_parcels - n_inject)
    rng.shuffle(plan)
    needs_deed = {"DOUBLE_SALE", "ANACHRONISM", "MUTATION_MISMATCH"}

    parcels, deeds, mutation_apps = [], [], []
    stats = defaultdict(int)

    for i, inject in enumerate(plan):
        for _attempt in range(12):
            parcel = make_parcel(i, inject)
            k = rng.choices([0, 1, 2, 3, 4], [0.15, 0.35, 0.28, 0.15, 0.07])[0]
            if inject == "KHAS_LAND_SALE":
                k = 0
            if inject in needs_deed:
                k = max(1, k)
            chain, holders, acq, last = legit_chain(
                parcel, k, force_last_fraction=0.6 if inject == "DOUBLE_SALE" else None)
            if inject in needs_deed and not chain:
                continue
            break
        parcels.append(parcel)
        extra = []
        skip_legit_mut_for = set()

        if inject is None:
            if chain and rng.random() < legit_burst_share:
                extra = burst(parcel, holders, acq, last, 3, fraud=False)
                stats["legit_bursts"] += 1

        elif inject == "DOUBLE_SALE":
            d1 = chain[-1]
            d1.mut_lag = sample_lag()          # make the window well defined
            in_win = rng.random() < in_window_share
            if in_win:
                delta = rng.randint(1, max(1, d1.mut_lag - 1))
            else:
                delta = d1.mut_lag + rng.randint(2, 60)
            reg = min(END, d_add(d1.reg_date, delta))
            exec_d = max(d1.reg_date, d_add(reg, -rng.randint(0, 3)))
            extra = [new_deed(parcel, d1.seller, new_person().pid, d1.area * rng.uniform(0.95, 1.0),
                              reg, exec_d, fraud=True, truth="DOUBLE_SALE",
                              meta={"in_window": in_win, "first_deed": d1.deed_id})]

        elif inject == "CHAIN_BREAK":
            reg = min(END, d_add(last, rng.randint(5, 200)))
            area = max(0.5, parcel.total_area * rng.uniform(0.2, 0.7))
            extra = [new_deed(parcel, new_person().pid, new_person().pid, area, reg,
                              d_add(reg, -rng.randint(0, 3)), fraud=True, truth="CHAIN_BREAK")]

        elif inject == "IMPERSONATION":
            cands = [(p, h) for p, h in holders.items() if p != GOV and h > 0] or \
                    [(p, a) for p, a in parcel.root_owners if p != GOV]
            victim = max(cands, key=lambda c: c[1])[0]
            strong = rng.random() < 0.25
            vp = people[victim]
            if strong:
                name, father = male_name(), male_name()
            else:
                name = _mild_variant(vp.name_bn, rng)
                father = vp.father_bn if rng.random() < 0.85 else _mild_variant(vp.father_bn, rng)
            counters["person"] += 1
            pid = "T" + hashlib.sha1(f"{seed}:{counters['person']}".encode()).hexdigest()[:10].upper()
            people[pid] = Person(pid, name, father)
            reg = min(END, d_add(last, rng.randint(10, 200)))
            area = max(0.5, max(holders.get(victim, 0), 1.0) * rng.uniform(0.4, 1.0))
            extra = [new_deed(parcel, pid, new_person().pid, area, reg, d_add(reg, -rng.randint(0, 3)),
                              fraud=True, truth="IMPERSONATION",
                              meta={"victim": victim, "strong_variation": strong})]

        elif inject == "OVERSELL":
            ever = {p: a for p, a in parcel.root_owners if p != GOV}
            for d in chain:
                ever[d.buyer] = ever.get(d.buyer, 0.0) + d.area
            seller = rng.choice(sorted(ever))
            ex = math.exp(rng.uniform(math.log(0.003), math.log(0.4)))
            reg = min(END, d_add(last, rng.randint(10, 200)))
            extra = [new_deed(parcel, seller, new_person().pid, max(0.5, ever[seller] * (1 + ex)), reg,
                              d_add(reg, -rng.randint(0, 3)), fraud=True, truth="OVERSELL",
                              meta={"excess": round(ex, 4)})]

        elif inject == "ANACHRONISM":
            d_last = chain[-1]
            reg = min(END, d_add(d_last.reg_date, rng.randint(1, 30)))
            exec_d = d_add(d_last.reg_date, -rng.randint(3, 40))
            extra = [new_deed(parcel, d_last.buyer, new_person().pid, max(0.5, d_last.area * rng.uniform(0.3, 1.0)),
                              reg, exec_d, fraud=True, truth="ANACHRONISM")]

        elif inject == "RAPID_FLIP":
            extra = burst(parcel, holders, acq, last, rng.choice([3, 4]), fraud=True)

        elif inject == "KHAS_LAND_SALE":
            reg = d_add(START, rng.randint(100, 1500))
            area = max(0.5, parcel.total_area * rng.uniform(0.2, 0.8))
            extra = [new_deed(parcel, new_person().pid, new_person().pid, area, reg,
                              d_add(reg, -rng.randint(0, 3)), fraud=True, truth="KHAS_LAND_SALE")]

        elif inject == "PENDING_CASE":
            parcel.case_filed = d_add(last, rng.randint(1, 60))
            reg = min(END, d_add(parcel.case_filed, rng.randint(5, 120)))
            cands = [(p, h) for p, h in holders.items() if h >= 0.5 and p != GOV]
            if cands:
                seller, h = rng.choice(cands)
                area = max(0.3, h * rng.uniform(0.3, 1.0))
                extra = [new_deed(parcel, seller, new_person().pid, area, reg,
                                  max(acq[seller], d_add(reg, -rng.randint(0, 3))),
                                  fraud=True, truth="PENDING_CASE")]

        elif inject == "MUTATION_MISMATCH":
            d_last = chain[-1]
            if rng.random() < 0.5:
                variant = "no_deed"
                applicant = new_person().pid
                area = max(0.5, parcel.total_area * rng.uniform(0.1, 0.6))
                applied = d_add(last, rng.randint(5, 200))
                cited = None
            else:
                variant = "inflated_area"
                applicant = d_last.buyer
                area = d_last.area * (1 + rng.uniform(0.05, 0.5))
                applied = d_add(d_last.reg_date, rng.randint(2, 60))
                cited = d_last.deed_id
                skip_legit_mut_for.add(d_last.deed_id)
            mutation_apps.append(MutationApp(
                app_id=f"M-F{len(mutation_apps) + 1:05d}", parcel_id=parcel.parcel_id,
                applicant=applicant, area=round(area, 2), applied_date=applied, deed_id=cited,
                truth="MUTATION_MISMATCH", truth_meta={"variant": variant}))

        deeds.extend(chain)
        deeds.extend(extra)
        for d in chain + extra:
            if d.truth:
                stats[d.truth] += 1
        # honest mutation applications for honest deeds
        for d in chain + extra:
            if d.truth is None and d.mut_lag is not None and d.deed_id not in skip_legit_mut_for:
                lag_cap = max(1, min(4, d.mut_lag - 1))
                mutation_apps.append(MutationApp(
                    app_id=f"M{len(mutation_apps) + 1:05d}", parcel_id=d.parcel_id, applicant=d.buyer,
                    area=round(d.area * (1 + rng.gauss(0, 0.002)), 2),
                    applied_date=d_add(d.reg_date, rng.randint(1, lag_cap)), deed_id=d.deed_id))

    meta = {
        "seed": seed, "n_parcels": n_parcels, "fraud_share": fraud_share,
        "in_window_share": in_window_share, "legit_burst_share": legit_burst_share,
        "ring_broker_share": ring_broker_share,
        "ring_intermediaries": sorted(ring_ids),
        "injected": dict(stats),
    }
    return LandState(parcels, list(people.values()), deeds, mutation_apps, meta)


def _mild_variant(name: str, rng: random.Random) -> str:
    """A harmless-looking spelling variant of a Bangla name (what a lookalike impostor would use)."""
    options = [
        lambda s: s.replace("মোঃ", "মোহাম্মদ"),
        lambda s: s.replace("মোঃ ", ""),
        lambda s: s.replace("ি", "ী", 1),
        lambda s: s.replace("আব্দুল", "আবদুল"),
        lambda s: s,                                   # identical name
        lambda s: s[:-2] + s[-1:] if len(s) > 6 else s  # one dropped character
    ]
    return rng.choice(options)(name)

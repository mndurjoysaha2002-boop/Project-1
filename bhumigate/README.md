# ভূমি গেট — BhumiGate

**LandTech 2026 · Track: Digital Land Records, Verification & Digitization · Problem statement: P3 — Fraud & Double-Selling Detection**

BhumiGate is a pre-registration gate. Before a deed is accepted, it checks the draft against **both** land ledgers in Bangladesh, the sub-registry's deed ledger (Law Ministry) and the AC Land khatian (Land Ministry), and returns **CLEAR / HOLD / BLOCK** with the evidence in Bangla and English. A human officer always makes the final decision.

> **All data in this repository is synthetic (dummy).** No real person, NID, address or land record is collected, used or displayed. No government portal is scraped or queried. See [Data](#data).

## The problem, and the gap we target

A deed registered at the sub-registry does not automatically update the mutation record (khatian) at the AC Land office. The two offices sit under different ministries and the khatian lags. A seller can therefore sell the same land twice: the second sale looks clean to anyone who only looks at the khatian. BhumiGate reconciles the two ledgers at the moment of registration, so the second deed is caught while the first is still un-mutated.

## What it does

| Detector | Catches |
|---|---|
| `DOUBLE_SALE` | Seller already sold the land; registry holding too small. Flags when the khatian still shows the seller as owner (the lag-window case). |
| `CHAIN_BREAK`, `IMPERSONATION` | Seller has no recorded title; or a near-identical name and father's name with a different identity token (Bangla spelling variants are normalised). |
| `OVERSELL`, `AREA_EXCEEDS_PARCEL` | Deed sells more than the seller ever owned, or more than the whole plot. Units (decimal, katha, bigha, acre, sq ft) are converted at the edge. |
| `ANACHRONISM` | Deed executed before the seller acquired the land. |
| `RAPID_FLIP` | Several transfers of a plot within 14 days. |
| `KHAS_ACQUIRED`, `PENDING_CASE` | Sale of khas/acquired land, or of a plot with a case pending. |
| `MUTATION_WITHOUT_DEED`, `MUTATION_AREA_EXCEEDS_DEED` | Mutation applications that the deed ledger does not support (registration vs mutation mismatch). |
| `RING_LINK` | Brokers, deed writers or witnesses who keep appearing on blocked deeds across plots (graph analysis, `networkx`). |

Also:
- **Tamper-evident ledger.** Every registered deed is hashed (SHA-256), chained to the previous entry and signed with **Ed25519 by two keys** (Sub-Registry and AC Land). Editing, deleting or reordering an entry is detected. This matters for fraud detection: an insider who deletes the first sale makes the second look clean to the gate, but the broken hash chain exposes the deletion (dashboard tab 4, demo 4).
- **Officer in the loop.** Confirm block / request documents / release, written to an audit log.
- **Investigator agent** (`app/agent.py`): runs a fixed sequence of tool calls over the records, shows each step, and writes a Bangla and English case note. The note comes from templates that use only numbers in the evidence. An optional LLM step can polish the Bangla wording; it is **off by default** and never changes a decision.

## Why deterministic rules, not a black-box model

Land officers must be able to explain a hold to a citizen and to a court. Every alert carries machine-readable evidence, scores are a simple, documented combination (`app/gate.py`), and the detectors never read the synthetic ground-truth labels (there is a test for this).

## Run it

Requires Python 3.10+ (developed and tested on 3.13). No web framework: the server uses only the standard library.

```bash
pip install -r requirements.txt        # cryptography, networkx
python -m app.server                   # http://127.0.0.1:8000
python -m app.evaluate 3000            # prints the evaluation, writes data/eval.json
python -m unittest discover -s tests   # 29 tests
```

Options: `python -m app.server --port 9000 --parcels 3000 --seed 42`. The server binds to `127.0.0.1` unless you pass `--host`.

Optional LLM polish of the Bangla note: set `ANTHROPIC_API_KEY` (and optionally `LLM_MODEL`). This path needs internet and a key, and is not covered by the automated tests; the default demo does not use it.

## Architecture

```
 synthetic generator ──► LandState ─┬─ registry view  (root khatian + every deed registered so far)
 (labelled fraud)                   └─ AC Land view   (khatian + only the mutations approved so far, lagging)
                                         │
 draft deed ───► detectors.py ──► gate.py (score → CLEAR/HOLD/BLOCK) ──► rings.py (escalate/watch)
                                         │                                      │
                                   agent.py (case note)                  ledger.py (hash chain + 2 signatures)
                                         └────────────► service.py ──► server.py ──► static/ dashboard (বাংলা / English)
```

## Evaluation (synthetic data; read the caveats)

`python -m app.evaluate 3000` — 3,000 plots, 5,509 deeds, seed 42:

| | BhumiGate | Khatian-only baseline |
|---|---|---|
| Fraud recall (all injected types) | 96.9% | 87.1% |
| False alerts on legitimate deeds | 0.8% | 6.8% |
| Double sales inside the mutation-lag window (n=37) | 100% | 3% |
| Double sales outside the window (n=13) | 100% | 92% |

**Caveats, stated plainly:**
- The fraud patterns and rates were chosen by us. High recall on patterns we injected shows the mechanism works; it is **not** accuracy on real Bangladeshi records, which we have not seen.
- The baseline is an owner-of-record check on the AC Land view only: a modelling choice, not a measurement of any live system.
- How badly the baseline does on double sales depends on the assumed share made inside the lag window, so the dashboard and `evaluate.py` include a sensitivity table (baseline recall falls from 76% to 12% as that share goes from 25% to 100%; the gate stays at 100%).
- The mutation delay (median 35 days) is an assumption loosely informed by the official e-Mutation target, not a measured value. Fraud prevalence is stylised at 15% of plots so each type has enough samples; the precision-at-1%-prevalence figure is the more realistic one.
- Inheritance by unrecorded heirs, power-of-attorney deeds, and OCR of scanned records are **not** modelled.

## Data

- **Source:** generated by `app/generator.py`. Names are random combinations from short lists; identity tokens are random hashes (a stand-in for a hashed NID; no NID is ever needed); plot numbers are invented.
- **No real data** and **no scraping** of any government portal. Security features (ledger tamper demos) run only on this prototype's own data.
- Reproducible: the same `--seed` produces the same dataset.
- Land-law and process background (registration vs mutation split, CS/SA/RS/BS surveys, e-Mutation) comes from public news and law-journal articles and the LandTech 2026 Rule Book; it informed the design but no dataset was taken from them.

## Countrywide plan

1. **Pilot** in one upazila: run BhumiGate in shadow mode beside the sub-registry, officers compare its holds with their own.
2. **Integrate** through authorised APIs with the e-Registration and e-Mutation systems so both ledgers feed the gate; the Registration (Amendment) Act, 2026 introduces electronic registration, which is the natural insertion point.
3. **Joint custody of the ledger:** the two signing keys held by the two offices (ideally in HSMs), so no single office can rewrite history.
4. **Roll out** district by district. Hosting on government infrastructure; personal data stays in Bangladesh, consistent with the Personal Data Protection Act, 2026.
5. Any LLM component, if used at all, would be an open-weight Bangla-capable model run on government servers.

## Limitations

- Decision support only. It does not determine ownership.
- Demo signing keys are derived from a public seed in `app/ledger.py` and are **not secret**. In a deployment they would be generated and held by the two offices.
- One in-memory process; no database, authentication or role management yet.
- Name-similarity thresholds were set on synthetic names and would need calibration on real data.

## AI tool disclosure (Rule Book §9)

> **Team: edit this section so it is accurate before submitting.**

- **Claude (Anthropic)**, used through Claude Code / claude.ai, assisted with: researching the Bangladesh land-registration context, designing the architecture, writing and reviewing code (`app/`, `static/`, `tests/`), and drafting this README.
- All code was run and tested; the 29 tests pass. Both student members must be able to explain every module before the Final Round.
- Optional runtime use of an LLM (Anthropic API) for wording polish only; off by default.

## Team and mentors

> **Team: fill in.** Team name · Student 1 (leader) · Student 2 · Faculty mentor · Industry mentor.

## Changes since Round 1

_(Final Round only — summarise here.)_

## Licence and credits

Dependencies: [`cryptography`](https://cryptography.io) (Apache-2.0/BSD), [`networkx`](https://networkx.org) (BSD-3). Everything else is standard library. Add the licence you choose for this repository.

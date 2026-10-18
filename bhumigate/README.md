# ভূমি গেট · BhumiGate

**A pre-registration fraud gate for Bangladesh land records.**
LandTech 2026 Innovation Hackathon · Daffodil International University
Track: Digital Land Records, Verification & Digitization · Problem statement: **P3 – Fraud & Double-Selling Detection**

> **All data in this repository is synthetic (dummy).** No real person, NID, address or land record is collected, used or displayed. No government portal is scraped, queried or tested.

![BhumiGate gate screen: a double sale is blocked and a khatian-only check would have missed it](docs/screenshots/01-gate.png)

## Team

| Role | Name | DIU ID |
|---|---|---|
| Team member | Zarin Tasnim | 0242310005101030 |
| Team member | Munindro Nath Durjoy Saha | 0242310005101278 |
| Faculty mentor | Atiqur Rahman, Department of CSE | |
| Industry support mentor | MD Zafor Iqbal, CSE-TECH | |

## The problem

In Bangladesh, registering a deed and updating the khatian (mutation) are two separate steps at two offices under two ministries. The sub-registry (Law Ministry) records the deed. The AC Land office (Land Ministry) updates the khatian weeks later.

In that gap a seller can sell the same land twice. The second sale looks clean to anyone who checks only the khatian, because the khatian still shows the seller as the owner.

## What BhumiGate does

Before a deed is accepted, BhumiGate checks the draft against **both** ledgers of the plot:

- the **registry view**: the root khatian plus every deed registered so far;
- the **AC Land view**: the khatian plus only the mutations approved so far (this one lags).

It returns **CLEAR, HOLD or BLOCK** with a 0–100 risk score and the evidence in Bangla and English. A human officer always makes the final decision, and every officer action goes to an audit log.

Example from the demo data: the seller sold 5.57 decimals on 10 Jan 2022, so the registry shows 0.04 decimals left. The khatian still shows 5.61. On 15 Jan the seller offers 5.49 decimals to a second buyer. A khatian-only check passes it; BhumiGate blocks it.

### Detectors

All detectors are deterministic and explainable. Each alert carries machine-readable evidence.

| Detector | What it catches |
|---|---|
| `DOUBLE_SALE` | Seller already sold the land; the registry holding is too small while the khatian still shows the seller as owner |
| `CHAIN_BREAK` | Seller has no recorded title |
| `IMPERSONATION` | Near-identical name and father's name with a different identity token (Bangla spelling variants are normalised) |
| `OVERSELL`, `AREA_EXCEEDS_PARCEL` | Deed sells more than the seller owned, or more than the whole plot (units are converted: decimal, katha, bigha, acre, sq ft) |
| `ANACHRONISM` | Deed executed before the seller acquired the land |
| `RAPID_FLIP` | Several transfers of one plot within 14 days |
| `KHAS_ACQUIRED`, `PENDING_CASE` | Sale of khas or acquired land, or of a plot with a case pending |
| `PENDING_MUTATION` | Informational only: an earlier mutation is still pending (alone, it does not hold a legitimate resale) |
| `MUTATION_WITHOUT_DEED`, `MUTATION_AREA_EXCEEDS_DEED` | Mutation applications that the deed ledger does not support |
| `RING_LINK` | Brokers, deed writers or witnesses who keep appearing on blocked deeds across plots (graph analysis) |

Score = highest alert severity + 0.15 × the rest. BLOCK at 70 or more, HOLD at 30 or more, otherwise CLEAR.

### Web features and why they exist

| Screen | Purpose |
|---|---|
| **Gate** | The clerk's entry point. Ten example deeds can be replayed in one click; the draft form converts units; the verdict says when a khatian-only check would have missed the case. |
| **Case note** (Bangla first, English toggle) | Plain sentences built only from numbers in the evidence, so an officer can explain a hold to a citizen or a court. Lists every lookup the investigator ran. |
| **Alert queue** | Held and blocked deeds with filters, so officers start with the riskiest. |
| **Plot and two ledgers** | Any plot's registry holding, khatian holding and transfer history side by side. |
| **Mutation applications** | The same check on the AC Land side: requests with no deed behind them, or larger than the deed. |
| **Tamper-proof ledger** | Four live demos of what the signed ledger catches, including an insider deleting the first sale. |
| **Ring detection** | Repeat intermediaries across blocked deeds. |
| **Evaluation** | Results with an on-screen warning that the data is synthetic. |

| Case note and steps (Bangla) | Insider demo |
|---|---|
| ![Bangla case note, investigation steps and officer decision](docs/screenshots/02-case-note-bangla.png) | ![Insider deletes the first sale: the gate shows clear, the ledger check catches it](docs/screenshots/05-ledger-insider-demo.png) |

### Tamper-evident ledger

Every registered deed is hashed (SHA-256), chained to the previous entry and signed with Ed25519 by **two keys** (Sub-Registry and AC Land). Editing, deleting or reordering an entry is detected.

This matters for fraud detection, not only for record keeping. An insider who deletes the first sale makes the second look clean to the gate, but the broken hash chain exposes the deletion.

### Investigator

`app/agent.py` runs a fixed sequence of lookups over the records (registry history, AC Land record, detectors, ring check), shows each step, and writes a Bangla and English case note from templates. An optional step can polish the Bangla wording with a language model through the Anthropic API. It is **off by default**, is not covered by the automated tests, and never changes a decision.

## Why rules and not a black-box model

Land officers must be able to explain a hold to a citizen and to a court. Scores are a simple, documented combination (`app/gate.py`). The detectors never read the synthetic ground-truth labels, and a test checks this. The running system makes no AI calls unless you set an API key for the optional wording step.

## Run it

Requires Python 3.10 or newer (developed and tested on 3.13). The server uses only the standard library, so there is no web framework to install.

```bash
pip install -r requirements.txt        # cryptography, networkx
python -m app.server                   # then open http://127.0.0.1:8000
python -m app.evaluate 3000            # prints the evaluation, writes data/eval.json
python -m unittest discover -s tests   # 29 tests
```

On Windows use `py` instead of `python` if `python` is not recognised. In VS Code: File → Open Folder, open the terminal with Ctrl+`, then run the commands above. Startup takes a few seconds because it generates 3,000 plots and signs about 5,500 ledger entries.

Options: `python -m app.server --port 9000 --parcels 3000 --seed 42`. The server binds to `127.0.0.1` unless you pass `--host`.

Optional wording polish: set `ANTHROPIC_API_KEY` (and optionally `LLM_MODEL`). This needs internet and a key.

## Architecture

```
 synthetic generator ──► LandState ─┬─ registry view  (root khatian + every deed registered so far)
 (labelled fraud)                   └─ AC Land view   (khatian + only the mutations approved so far, lagging)
                                         │
 draft deed ───► detectors.py ──► gate.py (score → CLEAR/HOLD/BLOCK) ──► rings.py (escalate / watch)
                                         │                                      │
                                   agent.py (case note)                  ledger.py (hash chain + 2 signatures)
                                         └────────────► service.py ──► server.py ──► static/ dashboard (বাংলা / English)
```

```
app/        engine, ledger, investigator, generator, evaluation, HTTP server
static/     dashboard (plain HTML, CSS and JavaScript; no CDN, strict Content Security Policy)
tests/      29 unit and HTTP tests
data/       eval.json written by app.evaluate
docs/       screenshots
```

Security of the demo server: same-origin Content Security Policy, `nosniff`, strict input validation (bad input returns 400, not 500), path-traversal protection, a 64 KB request limit, no stack traces in responses.

## Evaluation (synthetic data; read the caveats)

`python -m app.evaluate 3000` — 3,000 plots, 5,509 deeds, seed 42.

| | BhumiGate | Khatian-only baseline |
|---|---|---|
| Fraud recall (425 injected fraud deeds) | 96.9% | 87.1% |
| False alerts on legitimate deeds (5,084) | 0.8% | 6.8% |
| Double sales inside the mutation-lag window (n = 37) | 100% | 3% |
| Double sales outside the window (n = 13) | 100% | 92% |
| Precision if fraud is 1% of deeds | 55% | 11.5% |

The 95% (Wilson) interval for the gate's recall is 94.8% to 98.2%. Mutation check: 49 of 50 unsupported applications flagged, 0 false alerts on 4,604 legitimate ones. Ring discovery: 9 of 9 planted members found, 0 false suspects.

![Evaluation screen](docs/screenshots/07-evaluation.png)

**Caveats, stated plainly:**

- The fraud patterns and rates were chosen by us. High recall on patterns we injected shows the mechanism works; it is **not** accuracy on real Bangladeshi records, which we have not seen.
- The baseline is an owner-of-record check on the AC Land view only. It is a modelling choice, not a measurement of any live system.
- How badly the baseline does on double sales depends on the assumed share made inside the lag window. The dashboard and `evaluate.py` include a sensitivity table: baseline recall falls from 76% to 12% as that share goes from 25% to 100%, while the gate stays at 100%.
- The mutation delay (median 35 days) is an assumption, not a measured value. Fraud prevalence is stylised at 15% of plots so each type has enough samples; the 1%-prevalence precision is the more realistic figure.
- Inheritance by unrecorded heirs, power-of-attorney deeds and OCR of scanned records are **not** modelled.

## Data

- **Source:** generated by `app/generator.py`. Names are random combinations from short lists; identity tokens are random hashes (a stand-in for a hashed NID, so no NID is ever needed); plot numbers are invented. The same `--seed` gives the same dataset.
- **No real data** and **no scraping** of any government portal. The tamper demos run only on this prototype's own data.
- Land-law and process background (registration versus mutation, survey records, e-Mutation) informed the design; no dataset was taken from any source.

## Roadmap

Built now: everything above. Not built yet:

1. **LLM investigator (planned).** A model that chooses its own read-only lookups, with a checker that rejects any note containing a number or name not found in the evidence. The rules would still make every decision.
2. **ML queue ranking (planned, after a pilot).** With only self-generated labels a model would mostly learn our own generator, so it needs real officer decisions. It would only order the queue and never override a rule.
3. **Shadow pilot** in one upazila, beside the sub-registry.
4. **Integration** with e-Registration and e-Mutation through authorised APIs. The two signing keys would be held by the two offices, ideally in hardware security modules.
5. **Rollout** district by district on government infrastructure, with personal data kept in Bangladesh. Any language model would be an open-weight Bangla-capable model on government servers.

## Limitations

- Decision support only. It does not determine ownership.
- Demo signing keys are derived from a public seed in `app/ledger.py` and are **not secret**.
- One in-memory process; no database, login or role management yet.
- Name-similarity thresholds were set on synthetic names and need calibration on real data.
- No live deployment; the demo runs locally.

## AI tool disclosure (Rule Book §9)

We used **Claude (Anthropic)**, through Claude Code and claude.ai, as a development assistant. It helped with:

- researching the Bangladesh land-registration context;
- designing the architecture;
- writing and reviewing code in `app/`, `static/` and `tests/`;
- drafting this README, the concept note and the pitch deck.

How we checked the work:

- We ran the dashboard and the full test suite locally; all 29 tests pass.
- The evaluation is reproducible from a fixed seed with `python -m app.evaluate 3000`.
- The numbers in this README come from `data/eval.json`, and its limits are stated above.

The product itself does not depend on AI to make decisions. Verdicts come from the deterministic rules in `app/detectors.py` and `app/gate.py`. The only optional runtime use of a language model is the wording polish described above, which is off by default.

## References

**Competition**
- LandTech 2026 Innovation Hackathon Rule Book, Daffodil International University (Sections 8 and 9 on data and AI-tool disclosure).

**Bangladesh land administration (design background)**
- The Registration Act, 1908 (deed registration at the sub-registry).
- The State Acquisition and Tenancy Act, 1950 (khas land and mutation of records).
- Ministry of Land, e-Mutation service (the digital mutation process).
- The Registration (Amendment) Act, 2026 and the Personal Data Protection Act, 2026, as reported publicly at the time of writing; check the official gazette text before relying on them.

**Techniques and standards**
- NIST FIPS 180-4, *Secure Hash Standard* (SHA-256).
- Josefsson, S. and Liusvaara, I., RFC 8032, *Edwards-Curve Digital Signature Algorithm (EdDSA)* (Ed25519).
- Hagberg, A., Schult, D. and Swart, P. (2008). Exploring network structure, dynamics, and function using NetworkX. *Proceedings of the 7th Python in Science Conference (SciPy 2008)*, pp. 11–15.
- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209–212 (confidence intervals in the evaluation).

**Software**
- [`cryptography`](https://cryptography.io) (Apache-2.0 / BSD) and [`networkx`](https://networkx.org) (BSD-3-Clause). Everything else is the Python standard library.

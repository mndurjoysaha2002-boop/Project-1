"""Tests for BhumiGate. Standard library unittest only:  python -m unittest discover -s tests -v

They check behaviour that matters for the claims we make: the gate sees double
sales that a khatian-only check misses, honest deeds are not flagged, the
ledger exposes tampering, and the HTTP API validates input.
"""

import copy
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import agent, units  # noqa: E402
from app.gate import check_deed  # noqa: E402
from app.generator import generate  # noqa: E402
from app.namematch import similarity  # noqa: E402
from app.server import Handler  # noqa: E402
from app.service import World  # noqa: E402

WORLD = World(n_parcels=600, seed=11)   # small, fast, deterministic


class Units(unittest.TestCase):
    def test_round_trip(self):
        for u in ("decimal", "katha", "bigha", "acre", "sqft"):
            self.assertAlmostEqual(units.from_decimal(units.to_decimal(3.5, u), u), 3.5)

    def test_acre_is_100_decimals(self):
        self.assertEqual(units.to_decimal(1, "acre"), 100.0)

    def test_unknown_unit(self):
        with self.assertRaises(ValueError):
            units.to_decimal(1, "furlong")


class Names(unittest.TestCase):
    def test_spelling_variants_match(self):
        self.assertGreater(similarity("মোঃ আব্দুল করিম", "মোহাম্মদ আবদুল করিম"), 0.85)

    def test_different_people_do_not(self):
        self.assertLess(similarity("মোঃ রহিম মিয়া", "মোঃ সালাম চৌধুরী"), 0.7)


class Generator(unittest.TestCase):
    def test_deterministic(self):
        a, b = generate(150, seed=5), generate(150, seed=5)
        self.assertEqual([d.deed_id for d in a.deeds], [d.deed_id for d in b.deeds])
        self.assertEqual([d.area for d in a.deeds], [d.area for d in b.deeds])

    def test_no_real_looking_ids(self):
        # identity tokens are hashes with a T prefix; no digit-only NID-like values
        for p in WORLD.state.people.values():
            self.assertFalse(p.pid.isdigit())

    def test_has_every_fraud_type(self):
        injected = WORLD.state.meta["injected"]
        for t in ("DOUBLE_SALE", "CHAIN_BREAK", "IMPERSONATION", "OVERSELL", "RAPID_FLIP", "KHAS_LAND_SALE"):
            self.assertGreater(injected.get(t, 0), 0, t)


class Gate(unittest.TestCase):
    def test_in_window_double_sale_is_caught_but_khatian_only_misses_it(self):
        ds = [d for d in WORLD.state.deeds if d.truth == "DOUBLE_SALE" and d.truth_meta.get("in_window")]
        self.assertTrue(ds)
        caught = sum(1 for d in ds if WORLD.results[d.deed_id].decision != "CLEAR")
        missed_by_baseline = sum(1 for d in ds if not WORLD.results[d.deed_id].baseline_flag)
        self.assertEqual(caught, len(ds))
        self.assertGreater(missed_by_baseline, len(ds) // 2)

    def test_honest_deeds_mostly_clear(self):
        legit = [d for d in WORLD.state.deeds if not d.truth]
        flagged = sum(1 for d in legit if WORLD.results[d.deed_id].decision != "CLEAR")
        self.assertLess(flagged / len(legit), 0.03)

    def test_pending_mutation_alone_does_not_hold_a_legit_resale(self):
        d = next(d for d in WORLD.state.deeds if not d.truth and "PENDING_MUTATION" in WORLD.results[d.deed_id].codes
                 and len(WORLD.results[d.deed_id].codes) == 1)
        self.assertEqual(WORLD.results[d.deed_id].decision, "CLEAR")

    def test_khas_land_is_blocked(self):
        for d in (x for x in WORLD.state.deeds if x.truth == "KHAS_LAND_SALE"):
            self.assertEqual(WORLD.results[d.deed_id].decision, "BLOCK")

    def test_detectors_never_read_ground_truth(self):
        d = next(x for x in WORLD.state.deeds if x.truth == "DOUBLE_SALE")
        before = check_deed(WORLD.state, d).to_dict()
        d2 = copy.copy(d)
        d2.truth, d2.truth_meta = None, {}
        self.assertEqual(before, check_deed(WORLD.state, d2).to_dict())


class Ledger(unittest.TestCase):
    def test_untouched_ledger_verifies(self):
        self.assertTrue(WORLD.ledger.verify()["ok"])

    def test_edit_is_detected(self):
        d = WORLD.state.deeds[10].deed_id
        self.assertFalse(WORLD.tamper("edit", d)["verification"]["ok"])

    def test_delete_is_detected(self):
        d = WORLD.state.deeds[10].deed_id
        self.assertFalse(WORLD.tamper("delete", d)["verification"]["ok"])

    def test_tamper_does_not_touch_real_ledger(self):
        WORLD.tamper("edit", WORLD.state.deeds[3].deed_id)
        self.assertTrue(WORLD.ledger.verify()["ok"])

    def test_altered_paper_copy(self):
        d = WORLD.state.deeds[5].deed_id
        self.assertTrue(WORLD.verify_copy(d, {})["authentic"])
        r = WORLD.verify_copy(d, {"area": "999.0000"})
        self.assertFalse(r["authentic"])
        self.assertEqual(r["changed_fields"], ["area"])

    def test_insider_deleting_first_sale_hides_it_from_gate_but_not_from_ledger(self):
        r = WORLD.insider_demo()
        self.assertEqual(r["with_intact_records"]["decision"], "BLOCK")
        self.assertNotEqual(r["after_first_sale_deleted"]["decision"], "BLOCK")
        self.assertFalse(r["ledger_check"]["ok"])


class Service(unittest.TestCase):
    def test_every_scenario_gives_its_expected_decision(self):
        sc = WORLD.scenarios()
        self.assertGreaterEqual(len(sc), 8)
        for s in sc:
            self.assertEqual(WORLD.check_draft(s["draft"])["decision"], s["expected"], s["id"])

    def test_draft_validation(self):
        good = WORLD.scenarios()[0]["draft"]
        for bad in ({**good, "parcel_id": "nope"}, {**good, "area": -3}, {**good, "area": "abc"},
                    {**good, "seller": ""}, {**good, "reg_date": "16/10/2026"}, {**good, "unit": "furlong"},
                    {**good, "deed_type": "mortgage"}):
            with self.assertRaises(ValueError):
                WORLD.check_draft(bad)

    def test_unit_conversion_reaches_the_gate(self):
        d = {**WORLD.scenarios()[0]["draft"], "unit": "acre", "area": 1}   # 100 decimals: far larger than the plot
        r = WORLD.check_draft(d)
        self.assertEqual(r["decision"], "BLOCK")

    def test_officer_decision_is_logged(self):
        d = WORLD.state.deeds[0].deed_id
        rec = WORLD.officer_decision(d, "release", "checked on site", "tester")
        self.assertEqual(WORLD.audit[-1], rec)
        with self.assertRaises(ValueError):
            WORLD.officer_decision(d, "delete_everything", "", "tester")

    def test_notes_are_bangla_and_use_only_evidence(self):
        s = next(x for x in WORLD.scenarios() if x["id"] == "double_sale")
        r = WORLD.check_draft(s["draft"])
        self.assertIn("শতাংশ", r["note_bn"])
        self.assertIn("decimals", r["note_en"])
        self.assertEqual(r["note_source"], "template")   # no API key in tests

    def test_llm_polish_is_off_without_a_key(self):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.assertIsNone(agent.polish_with_llm("টেস্ট"))


class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Handler.world = WORLD
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, path, body=None):
        req = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read()), r.headers
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read()), e.headers

    def test_summary_and_security_headers(self):
        code, data, hdr = self.call("/api/summary")
        self.assertEqual(code, 200)
        self.assertTrue(data["synthetic"])
        self.assertIn("default-src 'self'", hdr["Content-Security-Policy"])
        self.assertEqual(hdr["X-Content-Type-Options"], "nosniff")

    def test_gate_endpoint(self):
        code, data, _ = self.call("/api/gate", WORLD.scenarios()[2]["draft"])
        self.assertEqual(code, 200)
        self.assertEqual(data["decision"], "BLOCK")

    def test_bad_input_is_400_not_500(self):
        self.assertEqual(self.call("/api/gate", {"parcel_id": "x", "seller": "y", "area": 1})[0], 400)
        self.assertEqual(self.call("/api/deed/..%2F..%2Fetc%2Fpasswd")[0], 400)
        self.assertEqual(self.call("/api/deed/D999999999")[0], 404)

    def test_static_path_traversal_blocked(self):
        for p in ("/static/../app/service.py", "/../app/service.py", "/%2e%2e/app/service.py"):
            code = self.call(p)[0]
            self.assertIn(code, (400, 404), p)


if __name__ == "__main__":
    unittest.main()

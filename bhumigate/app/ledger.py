"""Tamper-evident registration ledger.

Every registered deed is sealed: its canonical fields are hashed (SHA-256),
chained to the previous entry, and signed by two independent keys (Sub-Registry
and AC Land). Deleting, editing or reordering any past entry breaks the chain.

This matters for fraud detection because the double-sale check replays the
registry. An insider who quietly deletes the first sale hides the second one
from the replay: the ledger check is what exposes that.

DEMO NOTE: here both keys live in one process. In a deployment the two
signing keys would be held by two different offices (ideally in an HSM), so no
single office could rewrite history alone.
"""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .models import canonical_json, sha256_hex

GENESIS = "0" * 64


class RegistryLedger:
    def __init__(self, seed: bytes = b"bhumigate-demo-keys-not-secret-0"):
        # deterministic demo keys so results are reproducible; never use real secrets like this
        self._k_reg = Ed25519PrivateKey.from_private_bytes(sha256_hex(seed.decode() + "reg")[:32].encode())
        self._k_ac = Ed25519PrivateKey.from_private_bytes(sha256_hex(seed.decode() + "ac")[:32].encode())
        self.pub_reg = self._k_reg.public_key()
        self.pub_ac = self._k_ac.public_key()
        self.entries: list[dict] = []

    # ---- writing ------------------------------------------------------
    @staticmethod
    def payload_hash(payload: dict) -> str:
        return sha256_hex(canonical_json(payload))

    def append(self, deed_id: str, payload: dict) -> dict:
        index = len(self.entries)
        prev = self.entries[-1]["entry_hash"] if self.entries else GENESIS
        ph = self.payload_hash(payload)
        entry_hash = sha256_hex(f"{index}|{prev}|{ph}")
        raw = bytes.fromhex(entry_hash)
        entry = {
            "index": index,
            "deed_id": deed_id,
            "payload": payload,
            "payload_hash": ph,
            "prev_hash": prev,
            "entry_hash": entry_hash,
            "sig_registry": self._k_reg.sign(raw).hex(),
            "sig_ac_land": self._k_ac.sign(raw).hex(),
        }
        self.entries.append(entry)
        return entry

    # ---- reading ------------------------------------------------------
    def find(self, deed_id: str):
        for e in self.entries:
            if e["deed_id"] == deed_id:
                return e
        return None

    def verify(self, entries: list | None = None) -> dict:
        """Verify hash chain and both signatures. Returns the first problem found, if any."""
        entries = self.entries if entries is None else entries
        prev = GENESIS
        for i, e in enumerate(entries):
            if e["index"] != i:
                return self._bad(i, e, "index gap: an entry was removed or reordered")
            if e["prev_hash"] != prev:
                return self._bad(i, e, "chain broken: previous hash does not match")
            if self.payload_hash(e["payload"]) != e["payload_hash"]:
                return self._bad(i, e, "payload altered: content no longer matches its hash")
            expect = sha256_hex(f"{i}|{prev}|{e['payload_hash']}")
            if expect != e["entry_hash"]:
                return self._bad(i, e, "entry hash mismatch")
            raw = bytes.fromhex(e["entry_hash"])
            try:
                self.pub_reg.verify(bytes.fromhex(e["sig_registry"]), raw)
                self.pub_ac.verify(bytes.fromhex(e["sig_ac_land"]), raw)
            except (InvalidSignature, ValueError):
                return self._bad(i, e, "signature invalid")
            prev = e["entry_hash"]
        return {"ok": True, "entries": len(entries), "head": prev}

    @staticmethod
    def _bad(i, e, reason):
        return {"ok": False, "first_bad_index": i, "deed_id": e.get("deed_id"), "reason": reason}

    def verify_deed(self, deed_id: str, payload: dict) -> dict:
        """Is a presented deed copy identical to what was sealed at registration?"""
        e = self.find(deed_id)
        if e is None:
            return {"authentic": False, "reason": "no such deed in the ledger", "changed_fields": []}
        changed = [k for k in sorted(set(e["payload"]) | set(payload))
                   if e["payload"].get(k) != payload.get(k)]
        if not changed:
            return {"authentic": True, "reason": "matches the sealed record", "changed_fields": [],
                    "entry_hash": e["entry_hash"]}
        return {"authentic": False, "reason": "presented copy differs from the sealed record",
                "changed_fields": changed,
                "sealed": {k: e["payload"].get(k) for k in changed},
                "presented": {k: payload.get(k) for k in changed}}

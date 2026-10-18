"""The gate: combine detector alerts into one decision (CLEAR / HOLD / BLOCK).

Decisions are decision-support for the Sub-Registrar / AC Land officer. They
never determine ownership; a human approves or rejects every HOLD and BLOCK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .detectors import (Alert, baseline_flag, deed_key, run_deed_detectors,
                        run_mutation_detectors)
from .models import Deed, MutationApp
from .state import LandState

BLOCK_AT = 70
HOLD_AT = 30


def score_alerts(alerts: list) -> int:
    """Highest severity, plus a small contribution from every other alert."""
    sevs = sorted((a.severity for a in alerts), reverse=True)
    if not sevs:
        return 0
    return int(min(100, round(sevs[0] + 0.15 * sum(sevs[1:]))))


def decide(score: int) -> str:
    if score >= BLOCK_AT:
        return "BLOCK"
    if score >= HOLD_AT:
        return "HOLD"
    return "CLEAR"


@dataclass
class GateResult:
    subject_id: str
    parcel_id: str
    kind: str                      # deed | mutation
    alerts: list = field(default_factory=list)
    context: dict = field(default_factory=dict)
    baseline_flag: Optional[bool] = None
    stage: int = 1                 # 1 = rules only, 2 = after ring escalation

    @property
    def score(self) -> int:
        return score_alerts(self.alerts)

    @property
    def decision(self) -> str:
        return decide(self.score)

    @property
    def codes(self) -> set:
        return {a.code for a in self.alerts}

    def add_alert(self, alert: Alert):
        self.alerts.append(alert)
        self.alerts.sort(key=lambda a: -a.severity)

    def to_dict(self) -> dict:
        return {
            "subject_id": self.subject_id,
            "parcel_id": self.parcel_id,
            "kind": self.kind,
            "decision": self.decision,
            "score": self.score,
            "alerts": [a.to_dict() for a in self.alerts],
            "context": self.context,
            "baseline_flag": self.baseline_flag,
            "stage": self.stage,
        }


def check_deed(state: LandState, deed: Deed, key=None) -> GateResult:
    key = key or deed_key(deed)
    alerts, ctx = run_deed_detectors(state, deed, key)
    return GateResult(
        subject_id=deed.deed_id,
        parcel_id=deed.parcel_id,
        kind="deed",
        alerts=alerts,
        context=ctx,
        baseline_flag=baseline_flag(state, deed, key),
    )


def check_mutation(state: LandState, app: MutationApp) -> GateResult:
    alerts = run_mutation_detectors(state, app)
    return GateResult(subject_id=app.app_id, parcel_id=app.parcel_id,
                      kind="mutation", alerts=alerts)

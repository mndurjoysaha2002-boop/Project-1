"""Ring detection: find brokers, deed writers and witnesses who keep turning up on blocked deeds.

Individual rules judge one deed at a time. Organised fraud shows up across
deeds: the same few intermediaries appear again and again. We build a graph of
deeds and their intermediaries (networkx), score each intermediary by how many
distinct plots they touched with BLOCK-level deeds, and use that to
  * escalate deeds that are only on HOLD to BLOCK when a suspect intermediary is on them,
  * put a "watch" mark (no hold) on otherwise clean deeds that involve a suspect.
"""

from __future__ import annotations

from collections import defaultdict

import networkx as nx

from .detectors import Alert
from .gate import BLOCK_AT, HOLD_AT, GateResult

MIN_BLOCKED_PLOTS = 3
MIN_BLOCK_RATE = 0.20


def find_suspects(state, results: dict) -> dict:
    """results: deed_id -> stage-1 GateResult. Returns {node: stats} for suspect intermediaries."""
    total = defaultdict(int)
    blocked = defaultdict(int)
    plots = defaultdict(set)
    for d in state.deeds:
        res = results.get(d.deed_id)
        for role, who in d.intermediaries():
            node = (role, who)
            total[node] += 1
            if res is not None and res.decision == "BLOCK":
                blocked[node] += 1
                plots[node].add(d.parcel_id)
    suspects = {}
    for node, n_blocked in blocked.items():
        rate = n_blocked / total[node]
        if len(plots[node]) >= MIN_BLOCKED_PLOTS and rate >= MIN_BLOCK_RATE:
            suspects[node] = {
                "role": node[0],
                "id": node[1],
                "name": state.name(node[1]),
                "deeds": total[node],
                "blocked_deeds": n_blocked,
                "block_rate": round(rate, 2),
                "blocked_plots": len(plots[node]),
            }
    return suspects


def build_graph(state, results: dict, suspects: dict):
    """Bipartite graph: BLOCK deeds <-> intermediaries. Used for clusters and the dashboard."""
    g = nx.Graph()
    for d in state.deeds:
        res = results.get(d.deed_id)
        if res is None or res.decision != "BLOCK":
            continue
        g.add_node(("deed", d.deed_id), kind="deed")
        for node in d.intermediaries():
            g.add_node(node, kind=node[0], suspect=node in suspects)
            g.add_edge(("deed", d.deed_id), node)
    return g


def clusters(state, graph, suspects: dict) -> list:
    """Group suspect intermediaries that co-occur on the same blocked deeds."""
    sg = nx.Graph()
    sg.add_nodes_from(suspects)
    for n in graph.nodes:
        if n[0] != "deed":
            continue
        linked = [m for m in graph.neighbors(n) if m in suspects]
        for i in range(len(linked)):
            for j in range(i + 1, len(linked)):
                sg.add_edge(linked[i], linked[j])
    out = []
    for comp in nx.connected_components(sg):
        members = sorted(comp)
        deeds = {n for n in graph.nodes if n[0] == "deed" and any(m in graph[n] for m in members)}
        hub = max(members, key=lambda m: suspects[m]["blocked_deeds"])
        out.append({
            "members": [suspects[m] for m in members],
            "blocked_deeds": len(deeds),
            "hub": {"role": hub[0], "id": hub[1], "name": state.name(hub[1])},
        })
    out.sort(key=lambda c: -c["blocked_deeds"])
    return out


def apply_escalation(state, deed, res: GateResult, suspects: dict) -> GateResult:
    """Stage 2. Mutates and returns `res`."""
    hits = [(role, who) for role, who in deed.intermediaries() if (role, who) in suspects]
    if not hits:
        return res
    evidence = {"suspects": [{"role": r, "id": w, "name": state.name(w),
                              "blocked_plots": suspects[(r, w)]["blocked_plots"]}
                             for r, w in hits]}
    score = res.score
    if HOLD_AT <= score < BLOCK_AT:
        res.add_alert(Alert("RING_LINK", 75, {**evidence, "effect": "escalated_to_block"}))
    elif score < HOLD_AT:
        res.add_alert(Alert("RING_LINK", 20, {**evidence, "effect": "watchlist_only"}))
    else:
        res.add_alert(Alert("RING_LINK", 40, {**evidence, "effect": "corroborates"}))
    res.stage = 2
    return res

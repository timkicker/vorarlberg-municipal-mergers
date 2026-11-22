"""Checks on the derived data. Run after `make results`."""

import csv
import json
import pathlib
import sys

import networkx as nx
import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
DIVISIONS = ROOT / "data/raw/vbg_regional_divisions.csv"
if not DIVISIONS.exists():
    pytest.skip("data/raw is empty, run make data first", allow_module_level=True)
GKZ = {r["gkz"] for r in csv.DictReader(DIVISIONS.open(encoding="utf-8"), delimiter=";")}


def need(name: str) -> pathlib.Path:
    """A file in data/derived; skips the test if it is one of those not passed on (DATA.md) and not built yet."""
    path = DERIVED / name
    if not path.exists():
        pytest.skip(f"data/derived/{name} missing, run make results")
    return path


def neighbours():
    return list(csv.DictReader(need("neighbours.csv").open(encoding="utf-8")))


def test_both_boundary_sources_give_the_same_edges():
    rows = neighbours()
    assert len(rows) == 251
    assert all(float(r["border_m_statat"]) > 0 and float(r["border_m_vogis"]) > 0 for r in rows)


def test_point_contacts_are_dropped():
    dropped = {(r["name_a"], r["name_b"]) for r in neighbours() if r["neighbour"] == "0"}
    assert dropped == {("Laterns", "Viktorsberg"), ("Dornbirn", "Zwischenwasser")}


def test_neighbour_graph_is_connected():
    g = nx.Graph((r["gkz_a"], r["gkz_b"]) for r in neighbours() if r["neighbour"] == "1")
    assert set(g) == GKZ
    assert nx.is_connected(g)


def test_cooperation_records_complete():
    recs = json.loads(need("coop2016.json").read_text())
    assert [r["id"] for r in recs] == list(range(1, 267))
    assert not [r["id"] for r in recs if r["unknown"]]
    # records that legitimately have fewer than two municipalities
    assert {r["id"] for r in recs if len(r["members"]) < 2} == {41, 172, 180, 215, 243}


def test_memberships_use_official_codes():
    rows = list(csv.DictReader(need("coop2016_members.csv").open(encoding="utf-8")))
    assert {r["gkz"] for r in rows} <= GKZ
    assert len(rows) == len({(r["coop_id"], r["gkz"]) for r in rows})


def test_commuter_lists_match_totals():
    flows = list(csv.DictReader(need("commuters_2024.csv").open(encoding="utf-8")))
    info = {r["gkz"]: r for r in csv.DictReader(need("commuters_2024_municipalities.csv").open(encoding="utf-8"))}
    assert set(info) == GKZ
    out = {g: 0 for g in GKZ}
    into = {g: 0 for g in GKZ}
    for r in flows:
        out[r["from_gkz"]] += int(r["count"])
        if r["to"] in GKZ:
            into[r["to"]] += int(r["count"])
        assert r["to"] != r["from_gkz"]
    assert all(out[g] == int(info[g]["out_commuters"]) for g in GKZ)
    assert all(into[g] <= int(info[g]["in_commuters"]) for g in GKZ)


def test_intramax_regions_are_contiguous():
    rows = list(csv.DictReader(need("intramax_regions.csv").open(encoding="utf-8")))
    g = nx.Graph((r["gkz_a"], r["gkz_b"]) for r in neighbours() if r["neighbour"] == "1")
    for col in ("k4", "k8", "k10", "k19"):
        groups = {}
        for r in rows:
            groups.setdefault(r[col], set()).add(r["gkz"])
        assert len(groups) == int(col[1:])
        assert all(nx.is_connected(g.subgraph(m)) for m in groups.values())


def test_cost_data_complete():
    rows = list(csv.DictReader(need("administration_2016_2019.csv").open(encoding="utf-8")))
    ok = [r for r in rows if r["complete"] == "True"]
    assert len(ok) == 2091
    assert {r["gkz"] for r in ok if r["state"] == "8"} == GKZ
    assert all(float(r["population"]) > 0 and float(r["area_km2"]) > 0 for r in ok)


def test_styria_mapping_and_panel():
    text = need("styria.txt").read_text()
    assert "2014: 539 municipalities, 2015: 287 units, without predecessor: []" in text
    assert "Units in panel 279, treated 123, control 156" in text


def test_styria_outcomes_use_same_units():
    text = need("styria_outcomes.txt").read_text()
    assert text.startswith("Styria 279 units (123 merged), other states 1677")


def test_pareto_candidates_are_contiguous_and_status_quo_on_front():
    g = nx.Graph((r["gkz_a"], r["gkz_b"]) for r in neighbours() if r["neighbour"] == "1")
    rows = list(csv.DictReader(need("pareto_partitions.csv").open(encoding="utf-8")))
    for col in [c for c in rows[0] if c not in ("gkz", "municipality")]:
        groups = {}
        for r in rows:
            groups.setdefault(r[col], set()).add(r["gkz"])
        assert all(nx.is_connected(g.subgraph(m)) for m in groups.values()), col
    cands = {r["name"]: r for r in csv.DictReader(need("pareto_candidates.csv").open(encoding="utf-8"))}
    assert cands["Status quo"]["front"] == "1" and cands["Status quo"]["E_main"] == "0"


def test_election_counts():
    text = need("elections.txt").read_text()
    assert "A: share 0.46" in text and "Status quo 2025: 14.9%" in text


def test_styria_elections_all_mapped():
    text = need("styria_elections.txt").read_text()
    assert "2005: municipalities without assignment via 2011: [], eligible voters 0" in text
    assert "2010: municipalities without assignment via 2011: [], eligible voters 0" in text
    assert "Units 279, merged 122, unchanged 157" in text


def test_capped_rule_without_cap_is_threshold_rule():
    sys.path.insert(0, str(ROOT / "src" / "gf"))
    import pareto
    import ratio
    import regions

    rows, t, adj = regions.load()
    adm = {r["gkz"]: r for r in csv.DictReader(need("administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[r["gkz"]]["population"]) for r in rows])
    assert pareto.threshold_rule(t, adj, pop, 3500) == ratio.capped_rule(t, adj, pop, 3500, None)[0]
    lab, _ = ratio.capped_rule(t, adj, pop, 3500, 5)
    for u in set(lab):
        m = pop[[i for i, l in enumerate(lab) if l == u]]
        assert m.max() / m.min() <= 5


def test_forecast_complete():
    sys.path.insert(0, str(ROOT / "src" / "gf"))
    import pop2050

    f = pop2050.forecast()
    assert len({g for g, _ in f}) == 96
    assert {y for _, y in f} == set(range(2026, 2051))
    assert round(sum(v[0] for (g, y), v in f.items() if y == 2026)) == 413325


def test_travel_time_matrix():
    rows = list(csv.reader(need("travel_time_seat.csv").open(encoding="utf-8")))
    T = np.array([[float(v) for v in r[1:]] for r in rows[1:]])
    assert T.shape == (96, 96)
    assert np.allclose(np.diag(T), 0) and np.allclose(T, T.T, atol=0.11)
    text = need("travel_time.txt").read_text()
    assert "['Mittelberg'], pairs 95" in text


def test_voluntary_rule():
    sys.path.insert(0, str(ROOT / "src" / "gf"))
    import pareto
    import regions
    import voluntary

    rows, t, adj = regions.load()
    adm = {r["gkz"]: r for r in csv.DictReader(need("administration_2016_2019.csv").open(encoding="utf-8"))}
    pop = np.array([float(adm[r["gkz"]]["population"]) for r in rows])
    assert voluntary.rule(t, adj, pop, 2000, None)[0] == pareto.threshold_rule(t, adj, pop, 2000)
    T = np.zeros((96, 96))
    lab, _ = voluntary.rule(t, adj, pop, 2000, lambda m: voluntary.acceptable(m, pop, T, 0.2, 15))
    for u in set(lab):
        m = [i for i, l in enumerate(lab) if l == u]
        assert (pop[m] / pop[m].sum()).min() >= 0.2


def test_typed_transfer_estimates_match_their_source():
    """styria_control.py types two estimates that later scripts print, so check they still agree."""
    import re

    control = need("styria_control.txt").read_text()
    for source, pattern, name in (
        ("styria_transfers.txt", r"after 2016-19, Styrian control \(n \d+\): ([+-]?\d+\.\d)", "state grants 2016-19"),
        ("styria_transfers_2024.txt", r"after 2020-24 \(n \d+\): ([+-]?\d+\.\d)", "section 94 2020-24"),
    ):
        value = float(re.search(pattern, need(source).read_text()).group(1))
        typed = float(re.search(re.escape(name) + r": estimated ([+-]?\d+\.\d)", control).group(1))
        assert typed == value, (source, typed, value)

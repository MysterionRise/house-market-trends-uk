"""Tests for the API services on the synthetic store."""

import pytest

from lix_api.services import areas, compare, explain, pois, ranking, search
from lix_api.services.scoring import resolve_weights
from lix_api.services.sql import SqlError, SqlGuard


class TestSearch:
    def test_postcode_exact(self, store):
        (p,) = search.search_place(store, "ls6 3hn")
        assert (p.kind, p.lsoa21cd) == ("postcode", "E01000001")

    def test_lsoa_and_area_codes(self, store):
        assert search.search_place(store, "E01000003")[0].kind == "lsoa"
        assert search.search_place(store, "E08000035")[0].name == "Leeds"

    def test_city_beats_village_and_lad_first(self, store):
        results = search.search_place(store, "Leeds")
        assert results[0].kind == "lad"
        assert [r.detail for r in results if r.kind == "place"][0] == "City, Leeds"

    def test_typo_and_nonsense(self, store):
        assert search.search_place(store, "Headingly")[0].name == "Headingley"
        assert search.search_place(store, "Nowheresville XYZ") == []


class TestProfile:
    def test_profile_fields(self, store):
        p = areas.area_profile(store, "LS6 3HN")
        assert p.lsoa21cd == "E01000001"
        assert p.neighbourhood == "Headingley"
        assert len(p.themes) == len(store.themes)
        assert p.strengths[0].score >= p.strengths[-1].score
        assert p.weaknesses[0].score <= p.weaknesses[-1].score
        assert 1 <= p.band <= 5

    def test_imputed_crime_is_flagged(self, store):
        assert any("Greater Manchester" in f for f in areas.area_profile(store, "E01000004").flags)

    def test_unknown_area(self, store):
        with pytest.raises(LookupError):
            areas.area_profile(store, "Nowheresville XYZ")


class TestRanking:
    def test_within_local_authority(self, store):
        r = ranking.rank_areas(store, within="Leeds", level="lsoa", limit=10)
        assert r.candidates == 4
        assert all(a.local_authority == "Leeds" for a in r.results)
        overall = [a.overall for a in r.results]
        assert overall == sorted(overall, reverse=True)

    def test_price_filter_and_msoa_level(self, store):
        r = ranking.rank_areas(store, level="msoa", max_median_price=400_000)
        assert {a.code for a in r.results} == {"E02000001", "E02000002"}

    def test_weights_change_the_order(self, store):
        safety_only = {t: 0.0 for t in store.themes} | {"safety": 1.0}
        r = ranking.rank_areas(store, level="lsoa", theme_weights=safety_only, limit=1)
        assert r.results[0].code == "E01000003"  # fewest crimes in the fixture
        assert r.preset.endswith("(adjusted)")

    def test_radius_around_place(self, store):
        r = ranking.rank_areas(store, within="Brighton", radius_km=5, level="lsoa")
        assert {a.code for a in r.results} == {"E01000005", "E01000006"}

    def test_unknown_preset(self, store):
        with pytest.raises(ValueError, match="Unknown preset"):
            resolve_weights(store, "hermit")


def test_compare(store):
    c = compare.compare_areas(store, ["LS6 3HN", "Brighton and Hove"])
    assert [a.level for a in c.areas] == ["lsoa", "lad"]
    assert c.areas[1].indicators["house_price"] == pytest.approx(
        (450_000 * 1900 + 520_000 * 2000) / 3900, rel=1e-3
    )
    with pytest.raises(ValueError):
        compare.compare_areas(store, ["LS6 3HN"])


class TestPois:
    def test_nearest_first_and_well_run_filter(self, store):
        r = pois.nearest_pois(store, "well_run_pub", "LS6 3HN", max_km=2)
        assert [p.name for p in r.pois] == ["Well Run Arms"]
        allpubs = pois.nearest_pois(store, "pub", "LS6 3HN", max_km=2)
        assert [p.name for p in allpubs.pois] == ["Grubby Tavern", "Well Run Arms"]

    def test_unknown_category(self, store):
        with pytest.raises(ValueError, match="Unknown category"):
            pois.nearest_pois(store, "spaceport", "LS6 3HN")


def test_explain_shares_sum_to_one(store):
    e = explain.explain_score(store, "LS6 3HN")
    assert sum(c.weight_share for c in e.contributions) == pytest.approx(1.0, abs=0.01)
    contributions = [c.contribution for c in e.contributions]
    assert contributions == sorted(contributions, reverse=True)
    one = explain.explain_score(store, "LS6 3HN", theme="safety")
    assert [c.theme for c in one.contributions] == ["safety"]


class TestSqlGuard:
    @pytest.fixture
    def guard(self, store):
        return SqlGuard(store)

    def test_select(self, guard):
        r = guard.run("SELECT lad_nm, count(*) AS n FROM lsoa GROUP BY 1 ORDER BY 1")
        assert r.columns == ["lad_nm", "n"]
        assert r.rows == [["Brighton and Hove", 2], ["Leeds", 4]]

    @pytest.mark.parametrize(
        "sql",
        [
            "COPY lsoa TO '/tmp/x.csv'",
            "ATTACH '/tmp/x.db'",
            "SELECT 1; SELECT 2",
            "INSTALL httpfs",
            "SET enable_external_access = true",
            "CREATE TABLE t AS SELECT 1",
            "SELECT * FROM read_csv('/etc/passwd')",
            "SELECT * FROM read_parquet('https://example.com/x.parquet')",
        ],
    )
    def test_rejects(self, guard, sql):
        with pytest.raises(SqlError):
            guard.run(sql)

    def test_row_cap(self, guard):
        r = guard.run("SELECT * FROM range(100)", max_rows=10)
        assert len(r.rows) == 10 and r.truncated

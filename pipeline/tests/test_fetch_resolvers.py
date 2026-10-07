"""Tests for resolvers (ArcGIS, GOV.UK), the FeatureServer fetcher and the fetch orchestrator."""

import json
from pathlib import Path

import geopandas as gpd
import polars as pl
import pytest
from werkzeug import Request, Response

from lix_core.config import (
    ArcgisItemAccess,
    DatasetSpec,
    GovukAttachmentAccess,
)
from lix_pipeline import fetch as fetch_mod
from lix_pipeline.fetch import ManualDownloadRequired, arcgis, fetch, govuk, select
from lix_pipeline.fetch.lock import read_lock
from lix_pipeline.fetch.session import make_session

ONS_QUERY = 'title:"National Statistics Postcode Lookup" AND owner:ONSGeography_data'


def _arcgis_access(**overrides) -> ArcgisItemAccess:
    base = dict(
        type="arcgis_item",
        query=ONS_QUERY,
        title_regex=r"^National Statistics Postcode Lookup \([A-Z][a-z]+ \d{4}\)$",
        item_type="CSV Collection",
        pin="pinned0",
        mode="data",
    )
    return ArcgisItemAccess(**{**base, **overrides})


@pytest.fixture
def arcgis_server(httpserver, monkeypatch):
    monkeypatch.setattr(arcgis, "ARCGIS", httpserver.url_for("/sharing/rest"))
    monkeypatch.setattr(arcgis, "HUB_DOWNLOAD", httpserver.url_for("/hub"))
    return httpserver


class TestResolveArcgisItem:
    SEARCH = {
        "results": [
            # Newest overall, but wrong type
            {"id": "table1", "type": "Feature Service", "modified": 300,
             "title": "National Statistics Postcode Lookup (August 2026) for the UK (Table)"},
            # Matches type but not title
            {"id": "guide1", "type": "CSV Collection", "modified": 250,
             "title": "National Statistics Postcode Lookup (August 2026) User Guide"},
            {"id": "aug26", "type": "CSV Collection", "modified": 200,
             "title": "National Statistics Postcode Lookup (August 2026)"},
            {"id": "may26", "type": "CSV Collection", "modified": 100,
             "title": "National Statistics Postcode Lookup (May 2026)"},
        ]
    }  # fmt: skip

    def test_picks_newest_matching_item(self, arcgis_server):
        arcgis_server.expect_request("/sharing/rest/search").respond_with_json(self.SEARCH)
        resolved = arcgis.resolve_item(_arcgis_access(), make_session())
        assert resolved["item_id"] == "aug26"
        assert resolved["title"] == "National Statistics Postcode Lookup (August 2026)"
        assert resolved["url"].endswith("/sharing/rest/content/items/aug26/data")

    def test_falls_back_to_pin_when_search_finds_nothing(self, arcgis_server):
        arcgis_server.expect_request("/sharing/rest/search").respond_with_json({"results": []})
        arcgis_server.expect_request("/sharing/rest/content/items/pinned0").respond_with_json(
            {"id": "pinned0", "title": "Pinned", "modified": 5, "type": "CSV Collection"}
        )
        resolved = arcgis.resolve_item(_arcgis_access(), make_session())
        assert resolved["item_id"] == "pinned0"

    def test_hub_export_and_featureserver_urls(self, arcgis_server):
        item = {"id": "fs1", "title": "T", "modified": 1, "type": "Feature Service",
                "url": "https://services1.arcgis.com/x/FeatureServer/"}  # fmt: skip
        arcgis_server.expect_request("/sharing/rest/content/items/fs1").respond_with_json(item)
        session = make_session()

        hub = _arcgis_access(query=None, pin="fs1", mode="hub_export", export_format="geoPackage")
        assert arcgis.resolve_item(hub, session)["url"].endswith("/hub/fs1/geoPackage?layers=0")

        fs = _arcgis_access(query=None, pin="fs1", mode="featureserver")
        assert arcgis.resolve_item(fs, session)["url"] == (
            "https://services1.arcgis.com/x/FeatureServer/0"
        )

    def test_arcgis_error_with_http_200_raises(self, arcgis_server):
        arcgis_server.expect_request("/sharing/rest/search").respond_with_json({"results": []})
        arcgis_server.expect_request("/sharing/rest/content/items/pinned0").respond_with_json(
            {"error": {"code": 400, "message": "Item does not exist or is inaccessible."}}
        )
        with pytest.raises(RuntimeError, match="Item does not exist"):
            arcgis.resolve_item(_arcgis_access(), make_session())


def _feature_layer(httpserver, records: list[dict], page_size: int, short_every: int = 0):
    """Serve a fake feature layer: metadata, count, and offset-paged queries.

    ``short_every`` > 0 makes each response return at most that many records, like a
    server hitting its transfer limit.
    """
    httpserver.expect_request("/layer/0", query_string={"f": "json"}).respond_with_json(
        {"maxRecordCount": page_size, "objectIdField": "OID", "fields": []}
    )

    def query(request: Request) -> Response:
        args = request.args
        if args.get("returnCountOnly") == "true":
            return Response(json.dumps({"count": len(records)}), content_type="application/json")
        assert args["orderByFields"] == "OID"
        offset, size = int(args["resultOffset"]), int(args["resultRecordCount"])
        if short_every:
            size = min(size, short_every)
        page = records[offset : offset + size]
        if args["f"] == "geojson":
            body = {"type": "FeatureCollection", "features": page}
        else:
            body = {"features": page}
        return Response(json.dumps(body), content_type="application/json")

    httpserver.expect_request("/layer/0/query").respond_with_handler(query)
    return httpserver.url_for("/layer/0")


class TestFetchFeatureserver:
    def test_points_to_parquet_with_bng_xy(self, httpserver, tmp_path: Path):
        records = [
            {"attributes": {"LSOA21CD": f"E0100000{i}"}, "geometry": {"x": 1000.0 + i, "y": 2000.0}}
            for i in range(5)
        ]
        url = _feature_layer(httpserver, records, page_size=2)
        access = _arcgis_access(mode="featureserver", geometry="point", fields=["LSOA21CD"])
        out = tmp_path / "pts.parquet"

        n = arcgis.fetch_featureserver(url, access, out, make_session(), workers=2)

        df = pl.read_parquet(out)
        assert n == 5
        assert df.columns == ["LSOA21CD", "x", "y"]
        assert df["LSOA21CD"].to_list() == [f"E0100000{i}" for i in range(5)]
        assert df["x"].to_list() == [1000.0, 1001.0, 1002.0, 1003.0, 1004.0]

    def test_follows_short_pages(self, httpserver, tmp_path: Path):
        records = [{"attributes": {"OA21CD": f"E{i:08d}"}} for i in range(7)]
        url = _feature_layer(httpserver, records, page_size=4, short_every=3)
        out = tmp_path / "t.parquet"

        arcgis.fetch_featureserver(url, _arcgis_access(mode="featureserver"), out, make_session())

        assert pl.read_parquet(out)["OA21CD"].to_list() == [f"E{i:08d}" for i in range(7)]

    def test_count_mismatch_raises(self, httpserver, tmp_path: Path):
        httpserver.expect_request("/layer/0", query_string={"f": "json"}).respond_with_json(
            {"maxRecordCount": 10, "objectIdField": "OID", "fields": []}
        )

        def query(request: Request) -> Response:
            if request.args.get("returnCountOnly") == "true":
                return Response(json.dumps({"count": 3}), content_type="application/json")
            return Response(json.dumps({"features": [{"attributes": {"a": 1}}]}))

        httpserver.expect_request("/layer/0/query").respond_with_handler(query)
        with pytest.raises(RuntimeError, match="Expected 3 records"):
            arcgis.fetch_featureserver(
                httpserver.url_for("/layer/0"),
                _arcgis_access(mode="featureserver"),
                tmp_path / "x.parquet",
                make_session(),
            )
        assert not (tmp_path / "x.parquet").exists()

    def test_polygons_to_geopackage_in_bng(self, httpserver, tmp_path: Path):
        square = [[[-1.0, 52.0], [-0.99, 52.0], [-0.99, 52.01], [-1.0, 52.01], [-1.0, 52.0]]]
        records = [
            {"type": "Feature", "properties": {"MSOA21CD": "E02000001"},
             "geometry": {"type": "Polygon", "coordinates": square}},
        ]  # fmt: skip
        url = _feature_layer(httpserver, records, page_size=10)
        out = tmp_path / "m.gpkg"

        arcgis.fetch_featureserver(
            url, _arcgis_access(mode="featureserver", geometry="polygon"), out, make_session()
        )

        gdf = gpd.read_file(out)
        assert gdf.crs.to_epsg() == 27700
        assert gdf["MSOA21CD"].tolist() == ["E02000001"]
        # ~690m x ~1110m square around 1°W 52°N
        assert 0.6e6 < gdf.geometry.area.iloc[0] < 0.9e6


class TestResolveGovuk:
    def test_finds_attachment_by_regex(self, httpserver, monkeypatch):
        monkeypatch.setattr(govuk, "CONTENT_API", httpserver.url_for("/api/content"))
        page = {
            "public_updated_at": "2025-11-17T09:20:39+00:00",
            "details": {
                "attachments": [
                    {"title": "File 1", "url": "https://assets/media/1/File_1_IoD2025_IMD.xlsx"},
                    {"title": "File 7", "url": "https://assets/media/7/File_7_IoD2025_All.csv"},
                ]
            },
        }
        httpserver.expect_request("/api/content/government/statistics/iod").respond_with_json(page)
        access = GovukAttachmentAccess(
            type="govuk_attachment",
            path="government/statistics/iod",
            attachment_regex=r"File_7_IoD2025_.*\.csv$",
        )

        resolved = govuk.resolve_attachment(access, make_session())

        assert resolved["url"] == "https://assets/media/7/File_7_IoD2025_All.csv"
        assert resolved["title"] == "File 7"

    def test_ambiguous_match_raises(self, httpserver, monkeypatch):
        monkeypatch.setattr(govuk, "CONTENT_API", httpserver.url_for("/api/content"))
        page = {"details": {"attachments": [{"url": "a.csv"}, {"url": "b.csv"}]}}
        httpserver.expect_request("/api/content/p").respond_with_json(page)
        access = GovukAttachmentAccess(
            type="govuk_attachment", path="p", attachment_regex=r"\.csv$"
        )
        with pytest.raises(RuntimeError, match="found 2"):
            govuk.resolve_attachment(access, make_session())


def _spec(access: dict, fmt: str = "csv", **kw) -> DatasetSpec:
    return DatasetSpec(
        title="Test",
        theme=kw.pop("theme", "geography"),
        access=access,
        format=fmt,
        description="d",
        licence="OGL-3.0",
        attribution="a",
        cadence="static",
        **kw,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch):
    """A throwaway repo root (for the lockfile) and data directory."""
    (tmp_path / "config").mkdir()
    monkeypatch.setenv("LIX_ROOT", str(tmp_path))
    monkeypatch.setenv("LIX_DATA_DIR", str(tmp_path / "data"))
    return tmp_path


class TestFetchOrchestrator:
    def test_resolves_downloads_and_locks(self, repo, httpserver):
        httpserver.expect_request("/f.csv", method="HEAD").respond_with_data(
            "", headers={"Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT"}
        )
        httpserver.expect_request("/f.csv", method="GET").respond_with_data(b"a,b\n1,2\n")
        registry = {"f": _spec({"type": "http", "url": httpserver.url_for("/f.csv")})}

        fetched = fetch("f", registry=registry)

        lock = read_lock()["f"]
        assert lock["resolved"]["version"] == "Mon, 01 Jan 2024 00:00:00 GMT"
        assert lock["fetched"]["sha256"] == fetched["sha256"]
        assert (repo / "data" / "raw" / "f" / "f.csv").read_bytes() == b"a,b\n1,2\n"

    def test_strict_rejects_changed_checksum(self, repo, httpserver):
        httpserver.expect_request("/f.csv", method="HEAD").respond_with_data("")
        httpserver.expect_request("/f.csv", method="GET").respond_with_data(b"new,data\n")
        registry = {"f": _spec({"type": "http", "url": httpserver.url_for("/f.csv")})}
        (repo / "config" / "datasets.lock.json").write_text(
            json.dumps({"f": {"fetched": {"sha256": "0" * 64}}})
        )

        with pytest.raises(RuntimeError, match="Checksum differs"):
            fetch("f", registry=registry, strict=True)

    def test_manual_dataset_missing_then_present(self, repo):
        access = {"type": "manual", "instructions": "Log in to GeoDS", "expect": ["AHAH*.csv"]}
        registry = {"ahah": _spec(access, theme="environment")}

        with pytest.raises(ManualDownloadRequired, match="Log in to GeoDS"):
            fetch("ahah", registry=registry)

        folder = repo / "data" / "manual" / "ahah"
        folder.mkdir(parents=True)
        (folder / "AHAH_V5_1.csv").write_text("lsoa21cd,ahah\n")
        fetched = fetch("ahah", registry=registry)
        assert list(fetched["files"]) == ["AHAH_V5_1.csv"]
        assert read_lock()["ahah"]["fetched"]["files"] == fetched["files"]

    def test_unknown_slug(self, repo):
        with pytest.raises(ValueError, match="Unknown dataset slug"):
            fetch("nope", registry={})


class TestSelect:
    REGISTRY = {
        "a": _spec({"type": "http", "url": "u"}),
        "b": _spec({"type": "http", "url": "u"}, theme="safety"),
        "c": _spec({"type": "http", "url": "u"}, theme="safety", priority="P1"),
    }

    def test_filters(self):
        assert select(self.REGISTRY) == ["a", "b", "c"]
        assert select(self.REGISTRY, theme="safety") == ["b", "c"]
        assert select(self.REGISTRY, priority="P1") == ["c"]
        assert select(self.REGISTRY, slugs=["a"]) == ["a"]

    def test_unknown_slug(self):
        with pytest.raises(ValueError, match="Unknown dataset slug"):
            select(self.REGISTRY, slugs=["zzz"])


def test_fetch_module_exports():
    # The CLI relies on these names
    for name in ("fetch", "resolve_and_lock", "check_link", "select", "ManualDownloadRequired"):
        assert hasattr(fetch_mod, name)

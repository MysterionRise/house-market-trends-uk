"""Tests for the download engine, against a local HTTP server."""

import hashlib
import io
import socket
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_socket import SocketConnectBlockedError
from werkzeug import Request, Response

from src.download import _read_meta, _safe_extract, _write_meta, download_dataset


def _zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.fixture
def project(tmp_path: Path):
    """Point the downloader at tmp_path and let each test supply its own registry."""
    registry: dict = {}
    with (
        patch("src.download.get_project_root", return_value=tmp_path),
        patch("src.download.get_config", return_value=registry),
    ):
        yield tmp_path, registry


class TestMetaRoundTrip:
    """Test .meta.json read/write cycle."""

    def test_write_and_read(self, tmp_path: Path):
        meta = {
            "slug": "test",
            "completed": True,
            "last_modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        }
        _write_meta(tmp_path, meta)

        loaded = _read_meta(tmp_path)
        assert loaded == meta

    def test_read_missing(self, tmp_path: Path):
        assert _read_meta(tmp_path) == {}

    def test_meta_file_location(self, tmp_path: Path):
        _write_meta(tmp_path, {"test": True})
        assert (tmp_path / ".meta.json").exists()


class TestSafeExtract:
    """Test ZIP extraction with path traversal protection."""

    def test_extracts_normal_zip(self, tmp_path: Path):
        data = _zip_bytes({"data.csv": "a,b\n1,2\n", "subdir/nested.txt": "hello"})
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            _safe_extract(zf, tmp_path)

        assert (tmp_path / "data.csv").exists()
        assert (tmp_path / "subdir" / "nested.txt").exists()

    def test_blocks_path_traversal(self, tmp_path: Path):
        data = _zip_bytes({"../../../etc/evil.txt": "malicious"})
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with pytest.raises(ValueError, match="outside destination"):
                _safe_extract(zf, tmp_path)

    def test_blocks_sibling_directory_with_same_prefix(self, tmp_path: Path):
        """'nspl_evil/' starts with 'nspl' as a string but is outside 'nspl/'."""
        dest = tmp_path / "nspl"
        dest.mkdir()
        data = _zip_bytes({"../nspl_evil/x.txt": "malicious"})
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with pytest.raises(ValueError, match="outside destination"):
                _safe_extract(zf, dest)
        assert not (tmp_path / "nspl_evil").exists()

    def test_extracts_only_matching_patterns(self, tmp_path: Path):
        data = _zip_bytes(
            {
                "Data/NSPL_AUG_2026_UK.csv": "pcds\n",
                "Data/NSPL_AUG_2026_UK.txt": "big duplicate",
                "Data/multi_csv/NSPL_AUG_2026_UK_AB.csv": "pcds\n",
                "Documents/LAD names.csv": "code,name\n",
            }
        )
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = _safe_extract(zf, tmp_path, ["Data/NSPL_*_UK.csv", "Documents/*.csv"])

        assert sorted(names) == ["Data/NSPL_AUG_2026_UK.csv", "Documents/LAD names.csv"]
        assert not (tmp_path / "Data" / "NSPL_AUG_2026_UK.txt").exists()
        assert not (tmp_path / "Data" / "multi_csv").exists()

    def test_no_matching_patterns_raises(self, tmp_path: Path):
        data = _zip_bytes({"other.csv": "x\n"})
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with pytest.raises(ValueError, match="No ZIP entries match"):
                _safe_extract(zf, tmp_path, ["Data/*.csv"])


class TestDownloadDataset:
    def test_skips_cached(self, project):
        root, registry = project
        registry["cached"] = {"download_url": "http://127.0.0.1:1/never", "format": "csv"}
        dest = root / "data" / "raw" / "cached"
        _write_meta(dest, {"completed": True})

        assert download_dataset("cached") == dest

    def test_downloads_csv_and_records_checksum(self, project, httpserver):
        root, registry = project
        body = b"col1,col2\nval1,val2\n"
        httpserver.expect_request("/test.csv").respond_with_data(
            body, headers={"Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT", "ETag": '"abc"'}
        )
        registry["test_csv"] = {"download_url": httpserver.url_for("/test.csv"), "format": "csv"}

        dest = download_dataset("test_csv")

        assert (dest / "test_csv.csv").read_bytes() == body
        meta = _read_meta(dest)
        assert meta["completed"] is True
        assert meta["bytes"] == len(body)
        assert meta["sha256"] == hashlib.sha256(body).hexdigest()
        assert meta["last_modified"] == "Mon, 01 Jan 2024 00:00:00 GMT"
        assert meta["etag"] == '"abc"'

    def test_downloads_and_extracts_zip(self, project, httpserver):
        root, registry = project
        httpserver.expect_request("/test.zip").respond_with_data(
            _zip_bytes({"data.csv": "a,b\n1,2\n"}), content_type="application/zip"
        )
        registry["test_zip"] = {"download_url": httpserver.url_for("/test.zip"), "format": "zip"}

        dest = download_dataset("test_zip")

        # ZIP should be extracted and deleted
        assert not (dest / "test_zip.zip").exists()
        assert (dest / "data.csv").read_text() == "a,b\n1,2\n"
        assert _read_meta(dest)["extracted"] == ["data.csv"]

    def test_follows_redirects(self, project, httpserver):
        """ONS Geoportal downloads redirect twice to a signed blob URL."""
        root, registry = project
        httpserver.expect_request("/start").respond_with_response(
            Response(status=302, headers={"Location": httpserver.url_for("/blob.gpkg")})
        )
        httpserver.expect_request("/blob.gpkg").respond_with_data(b"SQLite format 3\x00rest")
        registry["geo"] = {"download_url": httpserver.url_for("/start"), "format": "gpkg"}

        dest = download_dataset("geo")
        assert (dest / "geo.gpkg").read_bytes().startswith(b"SQLite format 3")

    def test_rejects_error_body_served_as_zip(self, project, httpserver):
        """ArcGIS answers deleted items with HTTP 200 and a JSON error body."""
        root, registry = project
        httpserver.expect_request("/gone").respond_with_json(
            {"error": {"code": 400, "message": "Item does not exist or is inaccessible."}}
        )
        registry["gone"] = {"download_url": httpserver.url_for("/gone"), "format": "zip"}

        with pytest.raises(ValueError, match="not a valid zip"):
            download_dataset("gone")

        dest = root / "data" / "raw" / "gone"
        # Neither the error body nor a .part file is kept; only the (incomplete) metadata
        assert [p.name for p in dest.iterdir()] == [".meta.json"]
        assert not _read_meta(dest).get("completed")

    def test_rejects_html_error_page_served_as_csv(self, project, httpserver):
        root, registry = project
        httpserver.expect_request("/page").respond_with_data(
            b"<!DOCTYPE html><html>Not found</html>", content_type="text/html"
        )
        registry["page"] = {"download_url": httpserver.url_for("/page"), "format": "csv"}

        with pytest.raises(ValueError, match="error page"):
            download_dataset("page")

    def test_unknown_slug_raises(self, project):
        with pytest.raises(ValueError, match="Unknown dataset slug"):
            download_dataset("nonexistent_dataset")

    def test_304_not_modified_updates_meta(self, project, httpserver):
        """HTTP 304 should skip download and mark as completed."""
        root, registry = project
        last_modified = "Mon, 01 Jan 2024 00:00:00 GMT"
        httpserver.expect_request(
            "/test.csv", headers={"If-Modified-Since": last_modified}
        ).respond_with_data(b"", status=304)
        registry["test_csv"] = {"download_url": httpserver.url_for("/test.csv"), "format": "csv"}
        dest = root / "data" / "raw" / "test_csv"
        _write_meta(dest, {"last_modified": last_modified})

        assert download_dataset("test_csv") == dest
        assert _read_meta(dest)["completed"] is True

    @staticmethod
    def _versioned_handler(body: bytes, etag: str, seen: list):
        """Serve ``body`` with an ETag, honouring Range only when If-Range matches it."""

        def handler(request: Request) -> Response:
            rng, if_range = request.headers.get("Range"), request.headers.get("If-Range")
            seen.append((rng, if_range))
            if rng and if_range == etag:
                start = int(rng.removeprefix("bytes=").split("-")[0])
                return Response(
                    body[start:],
                    status=206,
                    headers={
                        "Content-Range": f"bytes {start}-{len(body) - 1}/{len(body)}",
                        "ETag": etag,
                    },
                )
            return Response(body, headers={"ETag": etag})

        return handler

    def _interrupted(self, root, slug: str, partial: bytes, meta: dict) -> Path:
        """Simulate an earlier attempt that left ``partial`` bytes behind."""
        dest = root / "data" / "raw" / slug
        dest.mkdir(parents=True)
        (dest / f"{slug}.csv.part").write_bytes(partial)
        _write_meta(dest, {"completed": False, **meta})
        return dest

    def test_resumes_interrupted_download_with_range(self, project, httpserver):
        root, registry = project
        body = b"0123456789" * 1000
        seen = []
        handler = self._versioned_handler(body, '"v1"', seen)
        httpserver.expect_request("/big.csv").respond_with_handler(handler)
        registry["big"] = {"download_url": httpserver.url_for("/big.csv"), "format": "csv"}
        dest = self._interrupted(root, "big", body[:4000], {"partial_etag": '"v1"'})

        download_dataset("big")

        assert seen == [("bytes=4000-", '"v1"')]
        assert (dest / "big.csv").read_bytes() == body
        assert not (dest / "big.csv.part").exists()
        assert _read_meta(dest)["sha256"] == hashlib.sha256(body).hexdigest()

    def test_restarts_when_remote_file_changed(self, project, httpserver):
        """Appending a new version's bytes to an old partial would corrupt the file."""
        root, registry = project
        new_body = b"new,version\n" * 100
        seen = []
        handler = self._versioned_handler(new_body, '"v2"', seen)
        httpserver.expect_request("/f.csv").respond_with_handler(handler)
        registry["f"] = {"download_url": httpserver.url_for("/f.csv"), "format": "csv"}
        dest = self._interrupted(root, "f", b"old,version\n" * 50, {"partial_etag": '"v1"'})

        download_dataset("f")

        assert seen == [("bytes=600-", '"v1"')]
        assert (dest / "f.csv").read_bytes() == new_body

    def test_does_not_resume_without_validator(self, project, httpserver):
        root, registry = project
        body = b"a,b\n1,2\n"
        seen = []
        handler = self._versioned_handler(body, '"v1"', seen)
        httpserver.expect_request("/n.csv").respond_with_handler(handler)
        registry["n"] = {"download_url": httpserver.url_for("/n.csv"), "format": "csv"}
        dest = self._interrupted(root, "n", b"a,b\n", {})

        download_dataset("n")

        assert seen == [(None, None)]
        assert (dest / "n.csv").read_bytes() == body

    def test_interrupted_download_keeps_part_file_only(self, project, httpserver):
        """A failed transfer leaves a resumable .part file but nothing at the final path."""
        root, registry = project

        def handler(request: Request) -> Response:
            def stream():
                yield b"x" * 1024
                raise ConnectionError("connection lost")

            return Response(stream(), headers={"Content-Length": "1000000", "ETag": '"v1"'})

        httpserver.expect_request("/broken.csv").respond_with_handler(handler)
        registry["broken"] = {"download_url": httpserver.url_for("/broken.csv"), "format": "csv"}

        with pytest.raises(Exception):
            download_dataset("broken")

        dest = root / "data" / "raw" / "broken"
        assert not (dest / "broken.csv").exists()
        meta = _read_meta(dest)
        assert not meta.get("completed")
        # The validator is recorded so the next run can resume safely
        assert meta["partial_etag"] == '"v1"'


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_real_network_is_blocked():
    """Guard: pytest-socket must stop tests reaching the internet."""
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(("1.1.1.1", 443), timeout=2)

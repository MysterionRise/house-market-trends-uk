"""Tests for the download engine."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.download import _read_meta, _safe_extract, _write_meta, download_dataset


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
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("data.csv", "a,b\n1,2\n")
            zf.writestr("subdir/nested.txt", "hello")
        zip_buffer.seek(0)

        with zipfile.ZipFile(zip_buffer) as zf:
            _safe_extract(zf, tmp_path)

        assert (tmp_path / "data.csv").exists()
        assert (tmp_path / "subdir" / "nested.txt").exists()

    def test_blocks_path_traversal(self, tmp_path: Path):
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("../../../etc/evil.txt", "malicious")
        zip_buffer.seek(0)

        with zipfile.ZipFile(zip_buffer) as zf:
            with pytest.raises(ValueError, match="outside destination"):
                _safe_extract(zf, tmp_path)


class TestDownloadDataset:
    """Test download_dataset with mocked HTTP."""

    def test_skips_cached(self, tmp_path: Path):
        """Already-downloaded datasets should be skipped."""
        with patch("src.download.get_project_root", return_value=tmp_path):
            dest = tmp_path / "data" / "raw" / "nspl"
            dest.mkdir(parents=True)
            _write_meta(dest, {"completed": True})

            result = download_dataset("nspl", force=False)
            assert result == dest

    @patch("src.download.requests.get")
    def test_downloads_csv(self, mock_get, tmp_path: Path):
        """Test downloading a CSV file."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {
            "content-length": "100",
            "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        }
        mock_resp.iter_content.return_value = [b"col1,col2\nval1,val2\n"]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        test_config = {
            "test_csv": {
                "name": "Test CSV",
                "phase": 1,
                "download_url": "https://example.com/test.csv",
                "format": "csv",
            }
        }
        with (
            patch("src.download.get_project_root", return_value=tmp_path),
            patch("src.download.get_config", return_value=test_config),
        ):
            result = download_dataset("test_csv")

            assert result.exists()
            csv_file = result / "test_csv.csv"
            assert csv_file.exists()
            assert csv_file.read_bytes() == b"col1,col2\nval1,val2\n"

    @patch("src.download.requests.get")
    def test_downloads_and_extracts_zip(self, mock_get, tmp_path: Path):
        """Test downloading and extracting a ZIP file."""
        import io
        import zipfile

        # Create a ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("data.csv", "a,b\n1,2\n")
        zip_bytes = zip_buffer.getvalue()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-length": str(len(zip_bytes))}
        mock_resp.iter_content.return_value = [zip_bytes]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        test_config = {
            "test_zip": {
                "name": "Test ZIP",
                "phase": 1,
                "download_url": "https://example.com/test.zip",
                "format": "zip",
            }
        }
        with (
            patch("src.download.get_project_root", return_value=tmp_path),
            patch("src.download.get_config", return_value=test_config),
        ):
            result = download_dataset("test_zip")

            # ZIP should be extracted and deleted
            assert not (result / "test_zip.zip").exists()
            assert (result / "data.csv").exists()
            assert (result / "data.csv").read_text() == "a,b\n1,2\n"

    def test_unknown_slug_raises(self):
        """Unknown dataset slug should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown dataset slug"):
            download_dataset("nonexistent_dataset")

    @patch("src.download.requests.get")
    def test_304_not_modified_updates_meta(self, mock_get, tmp_path: Path):
        """HTTP 304 should skip download and mark as completed."""
        mock_resp = MagicMock()
        mock_resp.status_code = 304
        mock_get.return_value = mock_resp

        test_config = {
            "test_csv": {
                "name": "Test",
                "phase": 1,
                "download_url": "https://example.com/test.csv",
                "format": "csv",
            }
        }
        with (
            patch("src.download.get_project_root", return_value=tmp_path),
            patch("src.download.get_config", return_value=test_config),
        ):
            dest = tmp_path / "data" / "raw" / "test_csv"
            dest.mkdir(parents=True)
            _write_meta(
                dest, {"last_modified": "Mon, 01 Jan 2024 00:00:00 GMT"}
            )

            result = download_dataset("test_csv")
            assert result == dest

            # Verify meta now has completed=True
            meta = _read_meta(dest)
            assert meta["completed"] is True

    @patch("src.download.requests.get")
    def test_no_partial_file_on_failure(self, mock_get, tmp_path: Path):
        """Interrupted download should not leave partial files."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-length": "1000000"}
        mock_resp.iter_content.side_effect = ConnectionError("Connection lost")
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        test_config = {
            "test_csv": {
                "name": "Test",
                "phase": 1,
                "download_url": "https://example.com/test.csv",
                "format": "csv",
            }
        }
        with (
            patch("src.download.get_project_root", return_value=tmp_path),
            patch("src.download.get_config", return_value=test_config),
        ):
            with pytest.raises(ConnectionError):
                download_dataset("test_csv")

            # No CSV or .download temp files should remain
            dest = tmp_path / "data" / "raw" / "test_csv"
            csv_files = list(dest.glob("*.csv"))
            download_files = list(dest.glob("*.download"))
            assert csv_files == []
            assert download_files == []

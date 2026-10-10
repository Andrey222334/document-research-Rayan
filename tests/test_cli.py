from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app import cli


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "DocumentSearch 1.0.0"


def test_import_command(monkeypatch, capsys, tmp_path):
    importer = AsyncMock(return_value=42)
    monkeypatch.setattr(cli, "import_documents", importer)
    database = str(tmp_path / "documents.db")
    assert cli.main(["--database", database, "--index", "test-documents", "import", "posts.csv"]) == 0
    path, settings = importer.call_args.args
    assert path == Path("posts.csv")
    assert settings.database_path == database
    assert settings.index_name == "test-documents"
    assert "42" in capsys.readouterr().out


def test_import_error_returns_failure(monkeypatch, capsys):
    monkeypatch.setattr(cli, "import_documents", AsyncMock(side_effect=ValueError("bad csv")))
    assert cli.main(["import", "posts.csv"]) == 1
    assert "bad csv" in capsys.readouterr().err


def test_frozen_database_is_writable_user_path(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert cli.default_database_path() == str(tmp_path / "DocumentSearch" / "documents.db")
    monkeypatch.delenv("ELASTICSEARCH_INDEX", raising=False)
    assert cli.build_parser().parse_args([]).index == "documents-windows"

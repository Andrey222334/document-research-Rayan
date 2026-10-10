import json
from pathlib import Path

from app.main import app


def test_published_openapi_matches_api():
    assert json.loads(Path("docs.json").read_text(encoding="utf-8")) == app.openapi()

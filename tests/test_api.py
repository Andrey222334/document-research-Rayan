from datetime import datetime, timedelta, timezone
import sqlite3
from unittest.mock import AsyncMock

import httpx
import pytest
from elastic_transport import ConnectionError

from app.main import create_app, get_service
from app.models import Document
from app.repository import DocumentRepository
from app.service import DocumentService


class FakeIndex:
    """HTTP tests replace only Elasticsearch, keeping the real SQLite repository."""

    def __init__(self, batches):
        self.batches = batches
        self.ids = {i for batch in batches for i in batch}

    async def matching_batches(self, query):
        if query == "нетсовпадений":
            return
        for batch in self.batches:
            yield [i for i in batch if i in self.ids]

    async def delete(self, document_id):
        exists = document_id in self.ids
        self.ids.discard(document_id)
        return exists


@pytest.fixture
async def environment(tmp_path):
    repository = DocumentRepository(str(tmp_path / "documents.db"))
    await repository.initialize()
    documents = [Document(id=i, text="поиск Python", rubrics=["разработка"],
                          created_date=datetime(2020, 1, 1, tzinfo=timezone.utc)
                          + timedelta(days=i // 2)) for i in range(1, 46)]
    await repository.upsert(documents)
    index = FakeIndex([list(range(1, 26)), list(range(26, 46))])
    service = DocumentService(repository, index)
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                base_url="http://test") as client:
        yield client, repository, index, documents


async def test_global_date_order_and_all_fields(environment):
    client, _, _, documents = environment
    response = await client.get("/documents", params={"q": "Python"})
    assert response.status_code == 200
    expected = sorted(documents, key=lambda d: (-d.created_date.timestamp(), d.id))[:20]
    assert response.json() == [d.model_dump(mode="json") for d in expected]


async def test_no_matches(environment):
    client, *_ = environment
    assert (await client.get("/documents", params={"q": "нетсовпадений"})).json() == []


@pytest.mark.parametrize("query", [None, "", "   ", "x" * 10001])
async def test_invalid_query(environment, query):
    client, *_ = environment
    assert (await client.get("/documents", params={} if query is None else {"q": query})).status_code == 422


async def test_delete_both_storages(environment):
    client, repository, index, _ = environment
    response = await client.delete("/documents/45")
    assert response.status_code == 204
    assert response.content == b""
    assert await repository.newest([45]) == []
    assert 45 not in index.ids
    assert (await client.delete("/documents/45")).status_code == 404
    assert all(d["id"] != 45 for d in (await client.get("/documents?q=Python")).json())


async def test_index_outage_preserves_database(environment):
    client, repository, index, _ = environment
    index.delete = AsyncMock(side_effect=ConnectionError("offline"))
    assert (await client.delete("/documents/45")).status_code == 503
    assert len(await repository.newest([45])) == 1


async def test_delete_recovers_missing_index_entry(environment):
    client, repository, index, _ = environment
    index.ids.remove(45)
    assert (await client.delete("/documents/45")).status_code == 204
    assert await repository.newest([45]) == []


async def test_retry_after_database_failure(environment):
    client, repository, index, _ = environment
    original_delete = repository.delete
    repository.delete = AsyncMock(side_effect=sqlite3.OperationalError("locked"))
    assert (await client.delete("/documents/45")).status_code == 503
    assert 45 not in index.ids
    assert len(await repository.newest([45])) == 1
    repository.delete = original_delete
    assert (await client.delete("/documents/45")).status_code == 204
    assert await repository.newest([45]) == []


@pytest.mark.parametrize("document_id", [0, -1, "abc"])
async def test_invalid_id(environment, document_id):
    client, *_ = environment
    assert (await client.delete(f"/documents/{document_id}")).status_code == 422

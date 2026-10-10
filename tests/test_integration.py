import os
from uuid import uuid4

import httpx
import pytest
from elasticsearch import AsyncElasticsearch

from app.config import Settings
from app.import_csv import import_documents
from app.main import create_app


@pytest.mark.integration
async def test_real_import_search_delete(tmp_path):
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("Set RUN_INTEGRATION=1 to test real Elasticsearch")
    settings = Settings(str(tmp_path / "test.db"),
                        os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
                        "test-" + uuid4().hex)
    csv_path = tmp_path / "posts.csv"
    csv_path.write_text("text,created_date,rubrics\n"
                        "Кошка спит,2020-01-01,['animals']\n"
                        "Кошки играют,2021-01-01,['animals']\n"
                        "Собака бежит,2022-01-01,['animals']\n", encoding="utf-8")
    async with AsyncElasticsearch(settings.elasticsearch_url) as elastic:
        try:
            assert await import_documents(csv_path, settings) == 3
            assert await import_documents(csv_path, settings) == 3
            assert (await elastic.count(index=settings.index_name))["count"] == 3
            app = create_app(settings)
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.get("/documents", params={"q": "кошка"})
                    assert response.status_code == 200
                    assert [d["id"] for d in response.json()] == [2, 1]
                    assert (await client.delete("/documents/2")).status_code == 204
                    assert not await elastic.exists(index=settings.index_name, id="2")
                    assert [d["id"] for d in (await client.get("/documents?q=кошка")).json()] == [1]
                    assert (await client.delete("/documents/2")).status_code == 404
                    assert (await client.get("/documents?q=несуществующий")).json() == []
        finally:
            await elastic.indices.delete(index=settings.index_name, ignore_unavailable=True)

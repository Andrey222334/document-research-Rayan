from collections.abc import AsyncIterator

from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk, async_scan

from app.models import Document


class SearchIndex:
    def __init__(self, client: AsyncElasticsearch, name: str):
        self.client = client
        self.name = name

    async def initialize(self) -> None:
        if not await self.client.indices.exists(index=self.name):
            await self.client.indices.create(index=self.name, mappings={
                "dynamic": "strict",
                "properties": {
                    "id": {"type": "long"},
                    "text": {"type": "text", "analyzer": "russian"},
                },
            })

    async def matching_batches(self, query: str) -> AsyncIterator[list[int]]:
        batch: list[int] = []
        # Scroll обходит лимит выдачи в 10 000 записей. Даты хранятся только в SQLite.
        async for hit in async_scan(
            self.client, index=self.name, size=500,
            query={"query": {"match": {"text": query}}, "_source": ["id"]},
        ):
            batch.append(hit["_source"]["id"])
            if len(batch) == 500:
                yield batch
                batch = []
        if batch:
            yield batch

    async def upsert(self, documents: list[Document]) -> None:
        await async_bulk(self.client, [
            {"_index": self.name, "_id": d.id, "_source": {"id": d.id, "text": d.text}}
            for d in documents
        ])

    async def delete(self, document_id: int) -> bool:
        try:
            await self.client.delete(index=self.name, id=str(document_id), refresh="wait_for")
            return True
        except NotFoundError:
            return False

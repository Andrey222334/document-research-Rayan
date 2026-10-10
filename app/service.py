from app.models import Document
from app.repository import DocumentRepository
from app.search import SearchIndex


class DocumentService:
    def __init__(self, repository: DocumentRepository, index: SearchIndex):
        self.repository = repository
        self.index = index

    async def search(self, query: str) -> list[Document]:
        result: list[Document] = []
        async for ids in self.index.matching_batches(query):
            result.extend(await self.repository.newest(ids))
            # Оставляем глобальные 20 самых новых после каждой порции совпадений.
            result.sort(key=lambda document: document.id)
            result.sort(key=lambda document: document.created_date, reverse=True)
            result = result[:20]
        return result

    async def delete(self, document_id: int) -> bool:
        # Сначала индекс: при отказе Elasticsearch исходный документ не теряется.
        # При последующем отказе SQLite повторный запрос удалит оставшуюся строку.
        indexed = await self.index.delete(document_id)
        stored = await self.repository.delete(document_id)
        return indexed or stored

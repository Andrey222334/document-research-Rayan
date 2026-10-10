import logging
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from elasticsearch import ApiError, AsyncElasticsearch
from elastic_transport import TransportError
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse

from app.config import Settings
from app.models import Document
from app.repository import DocumentRepository
from app.search import SearchIndex
from app.service import DocumentService

logger = logging.getLogger(__name__)


def get_service(request: Request) -> DocumentService:
    return request.app.state.service


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        async with AsyncElasticsearch(settings.elasticsearch_url, request_timeout=30) as client:
            repository = DocumentRepository(settings.database_path)
            index = SearchIndex(client, settings.index_name)
            await repository.initialize()
            await index.initialize()
            application.state.service = DocumentService(repository, index)
            yield

    application = FastAPI(
        title="Document Search", version="1.0.0", lifespan=lifespan,
        description="Поиск по текстам документов и удаление из SQLite и Elasticsearch.",
    )

    async def unavailable(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Storage request failed", exc_info=exc)
        return JSONResponse(status_code=503, content={"detail": "Хранилище временно недоступно"})

    for exception in (ApiError, TransportError, sqlite3.Error):
        application.add_exception_handler(exception, unavailable)

    @application.get("/documents", response_model=list[Document],
                     responses={503: {"description": "Хранилище недоступно"}})
    async def search_documents(
        service: Annotated[DocumentService, Depends(get_service)],
        q: Annotated[str, Query(min_length=1, max_length=10000,
                               description="Полнотекстовый запрос")],
    ) -> list[Document]:
        """Вернуть до 20 совпадений: новые первыми, при равной дате — по id."""
        if not q.strip():
            raise HTTPException(status_code=422, detail="Запрос не должен быть пустым")
        return await service.search(q.strip())

    @application.delete("/documents/{document_id}", status_code=204,
                        responses={404: {"description": "Документ не найден"},
                                   503: {"description": "Хранилище недоступно"}})
    async def delete_document(
        document_id: Annotated[int, Path(gt=0)],
        service: Annotated[DocumentService, Depends(get_service)],
    ) -> Response:
        """Удалить документ из обоих хранилищ."""
        if not await service.delete(document_id):
            raise HTTPException(status_code=404, detail="Документ не найден")
        return Response(status_code=204)

    return application


app = create_app()

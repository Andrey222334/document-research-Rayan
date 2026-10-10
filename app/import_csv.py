"""Run with python -m app.import_csv data/posts.csv."""

import argparse
import ast
import asyncio
import csv
from datetime import datetime, timezone
from pathlib import Path

from elasticsearch import AsyncElasticsearch

from app.config import Settings
from app.models import Document
from app.repository import DocumentRepository
from app.search import SearchIndex


def read_documents(path: Path) -> list[Document]:
    documents = []
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"text", "rubrics", "created_date"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"CSV must contain: {', '.join(sorted(required))}")
        for document_id, row in enumerate(reader, start=1):
            try:
                # В CSV рубрики записаны как Python-список. eval выполнять нельзя.
                rubrics = ast.literal_eval(row["rubrics"])
                if not isinstance(rubrics, list) or not all(isinstance(r, str) for r in rubrics):
                    raise ValueError("rubrics must be a list of strings")
                date = datetime.fromisoformat(row["created_date"])
                # Даты без пояса считаем UTC, чтобы сортировать их единообразно.
                date = (date.replace(tzinfo=timezone.utc) if date.tzinfo is None
                        else date.astimezone(timezone.utc))
                documents.append(Document(id=document_id, rubrics=rubrics,
                                          text=row["text"], created_date=date))
            except (ValueError, TypeError, SyntaxError) as exc:
                raise ValueError(f"Invalid CSV record {document_id}: {exc}") from exc
    return documents


async def import_documents(path: Path, settings: Settings) -> int:
    # Проверяем весь файл до внесения изменений в хранилища.
    documents = await asyncio.to_thread(read_documents, path)
    repository = DocumentRepository(settings.database_path)
    await repository.initialize()
    async with AsyncElasticsearch(settings.elasticsearch_url, request_timeout=30) as client:
        index = SearchIndex(client, settings.index_name)
        await index.initialize()
        for offset in range(0, len(documents), 500):
            batch = documents[offset:offset + 500]
            await repository.upsert(batch)
            await index.upsert(batch)
        await client.indices.refresh(index=settings.index_name)
    return len(documents)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the supplied document CSV")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    count = asyncio.run(import_documents(args.path, Settings.from_env()))
    print(f"Imported {count} documents")


if __name__ == "__main__":
    main()

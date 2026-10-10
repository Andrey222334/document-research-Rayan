"""Команды для запуска API и импорта без установленного Python."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

from app.config import Settings
from app.import_csv import import_documents
from app.main import create_app

VERSION = "1.0.0"


def default_database_path() -> str:
    if getattr(sys, "frozen", False):
        # EXE может лежать в защищённой папке; изменяемые данные храним у пользователя.
        root = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "DocumentSearch"
        return str(root / "documents.db")
    return "data/documents.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Поиск по документам — API и импорт CSV")
    parser.add_argument("--version", action="version", version=f"DocumentSearch {VERSION}")
    parser.add_argument("--database", default=os.getenv("DATABASE_PATH", default_database_path()),
                        help="Путь к SQLite")
    parser.add_argument("--elasticsearch-url", default=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
                        help="Адрес Elasticsearch")
    default_index = "documents-windows" if getattr(sys, "frozen", False) else "documents"
    parser.add_argument("--index", default=os.getenv("ELASTICSEARCH_INDEX", default_index),
                        help="Имя поискового индекса")
    commands = parser.add_subparsers(dest="command")
    serve = commands.add_parser("serve", help="Запустить API (команда по умолчанию)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    importer = commands.add_parser("import", help="Загрузить CSV в SQLite и индекс")
    importer.add_argument("path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    # На Windows консоль может использовать cp1251. UTF-8 нужен и для логов, и для CSV.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    settings = Settings(args.database, args.elasticsearch_url, args.index)
    try:
        if args.command == "import":
            count = asyncio.run(import_documents(args.path, settings))
            print(f"Загружено документов: {count}")
        else:
            uvicorn.run(create_app(settings), host=getattr(args, "host", "127.0.0.1"),
                        port=getattr(args, "port", 8000), loop="asyncio", http="h11", ws="none")
    except Exception as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

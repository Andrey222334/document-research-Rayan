"""Environment configuration shared by the API and the importer."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_path: str = "data/documents.db"
    elasticsearch_url: str = "http://localhost:9200"
    index_name: str = "documents"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=os.getenv("DATABASE_PATH", "data/documents.db"),
            elasticsearch_url=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
            index_name=os.getenv("ELASTICSEARCH_INDEX", "documents"),
        )

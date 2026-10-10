from datetime import datetime

from pydantic import BaseModel


class Document(BaseModel):
    id: int
    rubrics: list[str]
    text: str
    created_date: datetime

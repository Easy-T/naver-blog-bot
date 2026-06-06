from pathlib import Path

from pydantic import BaseModel


class PhotoCaption(BaseModel):
    path: Path
    caption: str = ""
    category: str = "기타"

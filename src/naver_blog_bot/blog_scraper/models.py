from typing import Literal

from pydantic import BaseModel


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    content: str


class ImageBlock(BaseModel):
    type: Literal["image"] = "image"
    alt: str = ""
    src: str = ""


class EmoticonBlock(BaseModel):
    type: Literal["emoticon"] = "emoticon"
    description: str = ""


PostBlock = TextBlock | ImageBlock | EmoticonBlock


class PostDocument(BaseModel):
    url: str
    title: str = ""
    blocks: list[PostBlock]

    def to_structured_text(self) -> str:
        lines: list[str] = []
        if self.title:
            lines += [f"제목: {self.title}", ""]
        for block in self.blocks:
            if block.type == "text":
                stripped = block.content.strip()
                if stripped:
                    lines.append(stripped)
            elif block.type == "image":
                lines.append("[이미지]")
            elif block.type == "emoticon":
                description = f":{block.description}" if block.description else ""
                lines.append(f"[이모티콘{description}]")
        return "\n".join(lines)

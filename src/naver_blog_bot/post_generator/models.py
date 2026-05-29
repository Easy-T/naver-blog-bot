import html as _html
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class Draft(BaseModel):
    id: str
    title: str
    memo: str
    body_markdown: str
    photo_paths: list[Path]
    selected_memes: list[Path] = Field(default_factory=list)
    ogq_artwork_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def preview_text(self) -> str:
        photos = "\n".join(f"- {path}" for path in self.photo_paths) or "- (none)"
        memes = "\n".join(f"- {path}" for path in self.selected_memes) or "- (none)"
        ogq = self.ogq_artwork_id or "(none)"
        return (
            f"# {self.title}\n\n"
            f"Draft ID: {self.id}\n\n"
            f"Created: {self.created_at.isoformat()}\n\n"
            f"Memo: {self.memo}\n\n"
            f"Photos:\n{photos}\n\n"
            f"OGQ: {ogq}\n\n"
            f"Memes:\n{memes}\n\n"
            f"---\n\n"
            f"{self.body_markdown}\n"
        )

    def to_html(self) -> str:
        lines: list[str] = []
        for line in self.body_markdown.splitlines():
            stripped = line.strip()
            if not stripped:
                lines.append("<br>")
                continue
            if stripped.startswith("[사진:"):
                path = stripped[4:-1].strip()
                lines.append(
                    f'<div class="photo-placeholder">📷 {_html.escape(path)}</div>'
                )
            elif stripped.startswith("[짤방:"):
                ref = stripped[4:-1].strip()
                lines.append(
                    f'<div class="meme-placeholder">🖼️ 짤방: {_html.escape(ref)}</div>'
                )
            elif stripped.startswith("### "):
                lines.append(f"<h3>{_html.escape(stripped[4:])}</h3>")
            elif stripped.startswith("## "):
                lines.append(f"<h2>{_html.escape(stripped[3:])}</h2>")
            elif stripped.startswith("# "):
                lines.append(f"<h1>{_html.escape(stripped[2:])}</h1>")
            else:
                processed = re.sub(
                    r"\{\{이모티콘:([^}]+)\}\}",
                    lambda m: (
                        f'<span class="emoticon-badge">😊 {_html.escape(m.group(1))}</span>'
                    ),
                    _html.escape(line),
                )
                lines.append(f"<p>{processed}</p>")

        body_html = "\n".join(lines)
        escaped_title = _html.escape(self.title)
        escaped_memo = _html.escape(self.memo)
        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{escaped_title}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap" rel="stylesheet">
<style>
body{{font-family:'Noto Sans KR',sans-serif;background:#f5f5f5;margin:0;padding:20px}}
.post{{max-width:720px;margin:0 auto;background:#fff;padding:40px;border-radius:8px}}
.meta{{color:#888;font-size:13px;margin-bottom:20px;border-bottom:1px solid #eee;padding-bottom:16px}}
.photo-placeholder{{background:#e0e0e0;border:2px dashed #bbb;padding:30px;text-align:center;margin:16px 0;border-radius:4px;color:#666}}
.meme-placeholder{{background:#fff3e0;border:2px dashed #ffb74d;padding:20px;text-align:center;margin:16px 0;border-radius:4px;color:#e65100}}
.emoticon-badge{{background:#fff9c4;border:1px solid #f9a825;border-radius:12px;padding:2px 8px;font-size:13px}}
h1{{font-size:24px}}h2{{font-size:20px}}h3{{font-size:17px}}
p{{line-height:1.8;margin:8px 0}}
</style>
</head>
<body>
<div class="post">
<div class="meta">
  <strong>{escaped_title}</strong><br>
  Draft ID: {_html.escape(self.id)}<br>
  Created: {self.created_at.isoformat()}<br>
  Memo: {escaped_memo}
</div>
{body_html}
</div>
</body>
</html>"""

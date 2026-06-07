from pydantic import BaseModel, Field

from naver_blog_bot.meme_library.models import MemeAsset


class HarvestResult(BaseModel):
    assets: list[MemeAsset] = Field(default_factory=list)
    meme_srcs: list[str] = Field(default_factory=list)

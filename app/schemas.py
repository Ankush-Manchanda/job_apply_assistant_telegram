from pydantic import BaseModel


class SourceCreate(BaseModel):
    name: str
    source_type: str = "rss"
    url: str
    enabled: bool = True
    selector: str = ""
    title_selector: str = ""
    link_selector: str = ""
    location_hint: str = ""


class StatusUpdate(BaseModel):
    status: str


class ApplyUpdate(BaseModel):
    resume_id: int | None = None
    notes: str = ""

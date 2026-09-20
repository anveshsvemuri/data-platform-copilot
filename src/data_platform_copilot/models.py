from pydantic import BaseModel, Field


class Citation(BaseModel):
    source: str
    excerpt: str
    score: float = Field(ge=0, le=1)


class CopilotAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    grounded: bool
    mode: str


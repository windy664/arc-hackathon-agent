from pydantic import BaseModel, Field


class ModuleSummary(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: str = "ready"


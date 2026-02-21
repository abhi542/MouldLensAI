from pydantic import BaseModel, Field
from datetime import datetime

class LLMExtraction(BaseModel):
    cope: str | None = Field(default=None, description="The cope number from the upper mould section. Example: '81373'")
    drag_main: str | None = Field(default=None, description="The main drag number from the lower mould section. Example: '88234'")
    drag_sub: str | None = Field(default=None, description="The optional bracket value in the drag section, if present. Example: '644'")

class DragValue(BaseModel):
    main: str = Field(..., description="The main drag number")
    sub: str | None = Field(default=None, description="The optional bracket value in the drag section, if present")

class MouldReading(BaseModel):
    cope: str | None = Field(default=None, description="The cope number from the upper mould section")
    drag: DragValue | None = Field(default=None, description="The drag value from the lower mould section")

class MouldReadingResponse(MouldReading):
    mould_detected: bool = Field(default=True, description="Flag indicating if text/digits were visually detected in the image")
    scan_time_ms: float = Field(..., description="Time taken to process the image in milliseconds")
    timestamp: datetime = Field(..., description="Timestamp of the extraction")

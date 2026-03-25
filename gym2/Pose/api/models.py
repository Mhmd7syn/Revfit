from pydantic import BaseModel
from typing import Dict, List, Optional, Any


class FeedbackItem(BaseModel):
    message: str
    occurrence_count: int
    metric_type: str  # 'angle' or distance type
    avg_value: Optional[float] = None


class AnalysisResult(BaseModel):
    session_id: str
    exercise_name: str
    total_frames: int
    bad_frames: int
    rep_count: int
    good_form_percent: float
    feedbacks: List[FeedbackItem]
    annotated_video_url: str   # relative URL to download endpoint
    status: str = "completed"


class ExerciseListResponse(BaseModel):
    exercises: List[str]
    total: int


class ErrorResponse(BaseModel):
    detail: str
    status: str = "error"

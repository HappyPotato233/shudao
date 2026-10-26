"""考试工坊 Schema。"""
from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    type: str
    content: str = Field(..., max_length=2000)
    options: dict[str, str] | None = None
    answer: str
    explanation: str = ""
    score: float = 2
    difficulty: str = "easy"
    category_id: int | None = None
    tags: list[str] = Field(default_factory=list)


class QuestionUpdate(BaseModel):
    content: str | None = None
    options: dict[str, str] | None = None
    answer: str | None = None
    explanation: str | None = None
    score: float | None = None
    difficulty: str | None = None
    category_id: int | None = None
    tags: list[str] | None = None


class DuplicateCheckRequest(BaseModel):
    content: str


class QuestionReviewRequest(BaseModel):
    action: str
    comment: str | None = None
    edited_content: dict | None = None


class BatchReviewRequest(BaseModel):
    question_ids: list[int]
    action: str
    comment: str | None = None


class PaperQuestionInput(BaseModel):
    question_id: int
    score: float
    order: int


class PaperConfig(BaseModel):
    duration: int
    pass_score: float
    total_score: float
    shuffle_questions: bool = False
    shuffle_options: bool = False
    anti_cheat: bool = False
    max_switch_count: int = 3
    allow_retake: bool = False
    max_retake_count: int = 1
    start_time: str
    end_time: str


class PaperAssignees(BaseModel):
    type: str
    ids: list[str] = Field(default_factory=list)


class PaperCreate(BaseModel):
    title: str
    description: str | None = None
    mode: str
    questions: list[PaperQuestionInput] = Field(default_factory=list)
    strategy: dict | None = None
    config: PaperConfig
    assignees: PaperAssignees


class AiGenerateRequest(BaseModel):
    mode: str = "knowledge"
    knowledge_points: list[str] = Field(default_factory=list)
    topic: str | None = None
    document_id: int | None = None
    types: list[str] = Field(default_factory=list)
    count: int = Field(..., ge=1, le=50)
    difficulty: str = "mixed"
    use_knowledge_base: bool = True
    include_basis: bool = False


class AnswerSaveRequest(BaseModel):
    question_index: int
    answer: str | None = None


class BatchAnswerRequest(BaseModel):
    answers: list[AnswerSaveRequest]


class MarkRequest(BaseModel):
    marked: bool


class SwitchEventRequest(BaseModel):
    timestamp: str | None = None

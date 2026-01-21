"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class ContestStatusEnum(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SubmissionStatusEnum(str, Enum):
    PENDING = "pending"
    SOLVED = "solved"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# User Schemas
# =============================================================================

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None


class TopicRatingResponse(BaseModel):
    topic: str
    rating: int
    problems_solved: int
    problems_attempted: int

    model_config = ConfigDict(from_attributes=True)


class WeakTopicResponse(BaseModel):
    id: int
    topic: str
    current_level: int
    target_level: int
    consecutive_solves: int
    total_attempts: int
    total_failures: int
    detected_at: datetime
    last_attempt_at: Optional[datetime]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    rating: int
    total_contests: int
    total_problems_solved: int
    total_problems_attempted: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserDetailResponse(UserResponse):
    topic_ratings: List[TopicRatingResponse] = []
    weak_topics: List[WeakTopicResponse] = []


# =============================================================================
# Contest Schemas
# =============================================================================

class ContestCreate(BaseModel):
    num_problems: int = Field(default=5, ge=3, le=10)
    time_limit_minutes: int = Field(default=120, ge=30, le=300)
    include_weak_topics: bool = Field(default=True)


class ContestProblemResponse(BaseModel):
    id: int
    problem_id: str
    problem_name: str
    problem_url: Optional[str]
    topic: str
    difficulty: int
    source: str
    is_weak_topic_problem: bool
    status: SubmissionStatusEnum
    started_at: Optional[datetime]
    submitted_at: Optional[datetime]
    time_taken_seconds: Optional[int]
    attempts: int

    model_config = ConfigDict(from_attributes=True)


class ContestResponse(BaseModel):
    id: int
    user_id: int
    status: ContestStatusEnum
    rating_at_start: int
    rating_change: int
    num_problems: int
    target_difficulty: int
    started_at: datetime
    ended_at: Optional[datetime]
    time_limit_minutes: int
    problems_solved: int
    total_time_seconds: int

    model_config = ConfigDict(from_attributes=True)


class ContestDetailResponse(ContestResponse):
    problems: List[ContestProblemResponse] = []


# =============================================================================
# Submission Schemas
# =============================================================================

class ProblemSubmission(BaseModel):
    problem_id: str
    solved: bool
    time_taken_seconds: Optional[int] = None


class ContestSubmission(BaseModel):
    submissions: List[ProblemSubmission]


class SubmissionResponse(BaseModel):
    contest_id: int
    problem_id: str
    status: SubmissionStatusEnum
    time_taken_seconds: Optional[int]
    message: str


# =============================================================================
# Contest Result Schemas
# =============================================================================

class ProblemResult(BaseModel):
    problem_id: str
    problem_name: str
    topic: str
    difficulty: int
    solved: bool
    time_taken_seconds: Optional[int]
    is_weak_topic_problem: bool


class ContestResult(BaseModel):
    contest_id: int
    status: ContestStatusEnum
    problems_solved: int
    total_problems: int
    total_time_seconds: int

    # Rating changes
    old_rating: int
    new_rating: int
    rating_change: int

    # Topic analysis
    topics_passed: List[str]
    topics_failed: List[str]
    new_weak_topics: List[str]
    weak_topics_improved: List[str]

    # Problem details
    problems: List[ProblemResult]


# =============================================================================
# Statistics Schemas
# =============================================================================

class UserStatistics(BaseModel):
    user_id: int
    username: str
    rating: int
    rating_history: List[Dict[str, Any]]  # [{date, rating, change}]
    topic_distribution: Dict[str, int]  # {topic: problems_solved}
    weak_topics_count: int
    average_solve_time: Optional[float]
    contests_completed: int
    win_rate: float  # Percentage of contests with all problems solved


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    rating: int
    total_problems_solved: int

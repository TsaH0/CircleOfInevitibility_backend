"""
SQLAlchemy database models for the contest system.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey,
    Text, JSON, Enum as SQLEnum, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from .database import Base


class ContestStatus(enum.Enum):
    """Contest status enum."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SubmissionStatus(enum.Enum):
    """Submission status enum."""
    PENDING = "pending"
    SOLVED = "solved"
    FAILED = "failed"
    SKIPPED = "skipped"


class User(Base):
    """User model with overall rating."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, nullable=True)

    # Overall rating (starts at 20, on 1-100 scale matching internal problem ratings)
    # 1-25: Beginner, 26-50: Intermediate, 51-75: Advanced, 76-100: Expert
    rating = Column(Integer, default=20, nullable=False)

    # Statistics
    total_contests = Column(Integer, default=0)
    total_problems_solved = Column(Integer, default=0)
    total_problems_attempted = Column(Integer, default=0)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    topic_ratings = relationship("UserTopicRating", back_populates="user", cascade="all, delete-orphan")
    weak_topics = relationship("WeakTopic", back_populates="user", cascade="all, delete-orphan")
    contests = relationship("Contest", back_populates="user", cascade="all, delete-orphan")


class UserTopicRating(Base):
    """Per-topic rating for a user."""
    __tablename__ = "user_topic_ratings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Topic identifier (e.g., "dp_general", "graph_traversal")
    topic = Column(String(100), nullable=False, index=True)

    # Topic-specific rating (1-100 scale)
    rating = Column(Integer, default=20, nullable=False)

    # Statistics for this topic
    problems_solved = Column(Integer, default=0)
    problems_attempted = Column(Integer, default=0)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="topic_ratings")

    __table_args__ = (
        UniqueConstraint("user_id", "topic", name="unique_user_topic"),
        Index("idx_user_topic", "user_id", "topic"),
    )


class WeakTopic(Base):
    """Tracks weak topics that need reinforcement."""
    __tablename__ = "weak_topics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Topic identifier
    topic = Column(String(100), nullable=False, index=True)

    # Current difficulty level being practiced (starts lower than user's rating)
    current_level = Column(Integer, nullable=False)

    # Target level (user's rating + 10 at time of weakness detection)
    target_level = Column(Integer, nullable=False)

    # Tracking
    consecutive_solves = Column(Integer, default=0)  # Solves at current level
    total_attempts = Column(Integer, default=0)
    total_failures = Column(Integer, default=0)

    # Timestamps
    detected_at = Column(DateTime, default=func.now())
    last_attempt_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Is this weakness still active?
    is_active = Column(Boolean, default=True, index=True)

    # Relationships
    user = relationship("User", back_populates="weak_topics")

    __table_args__ = (
        UniqueConstraint("user_id", "topic", "is_active", name="unique_active_weak_topic"),
        Index("idx_user_weak_topic", "user_id", "is_active"),
    )


class Contest(Base):
    """A practice contest for a user."""
    __tablename__ = "contests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Contest metadata
    status = Column(SQLEnum(ContestStatus), default=ContestStatus.ACTIVE, nullable=False)

    # Rating snapshot at contest start
    rating_at_start = Column(Integer, nullable=False)
    rating_change = Column(Integer, default=0)

    # Problem configuration
    num_problems = Column(Integer, default=5)
    target_difficulty = Column(Integer, nullable=False)  # User rating + 10

    # Timing
    started_at = Column(DateTime, default=func.now())
    ended_at = Column(DateTime, nullable=True)
    time_limit_minutes = Column(Integer, default=120)  # 2 hours default

    # Results
    problems_solved = Column(Integer, default=0)
    total_time_seconds = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="contests")
    problems = relationship("ContestProblem", back_populates="contest", cascade="all, delete-orphan")


class ContestProblem(Base):
    """A problem assigned to a contest."""
    __tablename__ = "contest_problems"

    id = Column(Integer, primary_key=True, index=True)
    contest_id = Column(Integer, ForeignKey("contests.id", ondelete="CASCADE"), nullable=False)

    # Problem reference (from standardized_problems.json)
    problem_id = Column(String(100), nullable=False, index=True)
    problem_name = Column(String(255), nullable=False)
    problem_url = Column(String(500), nullable=True)

    # Problem metadata
    topic = Column(String(100), nullable=False, index=True)  # Primary topic/pattern
    difficulty = Column(Integer, nullable=False)  # Internal rating
    source = Column(String(50), nullable=False)  # codeforces, atcoder, usaco_guide

    # Is this from a weak topic?
    is_weak_topic_problem = Column(Boolean, default=False)

    # Submission status
    status = Column(SQLEnum(SubmissionStatus), default=SubmissionStatus.PENDING, nullable=False)

    # Timing
    started_at = Column(DateTime, nullable=True)  # When user first viewed
    submitted_at = Column(DateTime, nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)

    # Attempts
    attempts = Column(Integer, default=0)

    # Relationships
    contest = relationship("Contest", back_populates="problems")
    reflection = relationship("ProblemReflection", back_populates="contest_problem", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_contest_problem", "contest_id", "problem_id"),
    )


class ProblemHistory(Base):
    """Tracks all problems a user has attempted (for deduplication)."""
    __tablename__ = "problem_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    problem_id = Column(String(100), nullable=False, index=True)

    # Last attempt info
    last_attempted_at = Column(DateTime, default=func.now())
    times_attempted = Column(Integer, default=1)
    times_solved = Column(Integer, default=0)
    best_time_seconds = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "problem_id", name="unique_user_problem"),
        Index("idx_user_problem_history", "user_id", "problem_id"),
    )


class ProblemReflection(Base):
    """AI-generated reflection for a contest problem (Divine Rite of Reflection)."""
    __tablename__ = "problem_reflections"

    id = Column(Integer, primary_key=True, index=True)
    contest_problem_id = Column(Integer, ForeignKey("contest_problems.id", ondelete="CASCADE"), nullable=False, unique=True)

    # User-provided editorial (can be text or URL)
    editorial_text = Column(Text, nullable=True)
    editorial_url = Column(String(500), nullable=True)

    # AI-generated reflection content
    pivot_sentence = Column(Text, nullable=True)  # The key insight of the problem
    tips = Column(Text, nullable=True)  # Tips for similar problems
    what_to_improve = Column(Text, nullable=True)  # What could have been done differently
    master_approach = Column(Text, nullable=True)  # How "The Circle of Inevitability" would approach

    # Full response stored as text for future reference
    full_response = Column(Text, nullable=True)

    # Metadata
    model_used = Column(String(100), nullable=True)
    generated_at = Column(DateTime, default=func.now())
    generation_error = Column(Text, nullable=True)  # Store any errors

    # Relationship
    contest_problem = relationship("ContestProblem", back_populates="reflection")

    __table_args__ = (
        Index("idx_reflection_contest_problem", "contest_problem_id"),
    )

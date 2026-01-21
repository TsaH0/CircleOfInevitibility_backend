"""
User management API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import User, UserTopicRating, WeakTopic
from ..schemas import (
    UserCreate, UserUpdate, UserResponse, UserDetailResponse,
    TopicRatingResponse, WeakTopicResponse, UserStatistics
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user."""
    # Check if username exists
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user.username}' already exists"
        )

    # Check if email exists (if provided)
    if user.email:
        existing_email = db.query(User).filter(User.email == user.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{user.email}' already exists"
            )

    db_user = User(
        username=user.username,
        email=user.email,
        rating=20,  # Starting rating (1-100 scale, beginner level)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@router.get("/", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all users."""
    users = db.query(User).order_by(User.rating.desc()).offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=UserDetailResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user details including topic ratings and weak topics."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    return user


@router.get("/by-username/{username}", response_model=UserDetailResponse)
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """Get user details by username."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found"
        )

    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    """Update user details."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    if user_update.email is not None:
        # Check if email is taken by another user
        existing = db.query(User).filter(
            User.email == user_update.email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{user_update.email}' already in use"
            )
        user.email = user_update.email

    db.commit()
    db.refresh(user)

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    db.delete(user)
    db.commit()


@router.get("/{user_id}/topic-ratings", response_model=List[TopicRatingResponse])
def get_user_topic_ratings(user_id: int, db: Session = Depends(get_db)):
    """Get user's ratings for all topics."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    return user.topic_ratings


@router.get("/{user_id}/weak-topics", response_model=List[WeakTopicResponse])
def get_user_weak_topics(
    user_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get user's weak topics."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    query = db.query(WeakTopic).filter(WeakTopic.user_id == user_id)
    if active_only:
        query = query.filter(WeakTopic.is_active == True)

    return query.all()


@router.get("/{user_id}/statistics", response_model=UserStatistics)
def get_user_statistics(user_id: int, db: Session = Depends(get_db)):
    """Get comprehensive user statistics."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    # Calculate topic distribution
    topic_distribution = {}
    for tr in user.topic_ratings:
        topic_distribution[tr.topic] = tr.problems_solved

    # Calculate win rate (contests with all problems solved)
    from ..models import Contest, ContestStatus
    total_completed = db.query(Contest).filter(
        Contest.user_id == user_id,
        Contest.status == ContestStatus.COMPLETED,
    ).count()

    perfect_contests = db.query(Contest).filter(
        Contest.user_id == user_id,
        Contest.status == ContestStatus.COMPLETED,
        Contest.problems_solved == Contest.num_problems,
    ).count()

    win_rate = (perfect_contests / total_completed * 100) if total_completed > 0 else 0

    # Get rating history from contests
    from ..models import Contest
    contests = db.query(Contest).filter(
        Contest.user_id == user_id,
        Contest.status == ContestStatus.COMPLETED,
    ).order_by(Contest.ended_at.asc()).all()

    rating_history = []
    running_rating = 800
    for c in contests:
        running_rating = c.rating_at_start + c.rating_change
        rating_history.append({
            "date": c.ended_at.isoformat() if c.ended_at else None,
            "rating": running_rating,
            "change": c.rating_change,
        })

    # Calculate average solve time
    from ..models import ContestProblem, SubmissionStatus
    avg_time_result = db.query(ContestProblem).join(Contest).filter(
        Contest.user_id == user_id,
        ContestProblem.status == SubmissionStatus.SOLVED,
        ContestProblem.time_taken_seconds.isnot(None),
    ).all()

    avg_time = None
    if avg_time_result:
        total_time = sum(p.time_taken_seconds for p in avg_time_result if p.time_taken_seconds)
        avg_time = total_time / len(avg_time_result) if avg_time_result else None

    # Count active weak topics
    weak_topics_count = db.query(WeakTopic).filter(
        WeakTopic.user_id == user_id,
        WeakTopic.is_active == True,
    ).count()

    return UserStatistics(
        user_id=user.id,
        username=user.username,
        rating=user.rating,
        rating_history=rating_history,
        topic_distribution=topic_distribution,
        weak_topics_count=weak_topics_count,
        average_solve_time=avg_time,
        contests_completed=total_completed,
        win_rate=win_rate,
    )

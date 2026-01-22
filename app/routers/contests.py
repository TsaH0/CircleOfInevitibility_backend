"""
Contest management API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..models import User, Contest, ContestProblem, ContestStatus
from ..schemas import (
    ContestCreate, ContestResponse, ContestDetailResponse,
    ProblemSubmission, ContestSubmission, SubmissionResponse,
    ContestResult, ProblemResult
)
from ..services.contest_service import get_contest_service

router = APIRouter(prefix="/contests", tags=["contests"])


@router.post("/start/{user_id}", response_model=ContestDetailResponse, status_code=status.HTTP_201_CREATED)
def start_contest(
    user_id: int,
    contest_config: ContestCreate = None,
    db: Session = Depends(get_db)
):
    """
    Start a new contest for a user.

    The contest will:
    - Select problems at user's rating + 10 difficulty
    - Distribute topics across problems
    - Include weak topic problems if any exist
    """
    if contest_config is None:
        contest_config = ContestCreate()

    contest_service = get_contest_service()

    try:
        contest = contest_service.create_contest(
            db=db,
            user_id=user_id,
            num_problems=contest_config.num_problems,
            time_limit_minutes=contest_config.time_limit_minutes,
            include_weak_topics=contest_config.include_weak_topics,
            target_difficulty=contest_config.target_difficulty,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return contest


@router.get("/active/{user_id}", response_model=Optional[ContestDetailResponse])
def get_active_contest(user_id: int, db: Session = Depends(get_db)):
    """Get the user's currently active contest, if any."""
    contest_service = get_contest_service()
    contest = contest_service.get_active_contest(db, user_id)

    if not contest:
        return None

    return contest


@router.get("/{contest_id}", response_model=ContestDetailResponse)
def get_contest(contest_id: int, db: Session = Depends(get_db)):
    """Get contest details by ID."""
    contest_service = get_contest_service()
    contest = contest_service.get_contest(db, contest_id)

    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contest {contest_id} not found"
        )

    return contest


@router.post("/{contest_id}/start-problem/{problem_id}", response_model=ContestDetailResponse)
def start_problem(
    contest_id: int,
    problem_id: str,
    db: Session = Depends(get_db)
):
    """
    Mark a problem as started (begins timing for that problem).
    Call this when the user opens a problem to start tracking time.
    """
    contest_service = get_contest_service()

    try:
        contest_service.start_problem(db, contest_id, problem_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    contest = contest_service.get_contest(db, contest_id)
    return contest


@router.post("/{contest_id}/submit", response_model=SubmissionResponse)
def submit_problem(
    contest_id: int,
    submission: ProblemSubmission,
    db: Session = Depends(get_db)
):
    """
    Submit a solution for a single problem.

    Args:
        contest_id: Contest ID
        submission: Problem submission data
            - problem_id: The problem being submitted
            - solved: Whether the problem was solved correctly
            - time_taken_seconds: Optional explicit time taken
    """
    contest_service = get_contest_service()

    try:
        contest_problem = contest_service.submit_problem(
            db=db,
            contest_id=contest_id,
            problem_id=submission.problem_id,
            solved=submission.solved,
            partial=submission.partial,
            time_taken_seconds=submission.time_taken_seconds,
            user_approach=submission.user_approach,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return SubmissionResponse(
        contest_id=contest_id,
        problem_id=submission.problem_id,
        status=contest_problem.status.value,
        time_taken_seconds=contest_problem.time_taken_seconds,
        message="Problem submitted successfully",
    )


@router.post("/{contest_id}/submit-all", response_model=List[SubmissionResponse])
def submit_all_problems(
    contest_id: int,
    submissions: ContestSubmission,
    db: Session = Depends(get_db)
):
    """
    Submit solutions for multiple problems at once.
    Useful for submitting all results at the end of a contest.
    """
    contest_service = get_contest_service()
    results = []

    for submission in submissions.submissions:
        try:
            contest_problem = contest_service.submit_problem(
                db=db,
                contest_id=contest_id,
                problem_id=submission.problem_id,
                solved=submission.solved,
                partial=submission.partial,
                time_taken_seconds=submission.time_taken_seconds,
                user_approach=submission.user_approach,
            )
            results.append(SubmissionResponse(
                contest_id=contest_id,
                problem_id=submission.problem_id,
                status=contest_problem.status.value,
                time_taken_seconds=contest_problem.time_taken_seconds,
                message="Problem submitted successfully",
            ))
        except ValueError as e:
            results.append(SubmissionResponse(
                contest_id=contest_id,
                problem_id=submission.problem_id,
                status="error",
                time_taken_seconds=None,
                message=str(e),
            ))

    return results


@router.post("/{contest_id}/skip/{problem_id}", response_model=ContestDetailResponse)
def skip_problem(
    contest_id: int,
    problem_id: str,
    db: Session = Depends(get_db)
):
    """
    Skip a problem (mark as not attempted).
    Skipped problems are treated as failed when calculating ratings.
    """
    contest_service = get_contest_service()

    try:
        contest_service.skip_problem(db, contest_id, problem_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    contest = contest_service.get_contest(db, contest_id)
    return contest


@router.post("/{contest_id}/end", response_model=ContestResult)
def end_contest(contest_id: int, db: Session = Depends(get_db)):
    """
    End a contest and calculate results.

    This will:
    - Mark any pending problems as failed
    - Calculate rating changes
    - Update weak topics
    - Return detailed results
    """
    contest_service = get_contest_service()

    try:
        result = contest_service.end_contest(db, contest_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Convert to response schema
    return ContestResult(
        contest_id=result["contest_id"],
        status=result["status"],
        problems_solved=result["problems_solved"],
        total_problems=result["total_problems"],
        total_time_seconds=result["total_time_seconds"],
        old_rating=result["old_rating"],
        new_rating=result["new_rating"],
        rating_change=result["rating_change"],
        topics_passed=result["topics_passed"],
        topics_failed=result["topics_failed"],
        new_weak_topics=result["new_weak_topics"],
        weak_topics_improved=result["weak_topics_improved"],
        problems=[
            ProblemResult(
                problem_id=p["problem_id"],
                problem_name=p["problem_name"],
                topic=p["topic"],
                difficulty=p["difficulty"],
                solved=p["solved"],
                time_taken_seconds=p["time_taken_seconds"],
                is_weak_topic_problem=p["is_weak_topic_problem"],
            )
            for p in result["problems"]
        ],
    )


@router.post("/{contest_id}/abandon", response_model=ContestResponse)
def abandon_contest(contest_id: int, db: Session = Depends(get_db)):
    """
    Abandon a contest without any rating changes.
    Use this if the user wants to quit without penalty.
    """
    contest_service = get_contest_service()

    try:
        contest = contest_service.abandon_contest(db, contest_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return contest


@router.get("/history/{user_id}", response_model=List[ContestResponse])
def get_user_contest_history(
    user_id: int,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get a user's contest history."""
    contest_service = get_contest_service()

    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    contests = contest_service.get_user_contests(db, user_id, limit, offset)
    return contests


@router.get("/history/{user_id}/{contest_id}", response_model=ContestDetailResponse)
def get_user_contest_detail(
    user_id: int,
    contest_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific contest."""
    contest_service = get_contest_service()

    contest = contest_service.get_contest(db, contest_id)
    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contest {contest_id} not found"
        )

    if contest.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contest does not belong to this user"
        )

    return contest

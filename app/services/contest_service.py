"""
Contest management service.
Handles creating contests, tracking submissions, and ending contests.
"""

from typing import List, Dict, Set, Optional, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from ..models import (
    User, Contest, ContestProblem, ProblemHistory, WeakTopic,
    ContestStatus, SubmissionStatus
)
from .problem_service import get_problem_service, Problem
from .rating_service import get_rating_service


class ContestService:
    """Service for managing contests."""

    def __init__(self):
        self.problem_service = get_problem_service()
        self.rating_service = get_rating_service()

    def create_contest(
        self,
        db: Session,
        user_id: int,
        num_problems: int = 5,
        time_limit_minutes: int = 120,
        include_weak_topics: bool = True,
    ) -> Contest:
        """
        Create a new contest for a user.

        Args:
            db: Database session
            user_id: User ID
            num_problems: Number of problems (3-10)
            time_limit_minutes: Time limit in minutes
            include_weak_topics: Whether to include weak topic problems

        Returns:
            Created Contest object
        """
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Check for active contests
        active_contest = db.query(Contest).filter(
            Contest.user_id == user_id,
            Contest.status == ContestStatus.ACTIVE,
        ).first()

        if active_contest:
            raise ValueError(f"User already has an active contest: {active_contest.id}")

        # Calculate target difficulty
        target_difficulty = user.rating + 10

        # Get user's weak topics
        weak_topics = []
        if include_weak_topics:
            user_weak_topics = self.rating_service.get_user_weak_topics(db, user_id)
            weak_topics = [wt.topic for wt in user_weak_topics]

        # Get already solved problems to exclude
        excluded_ids = self._get_recent_problem_ids(db, user_id)

        # Select problems
        selected = self.problem_service.select_problems_for_contest(
            target_difficulty=target_difficulty,
            num_problems=num_problems,
            weak_topics=weak_topics,
            excluded_problem_ids=excluded_ids,
            include_weak_topics=include_weak_topics,
        )

        if len(selected) < num_problems:
            raise ValueError(
                f"Could not find enough problems. Found {len(selected)}, needed {num_problems}"
            )

        # Create contest
        contest = Contest(
            user_id=user_id,
            status=ContestStatus.ACTIVE,
            rating_at_start=user.rating,
            num_problems=num_problems,
            target_difficulty=target_difficulty,
            time_limit_minutes=time_limit_minutes,
        )
        db.add(contest)
        db.flush()  # Get contest ID

        # Create contest problems
        for item in selected:
            problem: Problem = item["problem"]

            # Adjust difficulty for weak topic problems based on their current level
            if item["is_weak_topic_problem"]:
                weak_topic = db.query(WeakTopic).filter(
                    WeakTopic.user_id == user_id,
                    WeakTopic.topic == item["topic"],
                    WeakTopic.is_active == True,
                ).first()

                if weak_topic:
                    # Use weak topic's current level
                    item["target_difficulty"] = weak_topic.current_level

            contest_problem = ContestProblem(
                contest_id=contest.id,
                problem_id=problem.id,
                problem_name=problem.name,
                problem_url=problem.url,
                topic=item["topic"],
                difficulty=problem.difficulty,
                source=problem.source,
                is_weak_topic_problem=item["is_weak_topic_problem"],
                status=SubmissionStatus.PENDING,
            )
            db.add(contest_problem)

        db.commit()
        db.refresh(contest)

        return contest

    def _get_recent_problem_ids(self, db: Session, user_id: int, days: int = 30) -> Set[str]:
        """Get problem IDs the user has attempted recently."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        history = db.query(ProblemHistory.problem_id).filter(
            ProblemHistory.user_id == user_id,
            ProblemHistory.last_attempted_at >= cutoff,
        ).all()

        return {h.problem_id for h in history}

    def get_contest(self, db: Session, contest_id: int) -> Optional[Contest]:
        """Get a contest by ID."""
        return db.query(Contest).filter(Contest.id == contest_id).first()

    def get_active_contest(self, db: Session, user_id: int) -> Optional[Contest]:
        """Get the user's active contest if any."""
        return db.query(Contest).filter(
            Contest.user_id == user_id,
            Contest.status == ContestStatus.ACTIVE,
        ).first()

    def start_problem(
        self,
        db: Session,
        contest_id: int,
        problem_id: str,
    ) -> ContestProblem:
        """Mark a problem as started (for timing)."""
        contest_problem = db.query(ContestProblem).filter(
            ContestProblem.contest_id == contest_id,
            ContestProblem.problem_id == problem_id,
        ).first()

        if not contest_problem:
            raise ValueError(f"Problem {problem_id} not found in contest {contest_id}")

        if contest_problem.started_at is None:
            contest_problem.started_at = datetime.utcnow()
            db.commit()

        return contest_problem

    def submit_problem(
        self,
        db: Session,
        contest_id: int,
        problem_id: str,
        solved: bool,
        time_taken_seconds: Optional[int] = None,
    ) -> ContestProblem:
        """
        Submit a solution for a problem.

        Args:
            db: Database session
            contest_id: Contest ID
            problem_id: Problem ID
            solved: Whether the problem was solved
            time_taken_seconds: Time taken (optional, calculated from start if not provided)

        Returns:
            Updated ContestProblem
        """
        # Get contest and verify it's active
        contest = db.query(Contest).filter(Contest.id == contest_id).first()
        if not contest:
            raise ValueError(f"Contest {contest_id} not found")

        if contest.status != ContestStatus.ACTIVE:
            raise ValueError(f"Contest {contest_id} is not active")

        # Check time limit
        elapsed = datetime.utcnow() - contest.started_at
        if elapsed.total_seconds() > contest.time_limit_minutes * 60:
            # Auto-end the contest
            self.end_contest(db, contest_id, auto_end=True)
            raise ValueError("Contest time limit exceeded")

        # Get contest problem
        contest_problem = db.query(ContestProblem).filter(
            ContestProblem.contest_id == contest_id,
            ContestProblem.problem_id == problem_id,
        ).first()

        if not contest_problem:
            raise ValueError(f"Problem {problem_id} not found in contest {contest_id}")

        # Update submission
        now = datetime.utcnow()
        contest_problem.submitted_at = now
        contest_problem.attempts += 1

        # Calculate time taken
        if time_taken_seconds is not None:
            contest_problem.time_taken_seconds = time_taken_seconds
        elif contest_problem.started_at:
            delta = now - contest_problem.started_at
            contest_problem.time_taken_seconds = int(delta.total_seconds())

        # Update status
        if solved:
            contest_problem.status = SubmissionStatus.SOLVED
        else:
            contest_problem.status = SubmissionStatus.FAILED

        # Update problem history
        self._update_problem_history(
            db,
            contest.user_id,
            problem_id,
            solved,
            contest_problem.time_taken_seconds,
        )

        db.commit()
        db.refresh(contest_problem)

        return contest_problem

    def _update_problem_history(
        self,
        db: Session,
        user_id: int,
        problem_id: str,
        solved: bool,
        time_seconds: Optional[int],
    ) -> None:
        """Update problem history for deduplication."""
        history = db.query(ProblemHistory).filter(
            ProblemHistory.user_id == user_id,
            ProblemHistory.problem_id == problem_id,
        ).first()

        if history:
            history.times_attempted += 1
            history.last_attempted_at = datetime.utcnow()
            if solved:
                history.times_solved += 1
                if time_seconds and (history.best_time_seconds is None or time_seconds < history.best_time_seconds):
                    history.best_time_seconds = time_seconds
        else:
            history = ProblemHistory(
                user_id=user_id,
                problem_id=problem_id,
                times_attempted=1,
                times_solved=1 if solved else 0,
                best_time_seconds=time_seconds if solved else None,
            )
            db.add(history)

    def skip_problem(
        self,
        db: Session,
        contest_id: int,
        problem_id: str,
    ) -> ContestProblem:
        """Mark a problem as skipped."""
        contest_problem = db.query(ContestProblem).filter(
            ContestProblem.contest_id == contest_id,
            ContestProblem.problem_id == problem_id,
        ).first()

        if not contest_problem:
            raise ValueError(f"Problem {problem_id} not found in contest {contest_id}")

        contest_problem.status = SubmissionStatus.SKIPPED
        contest_problem.submitted_at = datetime.utcnow()

        db.commit()
        db.refresh(contest_problem)

        return contest_problem

    def end_contest(
        self,
        db: Session,
        contest_id: int,
        auto_end: bool = False,
    ) -> Dict[str, Any]:
        """
        End a contest and calculate results.

        Args:
            db: Database session
            contest_id: Contest ID
            auto_end: Whether this is an automatic end (time limit)

        Returns:
            Contest result dictionary
        """
        contest = db.query(Contest).filter(Contest.id == contest_id).first()
        if not contest:
            raise ValueError(f"Contest {contest_id} not found")

        if contest.status != ContestStatus.ACTIVE:
            raise ValueError(f"Contest {contest_id} is not active")

        # Mark pending/skipped problems as failed
        for problem in contest.problems:
            if problem.status in [SubmissionStatus.PENDING, SubmissionStatus.SKIPPED]:
                problem.status = SubmissionStatus.FAILED

        # Update contest status
        contest.status = ContestStatus.COMPLETED
        contest.ended_at = datetime.utcnow()

        # Calculate total time
        total_time = sum(
            p.time_taken_seconds or 0
            for p in contest.problems
            if p.status == SubmissionStatus.SOLVED
        )
        contest.total_time_seconds = total_time

        db.commit()

        # Calculate ratings
        result = self.rating_service.calculate_contest_result(db, contest)

        # Add problem details to result
        result["contest_id"] = contest_id
        result["status"] = contest.status.value
        result["total_problems"] = len(contest.problems)
        result["total_time_seconds"] = total_time
        result["problems"] = [
            {
                "problem_id": p.problem_id,
                "problem_name": p.problem_name,
                "topic": p.topic,
                "difficulty": p.difficulty,
                "solved": p.status == SubmissionStatus.SOLVED,
                "time_taken_seconds": p.time_taken_seconds,
                "is_weak_topic_problem": p.is_weak_topic_problem,
            }
            for p in contest.problems
        ]

        return result

    def abandon_contest(self, db: Session, contest_id: int) -> Contest:
        """Abandon a contest without rating changes."""
        contest = db.query(Contest).filter(Contest.id == contest_id).first()
        if not contest:
            raise ValueError(f"Contest {contest_id} not found")

        if contest.status != ContestStatus.ACTIVE:
            raise ValueError(f"Contest {contest_id} is not active")

        contest.status = ContestStatus.ABANDONED
        contest.ended_at = datetime.utcnow()

        db.commit()
        db.refresh(contest)

        return contest

    def get_user_contests(
        self,
        db: Session,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Contest]:
        """Get user's contest history."""
        return db.query(Contest).filter(
            Contest.user_id == user_id,
        ).order_by(Contest.started_at.desc()).offset(offset).limit(limit).all()


# Singleton instance
_contest_service: Optional[ContestService] = None


def get_contest_service() -> ContestService:
    """Get the singleton contest service instance."""
    global _contest_service
    if _contest_service is None:
        _contest_service = ContestService()
    return _contest_service

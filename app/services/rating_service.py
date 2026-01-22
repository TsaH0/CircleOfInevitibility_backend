"""
Rating calculation service.
Handles user rating updates based on contest performance.
"""

from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from ..models import (
    User, UserTopicRating, WeakTopic, Contest, ContestProblem,
    ContestStatus, SubmissionStatus
)


class RatingService:
    """Service for calculating and updating ratings."""

    # Rating change constants
    RATING_INCREASE = 10  # Rating increase for solving all problems
    RATING_DECREASE_PER_FAIL = 5  # Rating decrease per failed problem
    WEAK_TOPIC_THRESHOLD = 2  # Consecutive failures to mark as weak

    # Weak topic progression
    WEAK_TOPIC_SOLVES_TO_ADVANCE = 2  # Consecutive solves to increase level
    WEAK_TOPIC_LEVEL_STEP = 5  # How much to increase level each time

    def calculate_contest_result(
        self,
        db: Session,
        contest: Contest,
    ) -> Dict:
        """
        Calculate the result of a completed contest.

        Returns dict with:
        - rating_change: Change in user's overall rating
        - topic_changes: Dict of topic -> rating change
        - new_weak_topics: List of newly detected weak topics
        - weak_topics_improved: List of weak topics that improved
        - weak_topics_resolved: List of weak topics fully resolved
        """
        user = contest.user
        problems = contest.problems

        # Count solved and failed (PARTIAL counts as failed)
        solved_problems = [p for p in problems if p.status == SubmissionStatus.SOLVED]
        failed_problems = [p for p in problems if p.status in [SubmissionStatus.FAILED, SubmissionStatus.PARTIAL]]

        all_solved = len(solved_problems) == len(problems)
        any_failed = len(failed_problems) > 0

        result = {
            "old_rating": user.rating,
            "new_rating": user.rating,
            "rating_change": 0,
            "topic_changes": {},
            "new_weak_topics": [],
            "weak_topics_improved": [],
            "weak_topics_resolved": [],
            "topics_passed": [],
            "topics_failed": [],
        }

        # Process each problem
        for problem in problems:
            topic = problem.topic
            is_weak = problem.is_weak_topic_problem
            solved = problem.status == SubmissionStatus.SOLVED

            if solved:
                result["topics_passed"].append(topic)
            else:
                result["topics_failed"].append(topic)

            # Handle weak topic problems
            if is_weak:
                self._process_weak_topic_result(db, user, topic, solved, result)
            else:
                # Handle regular topic problems
                self._process_regular_topic_result(db, user, topic, solved, result)

        # Calculate overall rating change
        if all_solved:
            # All problems solved: increase rating
            result["rating_change"] = self.RATING_INCREASE
            result["new_rating"] = user.rating + self.RATING_INCREASE
        elif any_failed:
            # Some problems failed: don't increase rating
            # But we don't decrease for regular fails, only track weak topics
            result["rating_change"] = 0
            result["new_rating"] = user.rating

        # Add problem counts to result
        result["problems_solved"] = len(solved_problems)
        result["total_problems"] = len(problems)

        # Update user rating
        user.rating = result["new_rating"]
        user.total_contests += 1
        user.total_problems_solved += len(solved_problems)
        user.total_problems_attempted += len(problems)

        # Update contest
        contest.rating_change = result["rating_change"]
        contest.problems_solved = len(solved_problems)

        db.commit()

        return result

    def _process_weak_topic_result(
        self,
        db: Session,
        user: User,
        topic: str,
        solved: bool,
        result: Dict,
    ) -> None:
        """Process result for a weak topic problem."""
        # Find active weak topic
        weak_topic = db.query(WeakTopic).filter(
            WeakTopic.user_id == user.id,
            WeakTopic.topic == topic,
            WeakTopic.is_active == True,
        ).first()

        if not weak_topic:
            return

        weak_topic.total_attempts += 1
        weak_topic.last_attempt_at = datetime.utcnow()

        if solved:
            weak_topic.consecutive_solves += 1

            # Check if ready to advance level
            if weak_topic.consecutive_solves >= self.WEAK_TOPIC_SOLVES_TO_ADVANCE:
                weak_topic.current_level += self.WEAK_TOPIC_LEVEL_STEP
                weak_topic.consecutive_solves = 0

                result["weak_topics_improved"].append(topic)

                # Check if weak topic is resolved (reached target level)
                if weak_topic.current_level >= weak_topic.target_level:
                    weak_topic.is_active = False
                    weak_topic.resolved_at = datetime.utcnow()
                    result["weak_topics_resolved"].append(topic)

        else:
            weak_topic.total_failures += 1
            weak_topic.consecutive_solves = 0

            # Decrease level if struggling (but not below minimum)
            if weak_topic.total_failures > 3 and weak_topic.current_level > 10:
                weak_topic.current_level = max(10, weak_topic.current_level - self.WEAK_TOPIC_LEVEL_STEP)

        db.commit()

    def _process_regular_topic_result(
        self,
        db: Session,
        user: User,
        topic: str,
        solved: bool,
        result: Dict,
    ) -> None:
        """Process result for a regular (non-weak) topic problem."""
        # Get or create topic rating
        topic_rating = db.query(UserTopicRating).filter(
            UserTopicRating.user_id == user.id,
            UserTopicRating.topic == topic,
        ).first()

        if not topic_rating:
            topic_rating = UserTopicRating(
                user_id=user.id,
                topic=topic,
                rating=user.rating,  # Start at user's overall rating
                problems_attempted=0,
                problems_solved=0,
            )
            db.add(topic_rating)
            db.flush()  # Ensure defaults are set

        topic_rating.problems_attempted += 1

        if solved:
            topic_rating.problems_solved += 1
            # Small rating increase for topic
            topic_rating.rating = min(topic_rating.rating + 5, 3000)
            result["topic_changes"][topic] = result["topic_changes"].get(topic, 0) + 5
        else:
            # Check if this topic should become weak
            # Calculate failure rate for this topic
            if topic_rating.problems_attempted >= 2:
                failure_rate = 1 - (topic_rating.problems_solved / topic_rating.problems_attempted)

                if failure_rate >= 0.5:  # 50% or more failures
                    # Check if already a weak topic
                    existing_weak = db.query(WeakTopic).filter(
                        WeakTopic.user_id == user.id,
                        WeakTopic.topic == topic,
                        WeakTopic.is_active == True,
                    ).first()

                    if not existing_weak:
                        # Create new weak topic
                        weak_topic = WeakTopic(
                            user_id=user.id,
                            topic=topic,
                            current_level=max(10, user.rating - 20),  # Start lower
                            target_level=user.rating + 10,
                            consecutive_solves=0,
                            total_attempts=0,
                            total_failures=0,
                        )
                        db.add(weak_topic)
                        result["new_weak_topics"].append(topic)

            # Small rating decrease for topic
            topic_rating.rating = max(topic_rating.rating - 3, 100)
            result["topic_changes"][topic] = result["topic_changes"].get(topic, 0) - 3

        db.commit()

    def get_user_weak_topics(self, db: Session, user_id: int) -> List[WeakTopic]:
        """Get all active weak topics for a user."""
        return db.query(WeakTopic).filter(
            WeakTopic.user_id == user_id,
            WeakTopic.is_active == True,
        ).all()

    def get_weak_topic_difficulty(self, weak_topic: WeakTopic) -> int:
        """Get the current difficulty level for a weak topic."""
        return weak_topic.current_level

    def update_topic_rating(
        self,
        db: Session,
        user_id: int,
        topic: str,
        solved: bool,
        difficulty: int,
    ) -> Optional[UserTopicRating]:
        """Update a user's rating for a specific topic."""
        topic_rating = db.query(UserTopicRating).filter(
            UserTopicRating.user_id == user_id,
            UserTopicRating.topic == topic,
        ).first()

        if not topic_rating:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None

            topic_rating = UserTopicRating(
                user_id=user_id,
                topic=topic,
                rating=user.rating,
            )
            db.add(topic_rating)

        topic_rating.problems_attempted += 1
        if solved:
            topic_rating.problems_solved += 1

        db.commit()
        return topic_rating


# Singleton instance
_rating_service: Optional[RatingService] = None


def get_rating_service() -> RatingService:
    """Get the singleton rating service instance."""
    global _rating_service
    if _rating_service is None:
        _rating_service = RatingService()
    return _rating_service

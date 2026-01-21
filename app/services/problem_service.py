"""
Problem selection service.
Handles loading problems from standardized_problems.json and selecting appropriate problems for contests.
"""

import json
import os
import random
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Problem:
    """Problem data class."""
    id: str
    name: str
    url: str
    source: str
    difficulty: int
    primary_skills: List[str]
    secondary_skills: List[str]
    pattern_id: Optional[str]
    tags: List[str]
    extra: Dict[str, Any]


class ProblemService:
    """Service for loading and selecting problems."""

    # Difficulty tolerance when selecting problems
    DIFFICULTY_TOLERANCE = 5

    # Topics to use for distribution (based on pattern_id or primary skills)
    CORE_TOPICS = [
        "dp_general", "dp_knapsack", "dp_lis", "dp_bitmask", "dp_trees",
        "graph_traversal", "graph_shortest_path", "graph_mst", "graph_dsu", "graph_topo",
        "tree_general", "tree_lca", "tree_euler",
        "search_binary", "search_two_pointers", "search_sliding_window",
        "ds_segtree", "ds_fenwick", "ds_pq",
        "math_nt", "math_combo", "math_modular",
        "string_general", "string_hash",
        "tech_greedy", "tech_sorting", "tech_prefix",
        "tech_implementation", "tech_brute",
    ]

    def __init__(self, problems_file: str = None):
        """Initialize the problem service."""
        if problems_file is None:
            # Default path relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            problems_file = os.path.join(base_dir, "output", "standardized_problems.json")

        self.problems_file = problems_file
        self._problems: List[Problem] = []
        self._problems_by_id: Dict[str, Problem] = {}
        self._problems_by_topic: Dict[str, List[Problem]] = {}
        self._problems_by_difficulty: Dict[int, List[Problem]] = {}
        self._loaded = False

    def load_problems(self) -> None:
        """Load problems from JSON file."""
        if self._loaded:
            return

        if not os.path.exists(self.problems_file):
            raise FileNotFoundError(f"Problems file not found: {self.problems_file}")

        with open(self.problems_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        problems_data = data.get("problems", [])

        for p in problems_data:
            problem = Problem(
                id=p.get("id", ""),
                name=p.get("name", "Unknown"),
                url=p.get("url", ""),
                source=p.get("source", ""),
                difficulty=p.get("internal_rating", 50),
                primary_skills=p.get("primary_skills", []),
                secondary_skills=p.get("secondary_skills", []),
                pattern_id=p.get("pattern_id"),
                tags=p.get("tags", []),
                extra=p.get("extra", {}),
            )

            if not problem.id or not problem.url:
                continue

            self._problems.append(problem)
            self._problems_by_id[problem.id] = problem

            # Index by topic (use pattern_id or first primary skill)
            topic = self._get_topic(problem)
            if topic not in self._problems_by_topic:
                self._problems_by_topic[topic] = []
            self._problems_by_topic[topic].append(problem)

            # Index by difficulty (bucketed by 5)
            bucket = (problem.difficulty // 5) * 5
            if bucket not in self._problems_by_difficulty:
                self._problems_by_difficulty[bucket] = []
            self._problems_by_difficulty[bucket].append(problem)

        self._loaded = True
        print(f"Loaded {len(self._problems)} problems")
        print(f"Topics: {len(self._problems_by_topic)}")

    def _get_topic(self, problem: Problem) -> str:
        """Get the primary topic for a problem."""
        if problem.pattern_id:
            return problem.pattern_id
        if problem.primary_skills:
            # Convert skill to topic-like format
            skill = problem.primary_skills[0].lower().replace(" ", "_")
            return f"skill_{skill}"
        return "general"

    def get_problem(self, problem_id: str) -> Optional[Problem]:
        """Get a problem by ID."""
        self.load_problems()
        return self._problems_by_id.get(problem_id)

    def get_available_topics(self) -> List[str]:
        """Get list of available topics."""
        self.load_problems()
        return list(self._problems_by_topic.keys())

    def select_problems_for_contest(
        self,
        target_difficulty: int,
        num_problems: int,
        weak_topics: List[str] = None,
        excluded_problem_ids: Set[str] = None,
        include_weak_topics: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Select problems for a contest with topic distribution.

        Args:
            target_difficulty: Target difficulty (user rating + 10)
            num_problems: Number of problems to select
            weak_topics: List of user's weak topics
            excluded_problem_ids: Problems to exclude (already solved)
            include_weak_topics: Whether to include weak topic problems

        Returns:
            List of problem dicts with topic and is_weak_topic_problem flags
        """
        self.load_problems()

        if excluded_problem_ids is None:
            excluded_problem_ids = set()
        if weak_topics is None:
            weak_topics = []

        selected = []
        used_topics = set()
        used_problem_ids = set(excluded_problem_ids)

        # Determine how many weak topic problems to include
        weak_topic_count = 0
        if include_weak_topics and weak_topics:
            weak_topic_count = min(len(weak_topics), max(1, num_problems // 3))

        # First, select weak topic problems (at lower difficulty)
        for i, weak_topic in enumerate(weak_topics[:weak_topic_count]):
            # Weak topic problems are at current level, not target
            # This will be adjusted by the calling code based on WeakTopic.current_level
            problem = self._select_problem_for_topic(
                topic=weak_topic,
                difficulty=target_difficulty - 10,  # Lower difficulty for weak topics
                tolerance=self.DIFFICULTY_TOLERANCE + 5,  # More tolerance
                excluded=used_problem_ids,
            )

            if problem:
                selected.append({
                    "problem": problem,
                    "topic": weak_topic,
                    "is_weak_topic_problem": True,
                    "target_difficulty": target_difficulty - 10,
                })
                used_problem_ids.add(problem.id)
                used_topics.add(weak_topic)

        # Fill remaining slots with distributed topics
        remaining = num_problems - len(selected)

        # Get topics to distribute (excluding already used weak topics)
        available_topics = [t for t in self._problems_by_topic.keys() if t not in used_topics]
        random.shuffle(available_topics)

        # Select problems from different topics
        topic_index = 0
        attempts = 0
        max_attempts = remaining * 10

        while len(selected) < num_problems and attempts < max_attempts:
            attempts += 1

            # Cycle through topics
            if topic_index >= len(available_topics):
                topic_index = 0
                # If we've cycled through all topics, allow repeats
                if attempts > len(available_topics):
                    available_topics = list(self._problems_by_topic.keys())
                    random.shuffle(available_topics)

            topic = available_topics[topic_index]
            topic_index += 1

            problem = self._select_problem_for_topic(
                topic=topic,
                difficulty=target_difficulty,
                tolerance=self.DIFFICULTY_TOLERANCE,
                excluded=used_problem_ids,
            )

            if problem:
                selected.append({
                    "problem": problem,
                    "topic": topic,
                    "is_weak_topic_problem": False,
                    "target_difficulty": target_difficulty,
                })
                used_problem_ids.add(problem.id)
                used_topics.add(topic)

        # If still not enough, relax constraints
        if len(selected) < num_problems:
            remaining_needed = num_problems - len(selected)
            fallback = self._select_fallback_problems(
                difficulty=target_difficulty,
                count=remaining_needed,
                excluded=used_problem_ids,
            )
            for problem in fallback:
                selected.append({
                    "problem": problem,
                    "topic": self._get_topic(problem),
                    "is_weak_topic_problem": False,
                    "target_difficulty": target_difficulty,
                })

        return selected

    def _select_problem_for_topic(
        self,
        topic: str,
        difficulty: int,
        tolerance: int,
        excluded: Set[str],
    ) -> Optional[Problem]:
        """Select a single problem for a specific topic and difficulty."""
        if topic not in self._problems_by_topic:
            return None

        candidates = [
            p for p in self._problems_by_topic[topic]
            if p.id not in excluded
            and abs(p.difficulty - difficulty) <= tolerance
        ]

        if not candidates:
            # Try with more tolerance
            candidates = [
                p for p in self._problems_by_topic[topic]
                if p.id not in excluded
                and abs(p.difficulty - difficulty) <= tolerance * 2
            ]

        if candidates:
            return random.choice(candidates)
        return None

    def _select_fallback_problems(
        self,
        difficulty: int,
        count: int,
        excluded: Set[str],
    ) -> List[Problem]:
        """Select problems without topic constraint (fallback)."""
        candidates = [
            p for p in self._problems
            if p.id not in excluded
            and abs(p.difficulty - difficulty) <= self.DIFFICULTY_TOLERANCE * 3
        ]

        if len(candidates) <= count:
            return candidates

        return random.sample(candidates, count)

    def get_problems_for_topic(
        self,
        topic: str,
        min_difficulty: int,
        max_difficulty: int,
        limit: int = 10,
    ) -> List[Problem]:
        """Get problems for a specific topic within difficulty range."""
        self.load_problems()

        if topic not in self._problems_by_topic:
            return []

        candidates = [
            p for p in self._problems_by_topic[topic]
            if min_difficulty <= p.difficulty <= max_difficulty
        ]

        if len(candidates) <= limit:
            return candidates

        return random.sample(candidates, limit)


# Singleton instance
_problem_service: Optional[ProblemService] = None


def get_problem_service() -> ProblemService:
    """Get the singleton problem service instance."""
    global _problem_service
    if _problem_service is None:
        _problem_service = ProblemService()
    return _problem_service

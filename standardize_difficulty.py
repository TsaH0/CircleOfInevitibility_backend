#!/usr/bin/env python3
"""
standardize_difficulty.py

Converts platform-specific difficulty labels into a unified internal scale (1-100).
Adds skill tags and pattern identification to each problem.

ASSUMPTIONS:
1. USACO Guide problems have a "source" field indicating division (Bronze/Silver/Gold/Platinum)
   and a "difficulty" field with labels like "Very Easy", "Easy", "Normal", "Hard", "Very Hard", "Insane"
2. Codeforces problems have a "rating" field (800-3500) - some may be null
3. AtCoder problems have "difficulty" from Kenkoooo (can be negative) and contest_id prefix
4. All input files are in the output/ directory

MAPPING PHILOSOPHY:
- Internal rating 1-100 represents relative difficulty
- 1-25: Beginner (learn basics)
- 26-50: Intermediate (standard techniques)
- 51-75: Advanced (complex algorithms)
- 76-100: Expert (competition-level hard)

TUNING GUIDE:
- Edit the *_MAPPING dictionaries to adjust difficulty mappings
- Edit SKILL_PRIORITY to change which tags are prioritized
- Edit PATTERN_KEYWORDS to map tags to pattern IDs
"""

import json
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# =============================================================================
# CONFIGURATION - EDIT THESE TO TUNE MAPPINGS
# =============================================================================

# USACO Guide: Division -> Base rating range
# Format: division -> (min_rating, max_rating)
USACO_DIVISION_MAPPING = {
    "Bronze": (10, 25),
    "Silver": (30, 45),
    "Gold": (50, 65),
    "Platinum": (70, 85),
    "Advanced": (85, 100),
}

# USACO Guide: Difficulty label -> multiplier within division range
# 0.0 = min of range, 1.0 = max of range
USACO_DIFFICULTY_MULTIPLIER = {
    "Very Easy": 0.0,
    "Easy": 0.2,
    "Medium": 0.5,  # Alias for Normal
    "Normal": 0.5,
    "Hard": 0.75,
    "Very Hard": 0.9,
    "Insane": 1.0,
}

# Codeforces: Rating -> Internal rating (linear interpolation between points)
# Format: [(cf_rating, internal_rating), ...]
CODEFORCES_MAPPING = [
    (800, 10),
    (1000, 20),
    (1200, 30),
    (1400, 40),
    (1600, 50),
    (1800, 60),
    (2000, 70),
    (2200, 80),
    (2400, 90),
    (2600, 95),
    (3000, 100),
]

# AtCoder: Contest type + problem index -> Internal rating
# First, we map by Kenkoooo difficulty if available, otherwise by contest/index
ATCODER_KENKOOOO_MAPPING = [
    (-1000, 5),
    (-500, 10),
    (0, 15),
    (200, 20),
    (400, 25),
    (600, 30),
    (800, 35),
    (1000, 40),
    (1200, 45),
    (1400, 50),
    (1600, 55),
    (1800, 60),
    (2000, 65),
    (2200, 70),
    (2400, 75),
    (2600, 80),
    (2800, 85),
    (3000, 90),
    (3200, 95),
    (3500, 100),
]

# AtCoder fallback: Contest type + index -> Internal rating (when no Kenkoooo rating)
ATCODER_FALLBACK_MAPPING = {
    # ABC (Beginner Contest)
    ("abc", "A"): 10,
    ("abc", "B"): 20,
    ("abc", "C"): 30,
    ("abc", "D"): 40,
    ("abc", "E"): 50,
    ("abc", "F"): 60,
    ("abc", "G"): 70,
    ("abc", "H"): 80,
    # ARC (Regular Contest)
    ("arc", "A"): 35,
    ("arc", "B"): 45,
    ("arc", "C"): 60,
    ("arc", "D"): 75,
    ("arc", "E"): 85,
    ("arc", "F"): 95,
    # AGC (Grand Contest)
    ("agc", "A"): 50,
    ("agc", "B"): 65,
    ("agc", "C"): 80,
    ("agc", "D"): 90,
    ("agc", "E"): 95,
    ("agc", "F"): 100,
}

# Skill tag priority (higher = more important for primary_skills)
# Tags not listed default to priority 0
SKILL_PRIORITY = {
    # Data Structures
    "Segment Tree": 10,
    "Fenwick Tree": 10,
    "BIT": 10,
    "Sparse Table": 9,
    "DSU": 9,
    "Union Find": 9,
    "Trie": 8,
    "Treap": 8,
    "Splay Tree": 8,

    # Algorithms
    "Dynamic Programming": 10,
    "DP": 10,
    "Binary Search": 9,
    "DFS": 8,
    "BFS": 8,
    "Graph Traversal": 8,
    "Dijkstra": 8,
    "Shortest Paths": 8,
    "MST": 7,
    "Topological Sort": 7,
    "Greedy": 7,
    "Two Pointers": 7,
    "Sliding Window": 7,
    "Divide and Conquer": 7,

    # Math
    "Number Theory": 6,
    "Combinatorics": 6,
    "Modular Arithmetic": 6,
    "Probability": 6,
    "Game Theory": 6,

    # Techniques
    "Prefix Sums": 5,
    "Sorting": 5,
    "Hashing": 5,
    "Bitmasks": 5,
    "Meet in the Middle": 5,
    "Sqrt Decomposition": 5,

    # Topics
    "Trees": 4,
    "Graphs": 4,
    "Strings": 4,
    "Geometry": 4,
    "Flows": 4,

    # General
    "Implementation": 2,
    "Simulation": 2,
    "Brute Force": 1,
    "Ad Hoc": 1,
}

# Pattern ID mapping: keyword in tags -> pattern_id
# Multiple keywords can map to the same pattern
PATTERN_KEYWORDS = {
    # DP Patterns
    "dp": "dp_general",
    "dynamic programming": "dp_general",
    "knapsack": "dp_knapsack",
    "lis": "dp_lis",
    "longest increasing subsequence": "dp_lis",
    "bitmask": "dp_bitmask",
    "dp on trees": "dp_trees",
    "digit dp": "dp_digit",
    "range dp": "dp_range",

    # Graph Patterns
    "dfs": "graph_traversal",
    "bfs": "graph_traversal",
    "graph traversal": "graph_traversal",
    "flood fill": "graph_flood_fill",
    "shortest path": "graph_shortest_path",
    "dijkstra": "graph_shortest_path",
    "bellman-ford": "graph_shortest_path",
    "floyd-warshall": "graph_shortest_path",
    "mst": "graph_mst",
    "minimum spanning tree": "graph_mst",
    "topological sort": "graph_topo",
    "toposort": "graph_topo",
    "dsu": "graph_dsu",
    "union find": "graph_dsu",
    "disjoint set": "graph_dsu",
    "scc": "graph_scc",
    "strongly connected": "graph_scc",
    "bipartite": "graph_bipartite",
    "cycle": "graph_cycle",
    "functional graph": "graph_functional",

    # Tree Patterns
    "tree": "tree_general",
    "lca": "tree_lca",
    "binary lifting": "tree_lca",
    "euler tour": "tree_euler",
    "centroid": "tree_centroid",
    "hld": "tree_hld",
    "heavy-light": "tree_hld",

    # Search Patterns
    "binary search": "search_binary",
    "ternary search": "search_ternary",
    "two pointers": "search_two_pointers",
    "2p": "search_two_pointers",
    "sliding window": "search_sliding_window",
    "meet in the middle": "search_mitm",

    # Data Structure Patterns
    "segment tree": "ds_segtree",
    "segtree": "ds_segtree",
    "fenwick": "ds_fenwick",
    "bit": "ds_fenwick",
    "sparse table": "ds_sparse_table",
    "monotonic stack": "ds_mono_stack",
    "monotonic queue": "ds_mono_queue",
    "deque": "ds_deque",
    "priority queue": "ds_pq",
    "heap": "ds_pq",
    "sorted set": "ds_sorted_set",
    "multiset": "ds_sorted_set",

    # Math Patterns
    "number theory": "math_nt",
    "prime": "math_prime",
    "sieve": "math_sieve",
    "gcd": "math_gcd",
    "modular": "math_modular",
    "combinatorics": "math_combo",
    "probability": "math_prob",
    "expected value": "math_prob",
    "game theory": "math_game",
    "nim": "math_game",

    # String Patterns
    "string": "string_general",
    "hashing": "string_hash",
    "kmp": "string_kmp",
    "z-function": "string_z",
    "suffix array": "string_suffix",
    "trie": "string_trie",

    # Geometry Patterns
    "geometry": "geo_general",
    "convex hull": "geo_convex_hull",
    "sweep line": "geo_sweep",
    "line sweep": "geo_sweep",

    # Technique Patterns
    "prefix sum": "tech_prefix",
    "difference array": "tech_difference",
    "greedy": "tech_greedy",
    "sorting": "tech_sorting",
    "simulation": "tech_simulation",
    "implementation": "tech_implementation",
    "constructive": "tech_constructive",
    "brute force": "tech_brute",
    "complete search": "tech_brute",
}

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class StandardizedProblem:
    """Standardized problem format."""
    # Identity
    id: str
    name: str
    url: str
    source: str  # "usaco_guide", "codeforces", "atcoder"

    # Original difficulty info
    original_difficulty: Optional[str]  # Original difficulty label/rating

    # Standardized fields
    internal_rating: int  # 1-100
    primary_skills: List[str]  # 1-3 main skills
    secondary_skills: List[str]  # 0-2 additional skills
    pattern_id: Optional[str]  # Pattern identifier or null

    # Metadata
    tags: List[str]  # All original tags
    extra: Dict[str, Any]  # Platform-specific extra data


class ValidationError:
    """Tracks validation issues."""
    def __init__(self):
        self.errors = []
        self.warnings = []

    def add_error(self, problem_id: str, message: str):
        self.errors.append(f"[ERROR] {problem_id}: {message}")

    def add_warning(self, problem_id: str, message: str):
        self.warnings.append(f"[WARN] {problem_id}: {message}")

    def report(self):
        print(f"\nValidation Report:")
        print(f"  Errors: {len(self.errors)}")
        print(f"  Warnings: {len(self.warnings)}")
        if self.errors:
            print("\nFirst 10 errors:")
            for err in self.errors[:10]:
                print(f"  {err}")
        if self.warnings:
            print(f"\nFirst 10 warnings:")
            for warn in self.warnings[:10]:
                print(f"  {warn}")


# =============================================================================
# DIFFICULTY CONVERSION FUNCTIONS
# =============================================================================

def linear_interpolate(value: float, mapping: List[Tuple[float, float]]) -> int:
    """
    Linearly interpolate a value using a mapping table.
    mapping: List of (input_value, output_value) tuples, sorted by input_value
    """
    if not mapping:
        return 50  # Default

    # Below minimum
    if value <= mapping[0][0]:
        return mapping[0][1]

    # Above maximum
    if value >= mapping[-1][0]:
        return mapping[-1][1]

    # Find the two points to interpolate between
    for i in range(len(mapping) - 1):
        x1, y1 = mapping[i]
        x2, y2 = mapping[i + 1]

        if x1 <= value <= x2:
            # Linear interpolation
            if x2 == x1:
                return y1
            ratio = (value - x1) / (x2 - x1)
            return int(round(y1 + ratio * (y2 - y1)))

    return mapping[-1][1]


def convert_usaco_difficulty(source: str, difficulty: Optional[str], validator: ValidationError, problem_id: str) -> int:
    """
    Convert USACO Guide difficulty to internal rating.

    Args:
        source: Division (Bronze, Silver, Gold, Platinum)
        difficulty: Difficulty label (Very Easy, Easy, Normal, Hard, Very Hard, Insane)
        validator: ValidationError instance for reporting issues
        problem_id: Problem ID for error reporting

    Returns:
        Internal rating (1-100)
    """
    # Determine division
    division = None
    for div in USACO_DIVISION_MAPPING:
        if div.lower() in source.lower():
            division = div
            break

    if not division:
        # Try to infer from common patterns
        if "silver" in source.lower():
            division = "Silver"
        elif "gold" in source.lower():
            division = "Gold"
        elif "plat" in source.lower():
            division = "Platinum"
        elif "bronze" in source.lower():
            division = "Bronze"
        elif "advanced" in source.lower() or "adv" in source.lower():
            division = "Advanced"
        else:
            # This is expected for problems from other sources (CSES, CF, etc.)
            # that are included in USACO Guide modules - use module division
            division = "Silver"  # Default fallback

    min_rating, max_rating = USACO_DIVISION_MAPPING[division]

    # Get difficulty multiplier
    if difficulty and difficulty in USACO_DIFFICULTY_MULTIPLIER:
        multiplier = USACO_DIFFICULTY_MULTIPLIER[difficulty]
    else:
        if difficulty:
            validator.add_warning(problem_id, f"Unknown difficulty label '{difficulty}', using Normal")
        multiplier = USACO_DIFFICULTY_MULTIPLIER["Normal"]

    # Calculate rating
    rating = min_rating + multiplier * (max_rating - min_rating)
    return int(round(rating))


def convert_codeforces_difficulty(rating: Optional[int], validator: ValidationError, problem_id: str) -> int:
    """
    Convert Codeforces rating to internal rating.

    Args:
        rating: Codeforces problem rating (800-3500, or None)
        validator: ValidationError instance
        problem_id: Problem ID for error reporting

    Returns:
        Internal rating (1-100)
    """
    if rating is None:
        validator.add_warning(problem_id, "No Codeforces rating, defaulting to 50")
        return 50

    return linear_interpolate(rating, CODEFORCES_MAPPING)


def convert_atcoder_difficulty(
    kenkoooo_difficulty: Optional[int],
    contest_id: Optional[str],
    problem_index: Optional[str],
    validator: ValidationError,
    problem_id: str
) -> int:
    """
    Convert AtCoder difficulty to internal rating.

    Uses Kenkoooo difficulty if available, otherwise falls back to contest type + index.

    Args:
        kenkoooo_difficulty: Difficulty rating from Kenkoooo (can be negative)
        contest_id: Contest ID (e.g., "abc200", "arc150", "agc050")
        problem_index: Problem index (e.g., "A", "B", "C")
        validator: ValidationError instance
        problem_id: Problem ID for error reporting

    Returns:
        Internal rating (1-100)
    """
    # Try Kenkoooo difficulty first
    if kenkoooo_difficulty is not None:
        return linear_interpolate(kenkoooo_difficulty, ATCODER_KENKOOOO_MAPPING)

    # Fallback to contest type + index
    if contest_id and problem_index:
        # Extract contest type (abc, arc, agc, etc.)
        contest_type = None
        for prefix in ["abc", "arc", "agc"]:
            if contest_id.lower().startswith(prefix):
                contest_type = prefix
                break

        if contest_type:
            # Normalize problem index (take first character)
            idx = problem_index.upper()[0] if problem_index else "A"
            key = (contest_type, idx)

            if key in ATCODER_FALLBACK_MAPPING:
                return ATCODER_FALLBACK_MAPPING[key]
            else:
                # Index not in mapping, estimate based on position
                base = ATCODER_FALLBACK_MAPPING.get((contest_type, "A"), 30)
                offset = (ord(idx) - ord('A')) * 10
                return min(100, base + offset)

    validator.add_warning(problem_id, "No AtCoder difficulty info, defaulting to 40")
    return 40


# =============================================================================
# SKILL EXTRACTION
# =============================================================================

def normalize_tag(tag: str) -> str:
    """Normalize a tag for comparison."""
    return tag.lower().strip()


def extract_skills(tags: List[str]) -> Tuple[List[str], List[str]]:
    """
    Extract primary and secondary skills from tags.

    Args:
        tags: List of original tags

    Returns:
        (primary_skills, secondary_skills)
        primary_skills: 1-3 most important skills
        secondary_skills: 0-2 additional skills
    """
    if not tags:
        return [], []

    # Score each tag by priority
    scored_tags = []
    for tag in tags:
        normalized = normalize_tag(tag)

        # Find best matching priority
        priority = 0
        for skill, p in SKILL_PRIORITY.items():
            if normalize_tag(skill) == normalized or normalize_tag(skill) in normalized:
                priority = max(priority, p)

        scored_tags.append((tag, priority))

    # Sort by priority (descending), then alphabetically
    scored_tags.sort(key=lambda x: (-x[1], x[0]))

    # Select primary skills (1-3, priority > 0)
    primary = []
    for tag, priority in scored_tags:
        if priority > 0 and len(primary) < 3:
            primary.append(tag)

    # If no high-priority tags, take first 1-2
    if not primary and tags:
        primary = tags[:min(2, len(tags))]

    # Select secondary skills (next 0-2, not in primary)
    secondary = []
    for tag, priority in scored_tags:
        if tag not in primary and len(secondary) < 2:
            secondary.append(tag)

    return primary, secondary


def identify_pattern(tags: List[str]) -> Optional[str]:
    """
    Identify a pattern from tags.

    Args:
        tags: List of original tags

    Returns:
        Pattern ID or None
    """
    if not tags:
        return None

    # Check each tag against pattern keywords
    for tag in tags:
        normalized = normalize_tag(tag)

        # Direct match
        if normalized in PATTERN_KEYWORDS:
            return PATTERN_KEYWORDS[normalized]

        # Partial match
        for keyword, pattern_id in PATTERN_KEYWORDS.items():
            if keyword in normalized:
                return pattern_id

    return None


# =============================================================================
# PROBLEM PROCESSING
# =============================================================================

def process_usaco_problem(problem: Dict, module_info: Dict, division: str, validator: ValidationError) -> StandardizedProblem:
    """Process a single USACO Guide problem."""
    problem_id = problem.get("uniqueId", "unknown")

    # Get source - prefer division from module context over problem's source field
    # Problem source might be "CSES", "CF", "AC" etc. which doesn't indicate difficulty
    problem_source = problem.get("source", "")

    # Use module division for rating, but track original source
    # Only use problem source if it's a USACO division
    if problem_source.lower() in ["bronze", "silver", "gold", "platinum", "advanced"]:
        rating_source = problem_source
    else:
        rating_source = division.capitalize()

    # Get difficulty
    difficulty = problem.get("difficulty")
    internal_rating = convert_usaco_difficulty(rating_source, difficulty, validator, problem_id)

    # Get tags
    tags = problem.get("tags", [])

    # Extract skills
    primary_skills, secondary_skills = extract_skills(tags)

    # Identify pattern
    pattern_id = identify_pattern(tags)

    return StandardizedProblem(
        id=problem_id,
        name=problem.get("name", "Unknown"),
        url=problem.get("url", ""),
        source="usaco_guide",
        original_difficulty=f"{rating_source} - {difficulty}" if difficulty else rating_source,
        internal_rating=internal_rating,
        primary_skills=primary_skills,
        secondary_skills=secondary_skills,
        pattern_id=pattern_id,
        tags=tags,
        extra={
            "division": division,
            "module_id": module_info.get("module_id"),
            "module_name": module_info.get("module_name"),
            "category": problem.get("category"),
            "isStarred": problem.get("isStarred", False),
            "original_source": problem_source,  # Track original source (CSES, CF, etc.)
        }
    )


def process_codeforces_problem(problem: Dict, validator: ValidationError) -> StandardizedProblem:
    """Process a single Codeforces problem."""
    contest_id = problem.get("contestId")
    index = problem.get("index", "")
    problem_id = f"cf-{contest_id}-{index}" if contest_id else f"cf-{problem.get('name', 'unknown')}"

    # Get rating
    rating = problem.get("rating")
    internal_rating = convert_codeforces_difficulty(rating, validator, problem_id)

    # Get tags
    tags = problem.get("tags", [])

    # Extract skills
    primary_skills, secondary_skills = extract_skills(tags)

    # Identify pattern
    pattern_id = identify_pattern(tags)

    return StandardizedProblem(
        id=problem_id,
        name=problem.get("name", "Unknown"),
        url=problem.get("url", ""),
        source="codeforces",
        original_difficulty=str(rating) if rating else "unrated",
        internal_rating=internal_rating,
        primary_skills=primary_skills,
        secondary_skills=secondary_skills,
        pattern_id=pattern_id,
        tags=tags,
        extra={
            "contestId": contest_id,
            "index": index,
            "type": problem.get("type"),
            "solvedCount": problem.get("solvedCount", 0),
        }
    )


def process_atcoder_problem(problem: Dict, validator: ValidationError) -> StandardizedProblem:
    """Process a single AtCoder problem."""
    problem_id = problem.get("id", "unknown")

    # Get difficulty
    kenkoooo_diff = problem.get("difficulty")
    contest_id = problem.get("contest_id")
    problem_index = problem.get("problem_index")

    internal_rating = convert_atcoder_difficulty(
        kenkoooo_diff, contest_id, problem_index, validator, problem_id
    )

    # AtCoder doesn't have tags in the Kenkoooo API, so we'll derive from contest type
    tags = []
    if contest_id:
        if contest_id.startswith("abc"):
            tags.append("AtCoder Beginner")
        elif contest_id.startswith("arc"):
            tags.append("AtCoder Regular")
        elif contest_id.startswith("agc"):
            tags.append("AtCoder Grand")

    # Extract skills (limited for AtCoder)
    primary_skills, secondary_skills = extract_skills(tags)

    # Pattern ID (limited for AtCoder)
    pattern_id = None

    return StandardizedProblem(
        id=f"atcoder-{problem_id}",
        name=problem.get("name", problem.get("title", "Unknown")),
        url=problem.get("url", ""),
        source="atcoder",
        original_difficulty=str(kenkoooo_diff) if kenkoooo_diff is not None else f"{contest_id}-{problem_index}",
        internal_rating=internal_rating,
        primary_skills=primary_skills,
        secondary_skills=secondary_skills,
        pattern_id=pattern_id,
        tags=tags,
        extra={
            "contest_id": contest_id,
            "problem_index": problem_index,
            "contest_title": problem.get("contest_title"),
            "kenkoooo_difficulty": kenkoooo_diff,
            "is_experimental": problem.get("is_experimental"),
            "rate_change": problem.get("rate_change"),
        }
    )


# =============================================================================
# MAIN PROCESSING
# =============================================================================

def load_json(filepath: str) -> Optional[Dict]:
    """Load JSON file if it exists."""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def main():
    print("=" * 60)
    print("Problem Difficulty Standardization")
    print("=" * 60)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")

    all_problems: List[StandardizedProblem] = []
    validator = ValidationError()

    # -------------------------------------------------------------------------
    # Load and process USACO Guide problems
    # -------------------------------------------------------------------------
    print("\nProcessing USACO Guide problems...")

    for division in ["silver", "gold", "platinum"]:
        filepath = os.path.join(output_dir, f"usaco_guide_{division}.json")
        data = load_json(filepath)

        if data:
            modules = data.get("modules", [])
            count = 0
            for module in modules:
                for problem in module.get("problems", []):
                    std_problem = process_usaco_problem(problem, module, division, validator)
                    all_problems.append(std_problem)
                    count += 1
            print(f"  {division.capitalize()}: {count} problems")
        else:
            print(f"  {division.capitalize()}: File not found ({filepath})")

    # -------------------------------------------------------------------------
    # Load and process Codeforces problems
    # -------------------------------------------------------------------------
    print("\nProcessing Codeforces problems...")

    cf_filepath = os.path.join(output_dir, "codeforces_problems.json")
    cf_data = load_json(cf_filepath)

    if cf_data:
        problems = cf_data.get("problems", [])
        for problem in problems:
            std_problem = process_codeforces_problem(problem, validator)
            all_problems.append(std_problem)
        print(f"  Processed: {len(problems)} problems")
    else:
        print(f"  File not found ({cf_filepath})")

    # -------------------------------------------------------------------------
    # Load and process AtCoder problems
    # -------------------------------------------------------------------------
    print("\nProcessing AtCoder problems...")

    atcoder_filepath = os.path.join(output_dir, "atcoder_problems.json")
    atcoder_data = load_json(atcoder_filepath)

    if atcoder_data:
        problems = atcoder_data.get("problems", [])
        for problem in problems:
            std_problem = process_atcoder_problem(problem, validator)
            all_problems.append(std_problem)
        print(f"  Processed: {len(problems)} problems")
    else:
        print(f"  File not found ({atcoder_filepath})")

    # -------------------------------------------------------------------------
    # Validation and Statistics
    # -------------------------------------------------------------------------
    validator.report()

    # Statistics
    print("\n" + "=" * 60)
    print("Statistics")
    print("=" * 60)

    by_source = {}
    by_rating_range = {
        "1-25 (Beginner)": 0,
        "26-50 (Intermediate)": 0,
        "51-75 (Advanced)": 0,
        "76-100 (Expert)": 0,
    }

    for p in all_problems:
        by_source[p.source] = by_source.get(p.source, 0) + 1

        if p.internal_rating <= 25:
            by_rating_range["1-25 (Beginner)"] += 1
        elif p.internal_rating <= 50:
            by_rating_range["26-50 (Intermediate)"] += 1
        elif p.internal_rating <= 75:
            by_rating_range["51-75 (Advanced)"] += 1
        else:
            by_rating_range["76-100 (Expert)"] += 1

    print(f"\nTotal problems: {len(all_problems)}")
    print("\nBy source:")
    for source, count in sorted(by_source.items()):
        print(f"  {source}: {count}")

    print("\nBy internal rating range:")
    for range_name, count in by_rating_range.items():
        print(f"  {range_name}: {count}")

    # -------------------------------------------------------------------------
    # Save standardized problems
    # -------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Saving output...")
    print("=" * 60)

    output_path = os.path.join(output_dir, "standardized_problems.json")

    # Convert to dict for JSON serialization
    output_data = {
        "metadata": {
            "total_problems": len(all_problems),
            "sources": list(by_source.keys()),
            "rating_distribution": by_rating_range,
        },
        "problems": [asdict(p) for p in all_problems]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Saved: {output_path}")
    print(f"File size: {os.path.getsize(output_path) / (1024*1024):.2f} MB")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()

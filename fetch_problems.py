#!/usr/bin/env python3
"""
Fetches problems from USACO Guide (via GitHub), Codeforces API, and AtCoder (via Kenkoooo).
Saves all data to the output folder.
"""

import json
import time
import requests
import os
from typing import Dict, List, Any

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# Module definitions - actual file names from USACO Guide GitHub
MODULES = {
    "silver": {
        "folder": "3_Silver",
        "modules": [
            "Prefix_Sums",
            "More_Prefix_Sums",
            "Two_Pointers",
            "Binary_Search_Sorted_Array",
            "Binary_Search",
            "Sorting_Custom",
            "Greedy_Sorting",
            "Priority_Queues",
            "Graph_Traversal",
            "Flood_Fill",
            "Intro_Tree",
            "Func_Graphs",
            "Intro_Bitwise",
            "Conclusion"
        ]
    },
    "gold": {
        "folder": "4_Gold",
        "modules": [
            "Divisibility",
            "Modular",
            "Combinatorics",
            "Intro_DP",
            "Knapsack_DP",
            "Paths_Grids",
            "LIS",
            "DP_Bitmasks",
            "DP_Ranges",
            "Digit_DP",
            "Unweighted_Shortest_Paths",
            "DSU",
            "TopoSort",
            "Shortest_Paths",
            "MST",
            "Intro_Sorted_Sets",
            "Custom_Cpp_STL",
            "Stacks",
            "Sliding_Window",
            "PURS",
            "Tree_Euler",
            "DP_Trees",
            "All_Roots",
            "Hashing",
            "Hashmaps",
            "Meet_In_The_Middle",
            "Ternary_Search",
            "Conclusion"
        ]
    },
    "platinum": {
        "folder": "5_Plat",
        "modules": [
            "Segtree_Ext",
            "Range_Sweep",
            "RURQ",
            "Sparse_Segtree",
            "2DRQ",
            "DC-SRQ",
            "Sqrt",
            "Binary_Jump",
            "Merging",
            "HLD",
            "Centroid",
            "VTree",
            "kruskal-tree",
            "Geo_Pri",
            "Sweep_Line",
            "Convex_Hull",
            "Convex_Hull_Trick",
            "PIE",
            "Matrix_Expo",
            "Bitsets",
            "DC-DP",
            "DP_SOS",
            "Conclusion"
        ]
    }
}

# GitHub raw content base URL
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/cpinitiative/usaco-guide/master/content"

# Delay between requests (in seconds)
REQUEST_DELAY = 1.0


def fetch_with_retry(url: str, max_retries: int = 3) -> requests.Response:
    """Fetch URL with retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response
            elif response.status_code == 404:
                print(f"  Not found: {url}")
                return response
            else:
                print(f"  Attempt {attempt + 1}: Status {response.status_code} for {url}")
        except requests.RequestException as e:
            print(f"  Attempt {attempt + 1}: Error fetching {url}: {e}")

        if attempt < max_retries - 1:
            time.sleep(REQUEST_DELAY * 2)

    return None


def fetch_usaco_guide_problems() -> Dict[str, Any]:
    """Fetch all problems from USACO Guide GitHub repository."""
    all_problems = {}

    for division, config in MODULES.items():
        print(f"\nFetching {division.upper()} division...")
        division_problems = {
            "division": division,
            "modules": []
        }

        for module_name in config["modules"]:
            # Construct the URL for the problems JSON file
            url = f"{GITHUB_RAW_BASE}/{config['folder']}/{module_name}.problems.json"
            print(f"  Fetching {module_name}...")

            response = fetch_with_retry(url)

            if response and response.status_code == 200:
                try:
                    problems_data = response.json()

                    # Extract all problems from the module
                    module_entry = {
                        "module_id": problems_data.get("MODULE_ID", module_name.lower().replace("_", "-")),
                        "module_name": module_name.replace("_", " "),
                        "problems": []
                    }

                    # Iterate through all problem categories in the JSON
                    for key, problems in problems_data.items():
                        if key != "MODULE_ID" and isinstance(problems, list):
                            for problem in problems:
                                problem_entry = {
                                    "uniqueId": problem.get("uniqueId"),
                                    "name": problem.get("name"),
                                    "url": problem.get("url"),
                                    "source": problem.get("source"),
                                    "difficulty": problem.get("difficulty"),
                                    "isStarred": problem.get("isStarred", False),
                                    "tags": problem.get("tags", []),
                                    "category": key  # ex, usaco, general, etc.
                                }
                                module_entry["problems"].append(problem_entry)

                    division_problems["modules"].append(module_entry)
                    print(f"    Found {len(module_entry['problems'])} problems")

                except json.JSONDecodeError as e:
                    print(f"    Error parsing JSON: {e}")
            else:
                print(f"    Could not fetch module: {module_name}")

            # Delay between requests
            time.sleep(REQUEST_DELAY)

        all_problems[division] = division_problems

    return all_problems


def fetch_codeforces_problems() -> Dict[str, Any]:
    """Fetch all problems from Codeforces API."""
    print("\nFetching Codeforces problems...")

    url = "https://codeforces.com/api/problemset.problems"
    response = fetch_with_retry(url)

    if response and response.status_code == 200:
        try:
            data = response.json()
            if data.get("status") == "OK":
                result = data.get("result", {})
                problems = result.get("problems", [])
                problem_statistics = result.get("problemStatistics", [])

                print(f"  Found {len(problems)} problems")

                # Create a lookup for solved counts
                solved_counts = {}
                for stat in problem_statistics:
                    key = f"{stat.get('contestId')}-{stat.get('index')}"
                    solved_counts[key] = stat.get("solvedCount", 0)

                # Process problems
                processed_problems = []
                for problem in problems:
                    contest_id = problem.get("contestId")
                    index = problem.get("index")

                    problem_entry = {
                        "contestId": contest_id,
                        "index": index,
                        "name": problem.get("name"),
                        "type": problem.get("type"),
                        "rating": problem.get("rating"),
                        "tags": problem.get("tags", []),
                        "url": f"https://codeforces.com/problemset/problem/{contest_id}/{index}" if contest_id else None,
                        "solvedCount": solved_counts.get(f"{contest_id}-{index}", 0)
                    }
                    processed_problems.append(problem_entry)

                return {
                    "source": "codeforces",
                    "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                    "total_problems": len(processed_problems),
                    "problems": processed_problems
                }
            else:
                print(f"  API error: {data.get('comment', 'Unknown error')}")
        except json.JSONDecodeError as e:
            print(f"  Error parsing JSON: {e}")
    else:
        print("  Failed to fetch Codeforces problems")

    return None


def fetch_atcoder_problems() -> Dict[str, Any]:
    """Fetch all problems from AtCoder via Kenkoooo's API."""
    print("\nFetching AtCoder problems (via Kenkoooo)...")

    # Kenkoooo API endpoints
    problems_url = "https://kenkoooo.com/atcoder/resources/problems.json"
    difficulty_url = "https://kenkoooo.com/atcoder/resources/problem-models.json"
    contests_url = "https://kenkoooo.com/atcoder/resources/contests.json"

    # Fetch problems
    print("  Fetching problems list...")
    problems_response = fetch_with_retry(problems_url)
    if not problems_response or problems_response.status_code != 200:
        print("  Failed to fetch AtCoder problems")
        return None

    time.sleep(REQUEST_DELAY)

    # Fetch difficulty ratings
    print("  Fetching difficulty ratings...")
    difficulty_response = fetch_with_retry(difficulty_url)
    difficulty_map = {}
    if difficulty_response and difficulty_response.status_code == 200:
        try:
            difficulty_map = difficulty_response.json()
            print(f"    Got ratings for {len(difficulty_map)} problems")
        except json.JSONDecodeError:
            print("    Could not parse difficulty data")

    time.sleep(REQUEST_DELAY)

    # Fetch contest info
    print("  Fetching contest info...")
    contests_response = fetch_with_retry(contests_url)
    contests_map = {}
    if contests_response and contests_response.status_code == 200:
        try:
            contests_list = contests_response.json()
            for contest in contests_list:
                contests_map[contest.get("id")] = {
                    "title": contest.get("title"),
                    "start_epoch_second": contest.get("start_epoch_second"),
                    "duration_second": contest.get("duration_second"),
                    "rate_change": contest.get("rate_change")
                }
            print(f"    Got info for {len(contests_map)} contests")
        except json.JSONDecodeError:
            print("    Could not parse contest data")

    # Process problems
    try:
        problems_list = problems_response.json()
        print(f"  Found {len(problems_list)} problems")

        processed_problems = []
        for problem in problems_list:
            problem_id = problem.get("id")
            contest_id = problem.get("contest_id")

            # Get difficulty info
            diff_info = difficulty_map.get(problem_id, {})
            difficulty = diff_info.get("difficulty") if diff_info else None

            # Get contest info
            contest_info = contests_map.get(contest_id, {})

            problem_entry = {
                "id": problem_id,
                "contest_id": contest_id,
                "problem_index": problem.get("problem_index"),
                "name": problem.get("name"),
                "title": problem.get("title"),
                "url": f"https://atcoder.jp/contests/{contest_id}/tasks/{problem_id}" if contest_id else None,
                "difficulty": difficulty,
                "is_experimental": diff_info.get("is_experimental") if diff_info else None,
                "contest_title": contest_info.get("title"),
                "contest_start_epoch": contest_info.get("start_epoch_second"),
                "rate_change": contest_info.get("rate_change")
            }
            processed_problems.append(problem_entry)

        # Categorize by contest type
        abc_problems = [p for p in processed_problems if p["contest_id"] and p["contest_id"].startswith("abc")]
        arc_problems = [p for p in processed_problems if p["contest_id"] and p["contest_id"].startswith("arc")]
        agc_problems = [p for p in processed_problems if p["contest_id"] and p["contest_id"].startswith("agc")]
        other_problems = [p for p in processed_problems if p["contest_id"] and not any(
            p["contest_id"].startswith(prefix) for prefix in ["abc", "arc", "agc"]
        )]

        return {
            "source": "atcoder",
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "total_problems": len(processed_problems),
            "by_contest_type": {
                "abc": len(abc_problems),
                "arc": len(arc_problems),
                "agc": len(agc_problems),
                "other": len(other_problems)
            },
            "problems": processed_problems
        }

    except json.JSONDecodeError as e:
        print(f"  Error parsing JSON: {e}")
        return None


def save_json(data: Any, filename: str) -> None:
    """Save data to JSON file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Saved: {filepath}")


def main():
    print("=" * 60)
    print("USACO Guide, Codeforces & AtCoder Problem Fetcher")
    print("=" * 60)

    # Fetch USACO Guide problems
    usaco_problems = fetch_usaco_guide_problems()

    # Save each division separately
    for division, data in usaco_problems.items():
        save_json(data, f"usaco_guide_{division}.json")

    # Save combined USACO Guide data
    save_json(usaco_problems, "usaco_guide_all.json")

    # Add delay before Codeforces request
    print("\nWaiting before Codeforces request...")
    time.sleep(REQUEST_DELAY * 2)

    # Fetch Codeforces problems
    cf_problems = fetch_codeforces_problems()
    if cf_problems:
        save_json(cf_problems, "codeforces_problems.json")

    # Add delay before AtCoder request
    print("\nWaiting before AtCoder request...")
    time.sleep(REQUEST_DELAY * 2)

    # Fetch AtCoder problems
    atcoder_problems = fetch_atcoder_problems()
    if atcoder_problems:
        save_json(atcoder_problems, "atcoder_problems.json")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)

    # Print summary
    print("\nSummary:")
    for division, data in usaco_problems.items():
        total = sum(len(m["problems"]) for m in data["modules"])
        print(f"  {division.upper()}: {total} problems across {len(data['modules'])} modules")

    if cf_problems:
        print(f"  Codeforces: {cf_problems['total_problems']} problems")

    if atcoder_problems:
        print(f"  AtCoder: {atcoder_problems['total_problems']} problems")
        print(f"    ABC: {atcoder_problems['by_contest_type']['abc']}")
        print(f"    ARC: {atcoder_problems['by_contest_type']['arc']}")
        print(f"    AGC: {atcoder_problems['by_contest_type']['agc']}")
        print(f"    Other: {atcoder_problems['by_contest_type']['other']}")


if __name__ == "__main__":
    main()

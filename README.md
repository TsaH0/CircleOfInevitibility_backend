# MasterCP Contest System - Backend API

A competitive programming practice system that recommends problems based on user rating, tracks weak topics, and provides personalized practice contests.

## Quick Start

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API Documentation: `http://localhost:8000/docs`

---

## API Endpoints

### Root & Health

#### `GET /`
Returns API information.

**Response:**
```json
{
  "name": "MasterCP Contest System",
  "version": "1.0.0",
  "docs": "/docs",
  "endpoints": {
    "users": "/users",
    "contests": "/contests"
  }
}
```

#### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

#### `GET /stats`
System statistics.

**Response:**
```json
{
  "total_users": 5,
  "total_contests": 12,
  "active_contests": 1,
  "completed_contests": 10,
  "total_problems_available": 20070
}
```

---

### Users

#### `POST /users/`
Create a new user.

**Request Body:**
```json
{
  "username": "alice",
  "email": "alice@example.com"  // optional
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "rating": 20,
  "total_contests": 0,
  "total_problems_solved": 0,
  "total_problems_attempted": 0,
  "created_at": "2026-01-21T19:30:00",
  "updated_at": "2026-01-21T19:30:00"
}
```

**Errors:**
- `400`: Username already exists

---

#### `GET /users/`
List all users (sorted by rating descending).

**Query Parameters:**
- `skip` (int, default: 0): Number of users to skip
- `limit` (int, default: 100): Maximum users to return

**Response:**
```json
[
  {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "rating": 40,
    "total_contests": 5,
    "total_problems_solved": 17,
    "total_problems_attempted": 25,
    "created_at": "2026-01-21T19:30:00",
    "updated_at": "2026-01-21T19:50:00"
  }
]
```

---

#### `GET /users/{user_id}`
Get user details including topic ratings and weak topics.

**Response:**
```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "rating": 40,
  "total_contests": 5,
  "total_problems_solved": 17,
  "total_problems_attempted": 25,
  "created_at": "2026-01-21T19:30:00",
  "updated_at": "2026-01-21T19:50:00",
  "topic_ratings": [
    {
      "topic": "dp_general",
      "rating": 35,
      "problems_solved": 2,
      "problems_attempted": 3
    }
  ],
  "weak_topics": [
    {
      "id": 1,
      "topic": "tech_difference",
      "current_level": 15,
      "target_level": 40,
      "consecutive_solves": 1,
      "total_attempts": 2,
      "total_failures": 0,
      "detected_at": "2026-01-21T19:45:00",
      "last_attempt_at": "2026-01-21T19:50:00",
      "is_active": true
    }
  ]
}
```

**Errors:**
- `404`: User not found

---

#### `GET /users/by-username/{username}`
Get user by username.

**Response:** Same as `GET /users/{user_id}`

---

#### `PATCH /users/{user_id}`
Update user details.

**Request Body:**
```json
{
  "email": "newemail@example.com"
}
```

**Response:** Updated user object

---

#### `DELETE /users/{user_id}`
Delete a user.

**Response:** `204 No Content`

---

#### `GET /users/{user_id}/topic-ratings`
Get user's ratings for all topics.

**Response:**
```json
[
  {
    "topic": "dp_general",
    "rating": 35,
    "problems_solved": 2,
    "problems_attempted": 3
  },
  {
    "topic": "graph_traversal",
    "rating": 30,
    "problems_solved": 1,
    "problems_attempted": 2
  }
]
```

---

#### `GET /users/{user_id}/weak-topics`
Get user's weak topics.

**Query Parameters:**
- `active_only` (bool, default: true): Only return active weak topics

**Response:**
```json
[
  {
    "id": 1,
    "topic": "tech_difference",
    "current_level": 15,
    "target_level": 40,
    "consecutive_solves": 1,
    "total_attempts": 2,
    "total_failures": 0,
    "detected_at": "2026-01-21T19:45:00",
    "last_attempt_at": "2026-01-21T19:50:00",
    "is_active": true
  }
]
```

---

#### `GET /users/{user_id}/statistics`
Get comprehensive user statistics.

**Response:**
```json
{
  "user_id": 1,
  "username": "alice",
  "rating": 40,
  "rating_history": [
    {"date": "2026-01-21T19:35:00", "rating": 30, "change": 10},
    {"date": "2026-01-21T19:50:00", "rating": 40, "change": 10}
  ],
  "topic_distribution": {
    "dp_general": 2,
    "graph_traversal": 1,
    "binary_search": 3
  },
  "weak_topics_count": 1,
  "average_solve_time": 285.5,
  "contests_completed": 5,
  "win_rate": 40.0
}
```

---

### Contests

#### `POST /contests/start/{user_id}`
Start a new contest for a user.

**Request Body:**
```json
{
  "num_problems": 5,           // 3-10, default: 5
  "time_limit_minutes": 120,   // 30-300, default: 120
  "include_weak_topics": true  // default: true
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "user_id": 1,
  "status": "active",
  "rating_at_start": 30,
  "rating_change": 0,
  "num_problems": 5,
  "target_difficulty": 40,
  "started_at": "2026-01-21T19:40:00",
  "ended_at": null,
  "time_limit_minutes": 120,
  "problems_solved": 0,
  "total_time_seconds": 0,
  "problems": [
    {
      "id": 1,
      "problem_id": "cf-1234-A",
      "problem_name": "Example Problem",
      "problem_url": "https://codeforces.com/problemset/problem/1234/A",
      "topic": "dp_general",
      "difficulty": 38,
      "source": "codeforces",
      "is_weak_topic_problem": false,
      "status": "pending",
      "started_at": null,
      "submitted_at": null,
      "time_taken_seconds": null,
      "attempts": 0
    },
    {
      "id": 2,
      "problem_id": "usaco-567",
      "problem_name": "Barn Problem",
      "problem_url": "http://usaco.org/...",
      "topic": "tech_difference",
      "difficulty": 25,
      "source": "usaco_guide",
      "is_weak_topic_problem": true,
      "status": "pending",
      "started_at": null,
      "submitted_at": null,
      "time_taken_seconds": null,
      "attempts": 0
    }
  ]
}
```

**Errors:**
- `400`: User already has an active contest
- `400`: Could not find enough problems
- `404`: User not found

---

#### `GET /contests/active/{user_id}`
Get user's currently active contest.

**Response:** Contest object (same as above) or `null` if no active contest

---

#### `GET /contests/{contest_id}`
Get contest details by ID.

**Response:** Contest object with problems

---

#### `POST /contests/{contest_id}/start-problem/{problem_id}`
Mark a problem as started (begins timing).

**Response:** Updated contest object

---

#### `POST /contests/{contest_id}/submit`
Submit a solution for a problem.

**Request Body:**
```json
{
  "problem_id": "cf-1234-A",
  "solved": true,
  "time_taken_seconds": 300  // optional, calculated from start if not provided
}
```

**Response:**
```json
{
  "contest_id": 1,
  "problem_id": "cf-1234-A",
  "status": "solved",
  "time_taken_seconds": 300,
  "message": "Problem submitted successfully"
}
```

**Status Values:** `"solved"`, `"failed"`, `"pending"`, `"skipped"`

**Errors:**
- `400`: Contest not active
- `400`: Contest time limit exceeded
- `400`: Problem not found in contest

---

#### `POST /contests/{contest_id}/submit-all`
Submit multiple problems at once.

**Request Body:**
```json
{
  "submissions": [
    {"problem_id": "cf-1234-A", "solved": true, "time_taken_seconds": 300},
    {"problem_id": "cf-1234-B", "solved": false, "time_taken_seconds": 600},
    {"problem_id": "cf-1234-C", "solved": true, "time_taken_seconds": 450}
  ]
}
```

**Response:**
```json
[
  {"contest_id": 1, "problem_id": "cf-1234-A", "status": "solved", "time_taken_seconds": 300, "message": "Problem submitted successfully"},
  {"contest_id": 1, "problem_id": "cf-1234-B", "status": "failed", "time_taken_seconds": 600, "message": "Problem submitted successfully"},
  {"contest_id": 1, "problem_id": "cf-1234-C", "status": "solved", "time_taken_seconds": 450, "message": "Problem submitted successfully"}
]
```

---

#### `POST /contests/{contest_id}/skip/{problem_id}`
Skip a problem (counts as failed).

**Response:** Updated contest object

---

#### `POST /contests/{contest_id}/end`
End a contest and calculate results.

**Response:**
```json
{
  "contest_id": 1,
  "status": "completed",
  "problems_solved": 4,
  "total_problems": 5,
  "total_time_seconds": 1350,
  "old_rating": 30,
  "new_rating": 30,
  "rating_change": 0,
  "topics_passed": ["dp_general", "graph_traversal", "binary_search", "greedy"],
  "topics_failed": ["tech_difference"],
  "new_weak_topics": ["tech_difference"],
  "weak_topics_improved": [],
  "problems": [
    {
      "problem_id": "cf-1234-A",
      "problem_name": "Example Problem",
      "topic": "dp_general",
      "difficulty": 38,
      "solved": true,
      "time_taken_seconds": 300,
      "is_weak_topic_problem": false
    },
    {
      "problem_id": "cf-1234-B",
      "problem_name": "Hard Problem",
      "topic": "tech_difference",
      "difficulty": 42,
      "solved": false,
      "time_taken_seconds": 600,
      "is_weak_topic_problem": false
    }
  ]
}
```

**Rating Rules:**
- All problems solved → `rating_change: +10`
- Any problem failed → `rating_change: 0`

---

#### `POST /contests/{contest_id}/abandon`
Abandon a contest without rating changes.

**Response:** Contest object with `status: "abandoned"`

---

#### `GET /contests/history/{user_id}`
Get user's contest history.

**Query Parameters:**
- `limit` (int, default: 10)
- `offset` (int, default: 0)

**Response:**
```json
[
  {
    "id": 5,
    "user_id": 1,
    "status": "completed",
    "rating_at_start": 30,
    "rating_change": 10,
    "num_problems": 5,
    "target_difficulty": 40,
    "started_at": "2026-01-21T19:50:00",
    "ended_at": "2026-01-21T20:10:00",
    "time_limit_minutes": 120,
    "problems_solved": 5,
    "total_time_seconds": 1500
  }
]
```

---

#### `GET /contests/history/{user_id}/{contest_id}`
Get detailed contest information.

**Response:** Full contest object with problems

---

## Data Models

### User
| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique identifier |
| username | string | Unique username (3-50 chars) |
| email | string? | Optional email |
| rating | int | Current rating (1-100 scale) |
| total_contests | int | Number of contests completed |
| total_problems_solved | int | Total problems solved |
| total_problems_attempted | int | Total problems attempted |

### Contest
| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique identifier |
| user_id | int | Owner user ID |
| status | enum | `active`, `completed`, `abandoned` |
| rating_at_start | int | User's rating when contest started |
| rating_change | int | Rating change after contest |
| num_problems | int | Number of problems (3-10) |
| target_difficulty | int | Target difficulty (user_rating + 10) |
| time_limit_minutes | int | Time limit in minutes |
| problems_solved | int | Number solved |
| total_time_seconds | int | Total solve time |

### ContestProblem
| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique identifier |
| problem_id | string | Problem ID from source |
| problem_name | string | Problem name |
| problem_url | string | Link to problem |
| topic | string | Primary topic/pattern |
| difficulty | int | Internal difficulty (1-100) |
| source | string | `codeforces`, `atcoder`, `usaco_guide` |
| is_weak_topic_problem | bool | From weak topic? |
| status | enum | `pending`, `solved`, `failed`, `skipped` |
| time_taken_seconds | int? | Time to solve |

### WeakTopic
| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique identifier |
| topic | string | Topic identifier |
| current_level | int | Current practice level |
| target_level | int | Target level to resolve |
| consecutive_solves | int | Consecutive solves at current level |
| total_attempts | int | Total attempts |
| total_failures | int | Total failures |
| is_active | bool | Still active? |

---

## Rating System

### Rating Scale
- **1-25**: Beginner
- **26-50**: Intermediate
- **51-75**: Advanced
- **76-100**: Expert

### Rating Changes
- **All problems solved**: +10 rating
- **Any problem failed**: No change (0)

### Weak Topic Detection
- Detected after 2+ attempts on a topic with ≥50% failure rate
- Starts at `current_level = user_rating - 20`
- Target: `user_rating + 10`
- Progress: 2 consecutive solves → level up by 5
- Resolved when `current_level >= target_level`

---

## Problem Sources

| Source | Count | Description |
|--------|-------|-------------|
| Codeforces | ~11,000 | CF problems with ratings |
| AtCoder | ~8,000 | ABC/ARC/AGC problems |
| USACO Guide | ~900 | Curated USACO problems |

---

## Error Responses

All errors follow this format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

Common HTTP status codes:
- `400`: Bad Request (invalid input)
- `404`: Not Found (resource doesn't exist)
- `500`: Internal Server Error

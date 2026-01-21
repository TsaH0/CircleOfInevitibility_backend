"""
MasterCP Contest System - FastAPI Application

A competitive programming practice system that:
- Recommends problems at user's rating + 10
- Tracks weak topics and provides targeted practice
- Distributes topics across contests
- Tracks timing for submissions

Run with: uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .database import init_db
from .routers import users, contests, reflections
from .services.problem_service import get_problem_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("Starting MasterCP Contest System...")

    # Initialize database
    init_db()
    print("Database initialized")

    # Pre-load problems
    try:
        problem_service = get_problem_service()
        problem_service.load_problems()
        print(f"Loaded {len(problem_service._problems)} problems")
    except FileNotFoundError as e:
        print(f"Warning: Could not load problems: {e}")
        print("Run standardize_difficulty.py first to generate the problems file")

    yield

    # Shutdown
    print("Shutting down MasterCP Contest System...")


app = FastAPI(
    title="MasterCP Contest System",
    description="""
A competitive programming practice system that helps you improve through personalized contests.

## Features

- **Personalized Problem Selection**: Problems are selected at your current rating + 10
- **Topic Distribution**: Each contest covers different topics for balanced practice
- **Weak Topic Tracking**: Problems you fail are tracked, and you'll get easier versions until mastery
- **Rating System**: Your rating increases when you solve all problems in a contest
- **Time Tracking**: Track how long each problem takes to solve

## How It Works

1. **Create a user** to get started
2. **Start a contest** - you'll receive 5 problems (configurable)
3. **Solve problems** - submit your results as you go
4. **End the contest** - see your rating changes and topic analysis

## Rating Rules

- Solve ALL problems → Rating +10
- Miss ANY problem → Rating stays the same (no penalty)
- Weak topics get special treatment:
  - Problems start at lower difficulty
  - Progress through levels by solving consecutively
  - Topic removed from weak list when you can solve at your rating + 10
""",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(contests.router)
app.include_router(reflections.router)


@app.get("/", tags=["root"])
def read_root():
    """Root endpoint with API information."""
    return {
        "name": "MasterCP Contest System",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "users": "/users",
            "contests": "/contests",
        }
    }


@app.get("/health", tags=["health"])
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/stats", tags=["stats"])
def get_system_stats():
    """Get system statistics."""
    from .database import SessionLocal
    from .models import User, Contest, ContestStatus

    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        total_contests = db.query(Contest).count()
        active_contests = db.query(Contest).filter(
            Contest.status == ContestStatus.ACTIVE
        ).count()
        completed_contests = db.query(Contest).filter(
            Contest.status == ContestStatus.COMPLETED
        ).count()

        problem_service = get_problem_service()
        total_problems = len(problem_service._problems) if problem_service._loaded else 0

        return {
            "total_users": total_users,
            "total_contests": total_contests,
            "active_contests": active_contests,
            "completed_contests": completed_contests,
            "total_problems_available": total_problems,
        }
    finally:
        db.close()

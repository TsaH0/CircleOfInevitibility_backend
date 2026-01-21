"""
MasterCP Contest System - FastAPI Application

A competitive programming practice system that:
- Recommends problems at user's rating + 10
- Tracks weak topics and provides targeted practice
- Distributes topics across contests
- Tracks timing for submissions

Run with: uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import DATABASE_URL, get_database_type, init_db
from .routers import contests, reflections, users
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
        },
    }


@app.get("/health", tags=["health"])
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "database": get_database_type()}


@app.get("/database-info", tags=["health"])
def database_info():
    """Get information about the current database connection."""
    from sqlalchemy import text

    from .database import SessionLocal, engine

    db_type = get_database_type()
    is_postgresql = "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL

    # Test connection and get some info
    info = {
        "database_type": db_type,
        "is_postgresql": is_postgresql,
        "is_neon": is_postgresql and "neon" in DATABASE_URL,
        "connection_status": "unknown",
        "tables": [],
    }

    try:
        db = SessionLocal()
        # Test query
        db.execute(text("SELECT 1"))
        info["connection_status"] = "connected"

        # Get table names
        if is_postgresql:
            result = db.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
            info["tables"] = [row[0] for row in result.fetchall()]
        else:
            result = db.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            info["tables"] = [row[0] for row in result.fetchall()]

        db.close()
    except Exception as e:
        info["connection_status"] = f"error: {str(e)}"

    return info


@app.get("/stats", tags=["stats"])
def get_system_stats():
    """Get system statistics."""
    from .database import SessionLocal
    from .models import Contest, ContestStatus, User

    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        total_contests = db.query(Contest).count()
        active_contests = (
            db.query(Contest).filter(Contest.status == ContestStatus.ACTIVE).count()
        )
        completed_contests = (
            db.query(Contest).filter(Contest.status == ContestStatus.COMPLETED).count()
        )

        problem_service = get_problem_service()
        total_problems = (
            len(problem_service._problems) if problem_service._loaded else 0
        )

        return {
            "total_users": total_users,
            "total_contests": total_contests,
            "active_contests": active_contests,
            "completed_contests": completed_contests,
            "total_problems_available": total_problems,
        }
    finally:
        db.close()

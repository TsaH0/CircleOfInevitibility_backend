"""
API routes for Divine Rite of Reflection - AI-powered problem analysis.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..database import get_db
from ..models import Contest, ContestProblem, ProblemReflection, SubmissionStatus
from ..services.openrouter_service import generate_reflection

router = APIRouter(prefix="/reflections", tags=["reflections"])


# Pydantic schemas
class EditorialInput(BaseModel):
    """Input for editorial - either text or URL."""
    editorial_text: Optional[str] = None
    editorial_url: Optional[str] = None


class ReflectionResponse(BaseModel):
    """Response for a single problem reflection."""
    id: int
    contest_problem_id: int
    problem_name: str
    problem_url: str
    topic: str
    difficulty: int
    solved: bool
    time_taken_seconds: Optional[int]
    
    # Editorial provided by user
    editorial_text: Optional[str]
    editorial_url: Optional[str]
    
    # AI-generated reflection
    pivot_sentence: Optional[str]
    tips: Optional[str]
    what_to_improve: Optional[str]
    master_approach: Optional[str]
    
    # Metadata
    model_used: Optional[str]
    generated_at: Optional[datetime]
    generation_error: Optional[str]

    class Config:
        from_attributes = True


class ContestReflectionSummary(BaseModel):
    """Summary of reflections for a contest."""
    contest_id: int
    problems_count: int
    reflections_generated: int
    reflections_pending: int
    problems: List[dict]


@router.post("/{contest_id}/problem/{problem_id}/editorial")
async def submit_editorial(
    contest_id: int,
    problem_id: int,
    editorial: EditorialInput,
    db: Session = Depends(get_db)
):
    """
    Submit editorial for a problem (before generating reflection).
    """
    # Get the contest problem
    contest_problem = db.query(ContestProblem).filter(
        ContestProblem.id == problem_id,
        ContestProblem.contest_id == contest_id
    ).first()
    
    if not contest_problem:
        raise HTTPException(status_code=404, detail="Problem not found in this contest")
    
    # Check if reflection already exists
    reflection = db.query(ProblemReflection).filter(
        ProblemReflection.contest_problem_id == problem_id
    ).first()
    
    if reflection:
        # Update existing
        reflection.editorial_text = editorial.editorial_text
        reflection.editorial_url = editorial.editorial_url
    else:
        # Create new
        reflection = ProblemReflection(
            contest_problem_id=problem_id,
            editorial_text=editorial.editorial_text,
            editorial_url=editorial.editorial_url,
        )
        db.add(reflection)
    
    db.commit()
    db.refresh(reflection)
    
    return {
        "message": "Editorial saved successfully",
        "problem_id": problem_id,
        "has_editorial": bool(editorial.editorial_text or editorial.editorial_url)
    }


@router.post("/{contest_id}/problem/{problem_id}/generate")
async def generate_problem_reflection(
    contest_id: int,
    problem_id: int,
    db: Session = Depends(get_db)
):
    """
    Generate AI reflection for a single problem.
    Requires the contest to be completed or abandoned.
    """
    # Get the contest
    contest = db.query(Contest).filter(Contest.id == contest_id).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    
    # Get the contest problem
    contest_problem = db.query(ContestProblem).filter(
        ContestProblem.id == problem_id,
        ContestProblem.contest_id == contest_id
    ).first()
    
    if not contest_problem:
        raise HTTPException(status_code=404, detail="Problem not found in this contest")
    
    # Get or create reflection record
    reflection = db.query(ProblemReflection).filter(
        ProblemReflection.contest_problem_id == problem_id
    ).first()
    
    if not reflection:
        reflection = ProblemReflection(contest_problem_id=problem_id)
        db.add(reflection)
        db.commit()
        db.refresh(reflection)
    
    # Check if already generated
    if reflection.pivot_sentence and not reflection.generation_error:
        return {
            "message": "Reflection already generated",
            "reflection": _build_reflection_response(contest_problem, reflection)
        }
    
    # Generate reflection using OpenRouter
    result = await generate_reflection(
        problem_name=contest_problem.problem_name,
        problem_url=contest_problem.problem_url or "",
        topic=contest_problem.topic,
        difficulty=contest_problem.difficulty,
        solved=(contest_problem.status == SubmissionStatus.SOLVED),
        time_taken_seconds=contest_problem.time_taken_seconds,
        editorial_text=reflection.editorial_text,
        editorial_url=reflection.editorial_url,
        user_rating=contest.rating_at_start,
    )
    
    # Update reflection with results
    reflection.pivot_sentence = result.get("pivot_sentence")
    reflection.tips = result.get("tips")
    reflection.what_to_improve = result.get("what_to_improve")
    reflection.master_approach = result.get("master_approach")
    reflection.model_used = result.get("model_used")
    reflection.full_response = result.get("full_response")
    reflection.generation_error = result.get("error")
    reflection.generated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(reflection)
    
    return {
        "message": "Reflection generated successfully" if not result.get("error") else "Generation failed",
        "reflection": _build_reflection_response(contest_problem, reflection)
    }


@router.post("/{contest_id}/generate-all")
async def generate_all_reflections(
    contest_id: int,
    db: Session = Depends(get_db)
):
    """
    Generate reflections for all problems in a contest.
    """
    contest = db.query(Contest).filter(Contest.id == contest_id).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    
    results = []
    
    for problem in contest.problems:
        # Get or create reflection
        reflection = db.query(ProblemReflection).filter(
            ProblemReflection.contest_problem_id == problem.id
        ).first()
        
        if not reflection:
            reflection = ProblemReflection(contest_problem_id=problem.id)
            db.add(reflection)
            db.commit()
            db.refresh(reflection)
        
        # Skip if already generated successfully
        if reflection.pivot_sentence and not reflection.generation_error:
            results.append({
                "problem_id": problem.id,
                "status": "already_generated"
            })
            continue
        
        # Generate
        result = await generate_reflection(
            problem_name=problem.problem_name,
            problem_url=problem.problem_url or "",
            topic=problem.topic,
            difficulty=problem.difficulty,
            solved=(problem.status == SubmissionStatus.SOLVED),
            time_taken_seconds=problem.time_taken_seconds,
            editorial_text=reflection.editorial_text,
            editorial_url=reflection.editorial_url,
            user_rating=contest.rating_at_start,
        )
        
        # Update
        reflection.pivot_sentence = result.get("pivot_sentence")
        reflection.tips = result.get("tips")
        reflection.what_to_improve = result.get("what_to_improve")
        reflection.master_approach = result.get("master_approach")
        reflection.model_used = result.get("model_used")
        reflection.full_response = result.get("full_response")
        reflection.generation_error = result.get("error")
        reflection.generated_at = datetime.utcnow()
        
        db.commit()
        
        results.append({
            "problem_id": problem.id,
            "status": "generated" if not result.get("error") else "failed",
            "error": result.get("error")
        })
    
    return {
        "contest_id": contest_id,
        "results": results,
        "total_generated": sum(1 for r in results if r["status"] in ["generated", "already_generated"]),
        "total_failed": sum(1 for r in results if r["status"] == "failed")
    }


@router.get("/{contest_id}")
async def get_contest_reflections(
    contest_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all reflections for a contest.
    """
    contest = db.query(Contest).filter(Contest.id == contest_id).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    
    problems_data = []
    reflections_generated = 0
    reflections_pending = 0
    
    for problem in contest.problems:
        reflection = db.query(ProblemReflection).filter(
            ProblemReflection.contest_problem_id == problem.id
        ).first()
        
        problem_data = {
            "id": problem.id,
            "problem_id": problem.problem_id,
            "problem_name": problem.problem_name,
            "problem_url": problem.problem_url,
            "topic": problem.topic,
            "difficulty": problem.difficulty,
            "status": problem.status.value,
            "time_taken_seconds": problem.time_taken_seconds,
            "has_reflection": False,
            "reflection": None,
        }
        
        if reflection:
            if reflection.pivot_sentence:
                reflections_generated += 1
                problem_data["has_reflection"] = True
                problem_data["reflection"] = {
                    "id": reflection.id,
                    "editorial_text": reflection.editorial_text,
                    "editorial_url": reflection.editorial_url,
                    "pivot_sentence": reflection.pivot_sentence,
                    "tips": reflection.tips,
                    "what_to_improve": reflection.what_to_improve,
                    "master_approach": reflection.master_approach,
                    "model_used": reflection.model_used,
                    "generated_at": reflection.generated_at.isoformat() if reflection.generated_at else None,
                    "generation_error": reflection.generation_error,
                }
            else:
                reflections_pending += 1
                problem_data["reflection"] = {
                    "id": reflection.id,
                    "editorial_text": reflection.editorial_text,
                    "editorial_url": reflection.editorial_url,
                    "generation_error": reflection.generation_error,
                }
        else:
            reflections_pending += 1
        
        problems_data.append(problem_data)
    
    return {
        "contest_id": contest_id,
        "problems_count": len(contest.problems),
        "reflections_generated": reflections_generated,
        "reflections_pending": reflections_pending,
        "problems": problems_data
    }


@router.get("/{contest_id}/problem/{problem_id}")
async def get_problem_reflection(
    contest_id: int,
    problem_id: int,
    db: Session = Depends(get_db)
):
    """
    Get reflection for a specific problem.
    """
    contest_problem = db.query(ContestProblem).filter(
        ContestProblem.id == problem_id,
        ContestProblem.contest_id == contest_id
    ).first()
    
    if not contest_problem:
        raise HTTPException(status_code=404, detail="Problem not found in this contest")
    
    reflection = db.query(ProblemReflection).filter(
        ProblemReflection.contest_problem_id == problem_id
    ).first()
    
    return {
        "problem": {
            "id": contest_problem.id,
            "problem_id": contest_problem.problem_id,
            "problem_name": contest_problem.problem_name,
            "problem_url": contest_problem.problem_url,
            "topic": contest_problem.topic,
            "difficulty": contest_problem.difficulty,
            "status": contest_problem.status.value,
            "time_taken_seconds": contest_problem.time_taken_seconds,
        },
        "reflection": {
            "id": reflection.id if reflection else None,
            "editorial_text": reflection.editorial_text if reflection else None,
            "editorial_url": reflection.editorial_url if reflection else None,
            "pivot_sentence": reflection.pivot_sentence if reflection else None,
            "tips": reflection.tips if reflection else None,
            "what_to_improve": reflection.what_to_improve if reflection else None,
            "master_approach": reflection.master_approach if reflection else None,
            "model_used": reflection.model_used if reflection else None,
            "generated_at": reflection.generated_at.isoformat() if reflection and reflection.generated_at else None,
            "generation_error": reflection.generation_error if reflection else None,
        } if reflection else None
    }


def _build_reflection_response(problem: ContestProblem, reflection: ProblemReflection) -> dict:
    """Helper to build reflection response dict."""
    return {
        "id": reflection.id,
        "contest_problem_id": problem.id,
        "problem_name": problem.problem_name,
        "problem_url": problem.problem_url,
        "topic": problem.topic,
        "difficulty": problem.difficulty,
        "solved": problem.status == SubmissionStatus.SOLVED,
        "time_taken_seconds": problem.time_taken_seconds,
        "editorial_text": reflection.editorial_text,
        "editorial_url": reflection.editorial_url,
        "pivot_sentence": reflection.pivot_sentence,
        "tips": reflection.tips,
        "what_to_improve": reflection.what_to_improve,
        "master_approach": reflection.master_approach,
        "model_used": reflection.model_used,
        "generated_at": reflection.generated_at.isoformat() if reflection.generated_at else None,
        "generation_error": reflection.generation_error,
    }

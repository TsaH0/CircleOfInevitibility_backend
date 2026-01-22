"""
OpenRouter API service for AI-powered reflections.
Uses Groq API as primary and OpenRouter free models as fallback.
"""

import json
import os
from typing import List, Optional

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("API_KEY")

# API URLs
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Groq best model
GROQ_MODEL = "llama-3.3-70b-versatile"

# OpenRouter fallback models (free, max 3 allowed)
OPENROUTER_FALLBACK_MODELS: List[str] = [
    "liquid/lfm-2.5-1.2b-thinking:free",  # Free thinking model
    "google/gemma-3-1b-it:free",  # Free Gemma model
    "meta-llama/llama-3.2-3b-instruct:free",  # Free Llama model
]


def _build_prompt(
    problem_name: str,
    problem_url: str,
    topic: str,
    difficulty: int,
    solved: bool,
    partial: bool,
    time_taken_seconds: Optional[int],
    editorial_text: Optional[str],
    editorial_url: Optional[str],
    user_approach: Optional[str],
    user_rating: int,
) -> str:
    """Build the reflection prompt."""
    # Format time
    time_str = "Not recorded"
    if time_taken_seconds:
        mins = time_taken_seconds // 60
        secs = time_taken_seconds % 60
        time_str = f"{mins} minutes and {secs} seconds"

    # Build the prompt
    editorial_section = ""
    if editorial_text:
        editorial_section = f"\n\n## Editorial/Solution Provided:\n{editorial_text}"
    elif editorial_url:
        editorial_section = f"\n\n## Editorial URL: {editorial_url}\n(Please consider the typical solution approach for this type of problem)"

    # Build user approach section
    approach_section = ""
    if user_approach:
        approach_section = f"\n\n## User's Approach During Contest:\n{user_approach}"

    # Determine outcome
    if solved:
        outcome = "SOLVED"
    elif partial:
        outcome = "PARTIALLY SOLVED (had some ideas but couldn't fully solve)"
    else:
        outcome = "NOT SOLVED"

    prompt = f"""You are the Divine Oracle of "The Circle of Inevitability", the highest-level competitive programming wisdom system. Analyze this problem attempt and provide deep insight.

## Problem Information:
- **Name**: {problem_name}
- **URL**: {problem_url}
- **Topic/Pattern**: {topic.replace("_", " ").title()}
- **Difficulty Rating**: {difficulty}/100
- **User's Rating**: {user_rating}/100

## Attempt Result:
- **Outcome**: {outcome}
- **Time Taken**: {time_str}
{approach_section}
{editorial_section}

---

Provide a reflection in the following JSON format (respond ONLY with valid JSON, no markdown):

{{
    "pivot_sentence": "The single most important insight that unlocks this problem. This should be a concise, memorable statement that captures the key algorithmic or logical breakthrough needed.",

    "tips": "3-5 practical tips for tackling similar problems in the future. Focus on pattern recognition, common pitfalls to avoid, and time management strategies.",

    "what_to_improve": "Based on the outcome ({outcome.lower()}) and time taken{", and the user's approach" if user_approach else ""}, what specific areas should be improved? {"Analyze where the user's thinking went wrong or was incomplete, and explain the correct way to think about this problem. Be specific about what was missing from their approach." if user_approach else "Be constructive and specific."}",

    "master_approach": "Describe how a Sequence 0 Beyonder (The Fool - master of all algorithms) would approach this problem from the very first read. Include the thought process, the key observations they would make immediately, and the optimal strategy they would employ. {"Compare this to the user's approach and highlight the key differences in thinking." if user_approach else "Write this as if teaching an apprentice."}"
}}

Remember: Your response must be ONLY valid JSON, no additional text or markdown formatting."""

    return prompt


def _parse_response(content: str, model_used: str) -> dict:
    """Parse the AI response and return structured data."""
    # Clean up the response (remove markdown code blocks if present)
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        reflection_data = json.loads(content)

        # Helper function to convert lists to strings
        def to_string(value):
            if isinstance(value, list):
                return "\n• " + "\n• ".join(str(item) for item in value)
            return value

        return {
            "pivot_sentence": to_string(reflection_data.get("pivot_sentence")),
            "tips": to_string(reflection_data.get("tips")),
            "what_to_improve": to_string(reflection_data.get("what_to_improve")),
            "master_approach": to_string(reflection_data.get("master_approach")),
            "model_used": model_used,
            "full_response": json.dumps(reflection_data),
            "error": None,
        }
    except json.JSONDecodeError as e:
        return {
            "error": f"Failed to parse AI response: {str(e)}",
            "pivot_sentence": content[:500] if content else None,
            "tips": None,
            "what_to_improve": None,
            "master_approach": None,
            "model_used": model_used,
            "full_response": {"raw": content},
        }


async def _call_groq(prompt: str) -> dict:
    """Call Groq API as primary."""
    if not GROQ_API_KEY:
        return {"error": "Groq API key not configured", "content": None}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are the Divine Oracle of The Circle of Inevitability, providing wisdom to competitive programmers. Always respond with valid JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
            )

            if response.status_code != 200:
                return {
                    "error": f"Groq API error: {response.status_code} - {response.text}",
                    "content": None,
                }

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"error": None, "content": content, "model": f"groq/{GROQ_MODEL}"}

    except httpx.TimeoutException:
        return {"error": "Groq request timed out", "content": None}
    except Exception as e:
        return {"error": f"Groq error: {str(e)}", "content": None}


async def _call_openrouter_fallback(prompt: str) -> dict:
    """Call OpenRouter API as fallback with free models."""
    if not OPENROUTER_API_KEY:
        return {"error": "OpenRouter API key not configured", "content": None}

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://mastercp.local",
                    "X-Title": "MasterCP - The Circle of Inevitability",
                },
                json={
                    "models": OPENROUTER_FALLBACK_MODELS,
                    "route": "fallback",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are the Divine Oracle of The Circle of Inevitability, providing wisdom to competitive programmers. Always respond with valid JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
            )

            if response.status_code != 200:
                return {
                    "error": f"OpenRouter API error: {response.status_code} - {response.text}",
                    "content": None,
                }

            data = response.json()
            model_used = data.get("model", OPENROUTER_FALLBACK_MODELS[0])
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"error": None, "content": content, "model": model_used}

    except httpx.TimeoutException:
        return {"error": "OpenRouter request timed out", "content": None}
    except Exception as e:
        return {"error": f"OpenRouter error: {str(e)}", "content": None}


async def generate_reflection(
    problem_name: str,
    problem_url: str,
    topic: str,
    difficulty: int,
    solved: bool,
    partial: bool = False,
    time_taken_seconds: Optional[int] = None,
    editorial_text: Optional[str] = None,
    editorial_url: Optional[str] = None,
    user_approach: Optional[str] = None,
    user_rating: int = 20,
) -> dict:
    """
    Generate AI-powered reflection for a problem.
    Uses Groq as primary, falls back to OpenRouter free models.

    Returns:
        dict with keys: pivot_sentence, tips, what_to_improve, master_approach, model_used, error
    """
    # Check if at least one API key is configured
    if not GROQ_API_KEY and not OPENROUTER_API_KEY:
        return {
            "error": "No API keys configured. Please set GROQ_API_KEY or API_KEY (OpenRouter) in .env",
            "pivot_sentence": None,
            "tips": None,
            "what_to_improve": None,
            "master_approach": None,
            "model_used": None,
        }

    # Build the prompt
    prompt = _build_prompt(
        problem_name=problem_name,
        problem_url=problem_url,
        topic=topic,
        difficulty=difficulty,
        solved=solved,
        partial=partial,
        time_taken_seconds=time_taken_seconds,
        editorial_text=editorial_text,
        editorial_url=editorial_url,
        user_approach=user_approach,
        user_rating=user_rating,
    )

    # Try Groq first (primary)
    if GROQ_API_KEY:
        groq_result = await _call_groq(prompt)
        if groq_result.get("content"):
            return _parse_response(groq_result["content"], groq_result["model"])
        # Log Groq error but continue to fallback
        groq_error = groq_result.get("error", "Unknown Groq error")
    else:
        groq_error = "Groq API key not configured"

    # Fallback to OpenRouter free models
    if OPENROUTER_API_KEY:
        openrouter_result = await _call_openrouter_fallback(prompt)
        if openrouter_result.get("content"):
            return _parse_response(
                openrouter_result["content"], openrouter_result["model"]
            )
        openrouter_error = openrouter_result.get("error", "Unknown OpenRouter error")
    else:
        openrouter_error = "OpenRouter API key not configured"

    # Both failed
    return {
        "error": f"All providers failed. Groq: {groq_error}. OpenRouter: {openrouter_error}",
        "pivot_sentence": None,
        "tips": None,
        "what_to_improve": None,
        "master_approach": None,
        "model_used": None,
    }

"""
OpenRouter API service for AI-powered reflections.
Uses the best available model for generating problem reflections.
"""

import os
import httpx
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OPENROUTER_API_KEY = os.getenv("API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Best available models (in order of preference)
PREFERRED_MODELS = [
    "anthropic/claude-sonnet-4",  # Best for reasoning
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "google/gemini-2.0-flash-001",
]


async def get_available_model() -> str:
    """Get the best available model from OpenRouter."""
    # For now, use a reliable model
    return "anthropic/claude-sonnet-4"


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
    
    Returns:
        dict with keys: pivot_sentence, tips, what_to_improve, master_approach, model_used, error
    """
    if not OPENROUTER_API_KEY:
        return {
            "error": "OpenRouter API key not configured",
            "pivot_sentence": None,
            "tips": None,
            "what_to_improve": None,
            "master_approach": None,
            "model_used": None,
        }

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
- **Topic/Pattern**: {topic.replace('_', ' ').title()}
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

    try:
        model = await get_available_model()
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://mastercp.local",
                    "X-Title": "MasterCP - The Circle of Inevitability",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are the Divine Oracle of The Circle of Inevitability, providing wisdom to competitive programmers. Always respond with valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000,
                }
            )
            
            if response.status_code != 200:
                error_text = response.text
                return {
                    "error": f"OpenRouter API error: {response.status_code} - {error_text}",
                    "pivot_sentence": None,
                    "tips": None,
                    "what_to_improve": None,
                    "master_approach": None,
                    "model_used": model,
                }
            
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Parse the JSON response
            import json
            
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
                    "model_used": model,
                    "full_response": json.dumps(reflection_data),  # Serialize to JSON string
                    "error": None,
                }
            except json.JSONDecodeError as e:
                return {
                    "error": f"Failed to parse AI response: {str(e)}",
                    "pivot_sentence": content[:500] if content else None,  # Store raw response as fallback
                    "tips": None,
                    "what_to_improve": None,
                    "master_approach": None,
                    "model_used": model,
                    "full_response": {"raw": content},
                }
                
    except httpx.TimeoutException:
        return {
            "error": "Request timed out. Please try again.",
            "pivot_sentence": None,
            "tips": None,
            "what_to_improve": None,
            "master_approach": None,
            "model_used": None,
        }
    except Exception as e:
        return {
            "error": f"Unexpected error: {str(e)}",
            "pivot_sentence": None,
            "tips": None,
            "what_to_improve": None,
            "master_approach": None,
            "model_used": None,
        }

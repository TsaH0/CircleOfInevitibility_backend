"""
OpenRouter API service for AI-powered reflections.
Uses Gemini API as primary (with model discovery), Groq as backup, and OpenRouter free models as last fallback.
"""

import json
import os
import re
from typing import List, Optional

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SECOND_GEMINI_KEY = os.getenv("SECOND_GEMINI_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("API_KEY")

# API URLs
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Groq backup model
GROQ_MODEL = "llama-3.3-70b-versatile"

# Preferred Gemini models in order of preference (best first)
PREFERRED_GEMINI_MODELS = [
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro-preview-05-06",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-pro",
]

# OpenRouter fallback models (free, max 3 allowed)
OPENROUTER_FALLBACK_MODELS: List[str] = [
    "liquid/lfm-2.5-1.2b-thinking:free",  # Free thinking model
    "google/gemma-3-1b-it:free",  # Free Gemma model
    "meta-llama/llama-3.2-3b-instruct:free",  # Free Llama model
]

# Cache for available Gemini models (keyed by API key to support fallback)
_gemini_models_cache: dict = {}


async def _list_gemini_models(api_key: str) -> List[str]:
    """List available Gemini models and return them sorted by preference."""
    global _gemini_models_cache

    # Use cache if available for this key
    cache_key = api_key[:8] if api_key else ""  # Use first 8 chars as cache key
    if cache_key in _gemini_models_cache:
        return _gemini_models_cache[cache_key]

    if not api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GEMINI_BASE_URL}/models",
                params={"key": api_key},
            )

            if response.status_code != 200:
                print(
                    f"Failed to list Gemini models: {response.status_code} - {response.text}"
                )
                return []

            data = response.json()
            models = data.get("models", [])

            # Extract model names that support generateContent
            available_models = []
            for model in models:
                model_name = model.get("name", "").replace("models/", "")
                supported_methods = model.get("supportedGenerationMethods", [])
                if "generateContent" in supported_methods:
                    available_models.append(model_name)

            print(f"Available Gemini models: {available_models}")

            # Sort by preference
            sorted_models = []
            for preferred in PREFERRED_GEMINI_MODELS:
                if preferred in available_models:
                    sorted_models.append(preferred)

            # Add any other models not in our preference list
            for model in available_models:
                if model not in sorted_models:
                    sorted_models.append(model)

            _gemini_models_cache[cache_key] = sorted_models
            print(f"Sorted Gemini models by preference: {sorted_models}")
            return sorted_models

    except Exception as e:
        print(f"Error listing Gemini models: {e}")
        return []


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
    outcome = "SOLVED" if solved else ("PARTIAL" if partial else "UNSOLVED")

    prompt = f"""Analyze this competitive programming attempt using Pólya's heuristics.

**Problem**: {problem_name} | {topic.replace("_", " ").title()} | Difficulty: {difficulty}/100
**Result**: {outcome} | Time: {time_str} | User Rating: {user_rating}/100
{approach_section}{editorial_section}

**Pólya Heuristics to Consider**: Understanding, Edge Cases, Invariants/Monovariants, Reformulation, Working Backward, Simpler Related Problem, Symmetry, Constraints Analysis, Greedy/DP Structure, Key Insight, Future Heuristic.

Respond with ONLY valid JSON (no markdown). All strings on ONE LINE, use \\n for breaks, escape special chars.

{{
    "pivot_sentence": "Key Pólya insight that unlocks this problem - frame as reusable heuristic.",
    "tips": "3-5 tips referencing Pólya heuristics (e.g. 'Constraints: N≤10^5 suggests O(n log n)'). Show how editorial uses these. Use \\n between tips.",
    "what_to_improve": "Which heuristics were missed? {"How did user's approach diverge from editorial?" if user_approach else "What to practice recognizing?"} Use \\n for breaks.",
    "master_approach": "Expert approach via Pólya: (1) Restate problem (2) Which heuristics & why (3) Key steps (4) Patterns to remember. {"Compare to user's approach." if user_approach else ""} Use \\n for breaks."
}}"""

    return prompt


def _to_markdown(value) -> str:
    """Convert a value to markdown string."""
    if value is None:
        return ""
    if isinstance(value, list):
        # Convert list to markdown bullet points
        return "\n".join(f"- {str(item)}" for item in value)
    return str(value)


def _build_full_response_markdown(reflection_data: dict) -> str:
    """Build a full markdown response from reflection data."""
    sections = []

    if reflection_data.get("pivot_sentence"):
        sections.append(
            f"## 🎯 Pivot Sentence\n\n{_to_markdown(reflection_data['pivot_sentence'])}"
        )

    if reflection_data.get("tips"):
        sections.append(f"## 💡 Tips\n\n{_to_markdown(reflection_data['tips'])}")

    if reflection_data.get("what_to_improve"):
        sections.append(
            f"## 📈 What to Improve\n\n{_to_markdown(reflection_data['what_to_improve'])}"
        )

    if reflection_data.get("master_approach"):
        sections.append(
            f"## 🧙 Master Approach\n\n{_to_markdown(reflection_data['master_approach'])}"
        )

    return "\n\n---\n\n".join(sections)


def _sanitize_json_string(content: str) -> str:
    """
    Sanitize a JSON string by escaping unescaped control characters.
    This handles cases where the AI returns JSON with literal newlines/tabs inside string values.
    """
    # First, let's try to fix control characters inside JSON string values
    # This regex finds strings and escapes control characters within them

    def escape_control_chars_in_string(match):
        """Escape control characters inside a matched JSON string."""
        s = match.group(0)
        # The string includes the quotes, so we process the content between them
        if len(s) < 2:
            return s
        quote = s[0]
        inner = s[1:-1]
        # Replace unescaped control characters
        inner = inner.replace("\n", "\\n")
        inner = inner.replace("\r", "\\r")
        inner = inner.replace("\t", "\\t")
        # Handle other control characters (ASCII 0-31 except those already handled)
        inner = re.sub(
            r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
            lambda m: f"\\u{ord(m.group(0)):04x}",
            inner,
        )
        return quote + inner + quote

    # Match JSON strings (handling escaped quotes within)
    # This pattern matches strings that start with " and end with unescaped "
    json_string_pattern = r'"(?:[^"\\]|\\.)*"'

    try:
        sanitized = re.sub(
            json_string_pattern,
            escape_control_chars_in_string,
            content,
            flags=re.DOTALL,
        )
        return sanitized
    except Exception:
        # If regex fails, do a simple replacement
        return content


def _parse_response(content: str, model_used: str) -> dict:
    """Parse the AI response and return structured data in Markdown format."""
    # Clean up the response (remove markdown code blocks if present)
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    # Sanitize JSON to handle control characters
    sanitized_content = _sanitize_json_string(content)

    try:
        reflection_data = json.loads(sanitized_content)

        # Convert each field to markdown
        pivot_sentence = _to_markdown(reflection_data.get("pivot_sentence"))
        tips = _to_markdown(reflection_data.get("tips"))
        what_to_improve = _to_markdown(reflection_data.get("what_to_improve"))
        master_approach = _to_markdown(reflection_data.get("master_approach"))

        # Build full response as markdown
        full_response_md = _build_full_response_markdown(reflection_data)

        return {
            "pivot_sentence": pivot_sentence,
            "tips": tips,
            "what_to_improve": what_to_improve,
            "master_approach": master_approach,
            "model_used": model_used,
            "full_response": full_response_md,
            "error": None,
        }
    except json.JSONDecodeError as e:
        # Try a more aggressive cleanup approach
        try:
            # Remove all control characters and try again
            aggressive_clean = re.sub(r"[\x00-\x1f\x7f]", " ", content)
            aggressive_clean = _sanitize_json_string(aggressive_clean)
            reflection_data = json.loads(aggressive_clean)

            # If we get here, parsing succeeded with aggressive cleanup
            pivot_sentence = _to_markdown(reflection_data.get("pivot_sentence"))
            tips = _to_markdown(reflection_data.get("tips"))
            what_to_improve = _to_markdown(reflection_data.get("what_to_improve"))
            master_approach = _to_markdown(reflection_data.get("master_approach"))
            full_response_md = _build_full_response_markdown(reflection_data)

            return {
                "pivot_sentence": pivot_sentence,
                "tips": tips,
                "what_to_improve": what_to_improve,
                "master_approach": master_approach,
                "model_used": model_used,
                "full_response": full_response_md,
                "error": None,
            }
        except json.JSONDecodeError:
            pass  # Fall through to raw content handling

        # If JSON parsing still fails, treat the raw content as markdown
        # Try to extract useful content from the raw response
        raw_content = content if content else "No response received."

        # Try to extract structured content even from malformed JSON
        extracted_sections = _extract_sections_from_raw(raw_content)

        if extracted_sections:
            # Build markdown from extracted sections
            full_response_md = "## 📝 AI Reflection (Extracted)\n\n*Note: Response was partially parsed.*\n\n"
            for section_name, section_content in extracted_sections.items():
                full_response_md += f"### {section_name.replace('_', ' ').title()}\n\n{section_content}\n\n"

            return {
                "error": None,  # Don't show error if we extracted content
                "pivot_sentence": extracted_sections.get("pivot_sentence"),
                "tips": extracted_sections.get("tips"),
                "what_to_improve": extracted_sections.get("what_to_improve"),
                "master_approach": extracted_sections.get("master_approach"),
                "model_used": model_used,
                "full_response": full_response_md,
            }

        # Build a markdown response from raw content
        full_response_md = f"## ⚠️ Raw AI Response\n\n*Note: The AI response could not be parsed as structured data.*\n\n{raw_content}"

        return {
            "error": f"Failed to parse AI response: {str(e)}",
            "pivot_sentence": raw_content[:500] if raw_content else None,
            "tips": None,
            "what_to_improve": None,
            "master_approach": None,
            "model_used": model_used,
            "full_response": full_response_md,
        }


def _extract_sections_from_raw(content: str) -> dict:
    """
    Try to extract sections from malformed JSON by looking for key patterns.
    Returns a dict with extracted sections, or empty dict if extraction fails.
    """
    sections = {}

    # Patterns to look for (key followed by colon and quoted content)
    keys = ["pivot_sentence", "tips", "what_to_improve", "master_approach"]

    for key in keys:
        # Try to find the key and extract content after it
        # Pattern: "key": "content" or "key": [ or "key": {
        pattern = rf'"{key}"\s*:\s*"([^"]*(?:\\.[^"]*)*)"'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            value = match.group(1)
            # Unescape common escapes
            value = value.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
            sections[key] = value.strip()
        else:
            # Try to find array or longer content
            # Look for key and capture everything until the next key or end
            start_pattern = rf'"{key}"\s*:\s*'
            start_match = re.search(start_pattern, content, re.IGNORECASE)
            if start_match:
                start_idx = start_match.end()
                # Find the end (next key or closing brace)
                remaining = content[start_idx:]
                # Try to find a reasonable end point
                end_patterns = [
                    r',\s*"(?:pivot_sentence|tips|what_to_improve|master_approach)"',
                    r"\}\s*$",
                ]
                end_idx = len(remaining)
                for ep in end_patterns:
                    end_match = re.search(ep, remaining)
                    if end_match and end_match.start() < end_idx:
                        end_idx = end_match.start()

                extracted = remaining[:end_idx].strip()
                # Clean up the extracted content
                extracted = extracted.strip('"').strip(",").strip()
                if extracted:
                    extracted = (
                        extracted.replace("\\n", "\n")
                        .replace("\\t", "\t")
                        .replace('\\"', '"')
                    )
                    sections[key] = extracted

    return sections


async def _call_gemini(prompt: str, model: str, api_key: str) -> dict:
    """Call Gemini API with a specific model and API key."""
    if not api_key:
        return {"error": "Gemini API key not configured", "content": None}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{GEMINI_BASE_URL}/models/{model}:generateContent",
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 2000,
                    },
                    "systemInstruction": {
                        "parts": [
                            {
                                "text": "You are the Divine Oracle of The Circle of Inevitability, providing wisdom to competitive programmers. Always respond with valid JSON only."
                            }
                        ]
                    },
                },
            )

            if response.status_code != 200:
                error_text = response.text
                return {
                    "error": f"Gemini API error ({model}): {response.status_code} - {error_text}",
                    "content": None,
                }

            data = response.json()

            # Check for blocked content or errors
            if "error" in data:
                return {
                    "error": f"Gemini error ({model}): {data['error'].get('message', 'Unknown error')}",
                    "content": None,
                }

            candidates = data.get("candidates", [])
            if not candidates:
                return {
                    "error": f"Gemini ({model}): No candidates in response",
                    "content": None,
                }

            content = (
                candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            )
            if not content:
                return {
                    "error": f"Gemini ({model}): Empty response content",
                    "content": None,
                }

            return {"error": None, "content": content, "model": f"gemini/{model}"}

    except httpx.TimeoutException:
        return {"error": f"Gemini ({model}) request timed out", "content": None}
    except Exception as e:
        return {"error": f"Gemini ({model}) error: {str(e)}", "content": None}


async def _call_gemini_with_fallback(prompt: str) -> dict:
    """Try multiple Gemini models in order of preference, with fallback to SECOND_GEMINI_KEY."""
    # Build list of API keys to try
    api_keys_to_try = []
    if GEMINI_API_KEY:
        api_keys_to_try.append(("PRIMARY", GEMINI_API_KEY))
    if SECOND_GEMINI_KEY:
        api_keys_to_try.append(("SECONDARY", SECOND_GEMINI_KEY))

    if not api_keys_to_try:
        return {"error": "No Gemini API keys configured", "content": None}

    all_errors = []

    for key_name, api_key in api_keys_to_try:
        print(f"Trying Gemini with {key_name} API key...")

        # Get available models for this key
        available_models = await _list_gemini_models(api_key)

        if not available_models:
            all_errors.append(f"{key_name}: No models available")
            print(f"{key_name} Gemini key: No models available")
            continue

        for model in available_models:
            print(f"Trying Gemini model: {model} ({key_name} key)")
            result = await _call_gemini(prompt, model, api_key)

            if result.get("content"):
                print(f"Successfully used Gemini model: {model} ({key_name} key)")
                return result

            error = result.get("error", "Unknown error")
            all_errors.append(f"{key_name}/{model}: {error}")
            print(f"Gemini model {model} ({key_name} key) failed: {error}")

    return {
        "error": f"All Gemini keys/models failed: {'; '.join(all_errors[:5])}...",
        "content": None,
    }


async def _call_groq(prompt: str) -> dict:
    """Call Groq API as backup."""
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
    """Call OpenRouter API as last fallback with free models."""
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
    Uses Gemini as primary (with model discovery), Groq as backup, falls back to OpenRouter free models.

    Returns:
        dict with keys: pivot_sentence, tips, what_to_improve, master_approach, model_used, error
    """
    # Check if at least one API key is configured
    if not GEMINI_API_KEY and not GROQ_API_KEY and not OPENROUTER_API_KEY:
        return {
            "error": "No API keys configured. Please set GEMINI_API_KEY, GROQ_API_KEY, or API_KEY (OpenRouter) in .env",
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

    # Try Gemini first (primary)
    if GEMINI_API_KEY:
        print("Attempting Gemini API (primary)...")
        gemini_result = await _call_gemini_with_fallback(prompt)
        if gemini_result.get("content"):
            return _parse_response(gemini_result["content"], gemini_result["model"])
        gemini_error = gemini_result.get("error", "Unknown Gemini error")
        print(f"Gemini failed: {gemini_error}")
    else:
        gemini_error = "Gemini API key not configured"

    # Try Groq as backup
    if GROQ_API_KEY:
        print("Attempting Groq API (backup)...")
        groq_result = await _call_groq(prompt)
        if groq_result.get("content"):
            return _parse_response(groq_result["content"], groq_result["model"])
        groq_error = groq_result.get("error", "Unknown Groq error")
        print(f"Groq failed: {groq_error}")
    else:
        groq_error = "Groq API key not configured"

    # Fallback to OpenRouter free models
    if OPENROUTER_API_KEY:
        print("Attempting OpenRouter API (last fallback)...")
        openrouter_result = await _call_openrouter_fallback(prompt)
        if openrouter_result.get("content"):
            return _parse_response(
                openrouter_result["content"], openrouter_result["model"]
            )
        openrouter_error = openrouter_result.get("error", "Unknown OpenRouter error")
    else:
        openrouter_error = "OpenRouter API key not configured"

    # All failed
    return {
        "error": f"All providers failed. Gemini: {gemini_error}. Groq: {groq_error}. OpenRouter: {openrouter_error}",
        "pivot_sentence": None,
        "tips": None,
        "what_to_improve": None,
        "master_approach": None,
        "model_used": None,
    }

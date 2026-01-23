"""
Test script for the reflection service.
Tests Gemini as primary, Groq as backup, and OpenRouter as last fallback.
"""

import asyncio
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check API keys
gemini_key = os.getenv("GEMINI_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")
openrouter_key = os.getenv("API_KEY")

print("=" * 60)
print("API Key Status:")
print(f"  GEMINI_API_KEY: {'✓ Set' if gemini_key else '✗ Not set'} (Primary)")
print(f"  GROQ_API_KEY: {'✓ Set' if groq_key else '✗ Not set'} (Backup)")
print(
    f"  API_KEY (OpenRouter): {'✓ Set' if openrouter_key else '✗ Not set'} (Last Fallback)"
)
print("=" * 60)


async def test_reflection():
    """Test the reflection service with a mock problem."""
    from app.services.openrouter_service import generate_reflection

    # Mock problem data
    mock_problem = {
        "problem_name": "Two Sum",
        "problem_url": "https://leetcode.com/problems/two-sum/",
        "topic": "hash_map",
        "difficulty": 25,
        "solved": False,
        "partial": True,
        "time_taken_seconds": 1200,  # 20 minutes
        "editorial_text": "Use a hash map to store seen numbers. For each number, check if target - num exists in the map.",
        "editorial_url": None,
        "user_approach": "I tried using two nested loops to check all pairs, but it was too slow for large inputs. I knew there had to be a better way but couldn't think of using a hash map.",
        "user_rating": 30,
    }

    print("\n" + "=" * 60)
    print("Testing Reflection Generation")
    print("=" * 60)
    print(f"\nProblem: {mock_problem['problem_name']}")
    print(f"Topic: {mock_problem['topic']}")
    print(f"Difficulty: {mock_problem['difficulty']}/100")
    print(f"Solved: {mock_problem['solved']}")
    print(f"Partial: {mock_problem['partial']}")
    print(f"Time: {mock_problem['time_taken_seconds'] // 60} minutes")
    print("\nGenerating reflection...")
    print("-" * 60)

    result = await generate_reflection(
        problem_name=mock_problem["problem_name"],
        problem_url=mock_problem["problem_url"],
        topic=mock_problem["topic"],
        difficulty=mock_problem["difficulty"],
        solved=mock_problem["solved"],
        partial=mock_problem["partial"],
        time_taken_seconds=mock_problem["time_taken_seconds"],
        editorial_text=mock_problem["editorial_text"],
        editorial_url=mock_problem["editorial_url"],
        user_approach=mock_problem["user_approach"],
        user_rating=mock_problem["user_rating"],
    )

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)

    if result.get("error"):
        print(f"\n❌ ERROR: {result['error']}")
    else:
        print(f"\n✓ Model Used: {result.get('model_used', 'Unknown')}")

        print("\n📌 PIVOT SENTENCE:")
        print("-" * 40)
        print(result.get("pivot_sentence", "N/A"))

        print("\n💡 TIPS:")
        print("-" * 40)
        print(result.get("tips", "N/A"))

        print("\n📈 WHAT TO IMPROVE:")
        print("-" * 40)
        print(result.get("what_to_improve", "N/A"))

        print("\n🎯 MASTER APPROACH:")
        print("-" * 40)
        print(result.get("master_approach", "N/A"))

    print("\n" + "=" * 60)
    return result


if __name__ == "__main__":
    if not gemini_key and not groq_key and not openrouter_key:
        print("\n❌ No API keys configured!")
        print("Please set GEMINI_API_KEY, GROQ_API_KEY, or API_KEY in your .env file")
        exit(1)

    result = asyncio.run(test_reflection())

    # Exit with error code if failed
    if result.get("error"):
        exit(1)
    print("\n✅ Test completed successfully!")

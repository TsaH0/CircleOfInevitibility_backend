#!/usr/bin/env python3
"""
Database Connection Test Script

Tests the connection to the configured database (Neon PostgreSQL or SQLite)
and verifies that all tables are properly created.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_connection():
    """Test database connection and display info."""
    print("\n" + "=" * 60)
    print("DATABASE CONNECTION TEST")
    print("=" * 60)

    # Check DATABASE_URL
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("❌ DATABASE_URL is not set!")
        print("   Using default SQLite database.")
        db_url = "sqlite:///./mastercp.db"

    # Determine database type
    is_postgresql = "postgresql" in db_url or "postgres" in db_url
    is_neon = is_postgresql and "neon" in db_url

    # Mask password for display
    if "@" in db_url:
        parts = db_url.split("@")
        user_part = parts[0].split("://")[1].split(":")[0]
        safe_url = db_url.split("://")[0] + "://" + user_part + ":****@" + parts[1]
    else:
        safe_url = db_url

    print(f"\n📋 Configuration:")
    print(f"   Database URL: {safe_url[:70]}...")
    print(f"   Type: {'PostgreSQL' if is_postgresql else 'SQLite'}")
    print(f"   Is Neon: {'Yes' if is_neon else 'No'}")

    # Import database module
    print("\n📋 Testing connection...")
    try:
        from sqlalchemy import inspect, text

        from app.database import SessionLocal, engine, get_database_type, init_db

        print(f"   Database type (from app): {get_database_type()}")

        # Test basic connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        print("   ✅ Basic connection: SUCCESS")

        # Initialize tables
        print("\n📋 Initializing/verifying tables...")
        init_db()

        # Get table info
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"   ✅ Found {len(tables)} tables:")
        for table in sorted(tables):
            print(f"      - {table}")

        # Test session
        print("\n📋 Testing session operations...")
        db = SessionLocal()
        try:
            # Try a simple query
            if is_postgresql:
                result = db.execute(text("SELECT current_database(), current_user"))
                row = result.fetchone()
                print(f"   Database: {row[0]}")
                print(f"   User: {row[1]}")
            else:
                result = db.execute(text("SELECT sqlite_version()"))
                row = result.fetchone()
                print(f"   SQLite version: {row[0]}")

            # Count rows in each table
            print("\n📋 Table row counts:")
            for table in sorted(tables):
                try:
                    result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"      - {table}: {count} rows")
                except Exception as e:
                    print(f"      - {table}: Error counting ({e})")

            print("   ✅ Session operations: SUCCESS")
        finally:
            db.close()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print(f"\nYour backend is configured to use: {get_database_type()}")
        print("\nYou can now start the server with:")
        print("   uvicorn app.main:app --reload")
        print()
        return 0

    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        print("\n" + "=" * 60)
        print("❌ TESTS FAILED")
        print("=" * 60)

        if is_neon:
            print("\nTroubleshooting for Neon:")
            print("1. Check your internet connection")
            print("2. Verify the DATABASE_URL in your .env file")
            print("3. Make sure the Neon project is active")
            print("4. Check if the hostname is correct (no typos)")
            print("\nExpected format:")
            print(
                "   DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require"
            )

        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(test_connection())

#!/usr/bin/env python3
"""
Database Migration Script

Migrates data from SQLite to PostgreSQL (Neon) or initializes fresh Neon database.
Supports full data migration from existing SQLite database.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


def check_neon_url():
    """Check if DATABASE_URL is set and points to PostgreSQL."""
    db_url = os.getenv("DATABASE_URL", "")

    if not db_url:
        print("❌ DATABASE_URL is not set in .env file")
        print("\nPlease add your Neon connection string to .env:")
        print("DATABASE_URL=postgresql://user:password@host/database?sslmode=require")
        return None

    if "postgresql" not in db_url and "postgres" not in db_url:
        print("❌ DATABASE_URL does not appear to be a PostgreSQL connection string")
        print(f"Current value: {db_url[:50]}...")
        return None

    return db_url


def get_sqlite_engine():
    """Create SQLite engine for reading existing data."""
    from sqlalchemy import create_engine

    sqlite_path = Path(__file__).parent / "mastercp.db"
    if not sqlite_path.exists():
        return None

    return create_engine(
        f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False}
    )


def check_database_connection(engine, name="Database"):
    """Check if database connection works."""
    from sqlalchemy import inspect, text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        return True, tables
    except Exception as e:
        print(f"❌ {name} connection failed: {e}")
        return False, []


def get_table_row_counts(engine, tables):
    """Get row counts for each table."""
    from sqlalchemy import text

    counts = {}
    with engine.connect() as conn:
        for table in tables:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                counts[table] = result.scalar()
            except Exception:
                counts[table] = 0
    return counts


def migrate_data(sqlite_engine, pg_engine):
    """Migrate data from SQLite to PostgreSQL."""
    from sqlalchemy import MetaData, inspect, text

    print("\n" + "=" * 60)
    print("MIGRATING DATA FROM SQLITE TO POSTGRESQL")
    print("=" * 60)

    # Tables in order of dependencies (parents first)
    table_order = [
        "users",
        "user_topic_ratings",
        "weak_topics",
        "contests",
        "contest_problems",
        "problem_history",
        "problem_reflections",
    ]

    # Reflect SQLite tables
    sqlite_meta = MetaData()
    sqlite_meta.reflect(bind=sqlite_engine)

    # Get existing tables in SQLite
    sqlite_inspector = inspect(sqlite_engine)
    existing_tables = sqlite_inspector.get_table_names()

    total_rows_migrated = 0

    for table_name in table_order:
        if table_name not in existing_tables:
            print(f"⏭️  Skipping {table_name} (not in SQLite)")
            continue

        if table_name not in sqlite_meta.tables:
            print(f"⏭️  Skipping {table_name} (could not reflect)")
            continue

        table = sqlite_meta.tables[table_name]

        # Read data from SQLite
        with sqlite_engine.connect() as sqlite_conn:
            result = sqlite_conn.execute(table.select())
            rows = result.fetchall()
            columns = result.keys()

        if not rows:
            print(f"⏭️  Skipping {table_name} (no data)")
            continue

        print(f"\n📦 Migrating {table_name}: {len(rows)} rows...")

        # Insert into PostgreSQL
        with pg_engine.connect() as pg_conn:
            # Clear existing data in PostgreSQL table
            pg_conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
            pg_conn.commit()

            # Insert rows
            for row in rows:
                row_dict = dict(zip(columns, row))

                # Build INSERT statement
                cols = ", ".join(row_dict.keys())
                placeholders = ", ".join([f":{k}" for k in row_dict.keys()])
                insert_sql = text(
                    f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
                )

                try:
                    pg_conn.execute(insert_sql, row_dict)
                except Exception as e:
                    print(f"  ⚠️  Error inserting row: {e}")
                    continue

            pg_conn.commit()

            # Reset sequence for tables with auto-increment
            if "id" in columns:
                try:
                    pg_conn.execute(
                        text(
                            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                            f"COALESCE((SELECT MAX(id) FROM {table_name}), 1))"
                        )
                    )
                    pg_conn.commit()
                except Exception:
                    pass  # Some tables might not have sequences

        print(f"  ✅ Migrated {len(rows)} rows to {table_name}")
        total_rows_migrated += len(rows)

    print(f"\n✅ Total rows migrated: {total_rows_migrated}")
    return total_rows_migrated


def initialize_neon_database():
    """Initialize Neon database tables."""
    print("\n" + "=" * 60)
    print("INITIALIZING NEON DATABASE")
    print("=" * 60)

    # Import after setting up path
    from sqlalchemy import inspect

    from app.database import engine, init_db

    try:
        init_db()
        print("✅ Database tables created successfully!")

        # Show created tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"\nCreated tables ({len(tables)}):")
        for table in sorted(tables):
            print(f"  - {table}")

        return True, engine
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        import traceback

        traceback.print_exc()
        return False, None


def main():
    """Main migration flow."""
    print("\n🔄 MasterCP Database Migration Tool")
    print("=" * 60)

    # Step 1: Check Neon URL
    print("\n📋 Step 1: Checking DATABASE_URL configuration...")
    neon_url = check_neon_url()
    if not neon_url:
        return 1

    # Mask password in output
    if "@" in neon_url:
        parts = neon_url.split("@")
        user_part = parts[0].split("://")[1].split(":")[0]
        safe_url = neon_url.split("://")[0] + "://" + user_part + ":****@" + parts[1]
    else:
        safe_url = neon_url

    print(f"✅ Found PostgreSQL URL: {safe_url[:60]}...")

    # Step 2: Check for existing SQLite database
    print("\n📋 Step 2: Checking for existing SQLite database...")
    sqlite_engine = get_sqlite_engine()
    has_sqlite_data = False
    sqlite_tables = []
    sqlite_counts = {}

    if sqlite_engine:
        success, sqlite_tables = check_database_connection(sqlite_engine, "SQLite")
        if success and sqlite_tables:
            sqlite_counts = get_table_row_counts(sqlite_engine, sqlite_tables)
            total_rows = sum(sqlite_counts.values())
            if total_rows > 0:
                has_sqlite_data = True
                print(f"✅ Found SQLite database with {total_rows} total rows:")
                for table, count in sqlite_counts.items():
                    if count > 0:
                        print(f"   - {table}: {count} rows")
            else:
                print("ℹ️  SQLite database exists but has no data")
        else:
            print("ℹ️  SQLite database exists but has no tables")
    else:
        print("ℹ️  No existing SQLite database found")

    # Step 3: Initialize Neon database
    print("\n📋 Step 3: Initializing Neon database tables...")
    success, pg_engine = initialize_neon_database()
    if not success:
        return 1

    # Step 4: Check Neon connection and existing data
    print("\n📋 Step 4: Checking Neon database status...")
    success, pg_tables = check_database_connection(pg_engine, "Neon PostgreSQL")
    if not success:
        return 1

    pg_counts = get_table_row_counts(pg_engine, pg_tables)
    pg_total = sum(pg_counts.values())

    if pg_total > 0:
        print(f"⚠️  Neon database already has {pg_total} rows of data:")
        for table, count in pg_counts.items():
            if count > 0:
                print(f"   - {table}: {count} rows")

    # Step 5: Offer migration if SQLite has data
    if has_sqlite_data:
        print("\n📋 Step 5: Data migration options...")
        print(f"\nFound data in SQLite that can be migrated to Neon.")

        if pg_total > 0:
            print("⚠️  WARNING: Neon database already has data!")
            print("   Migrating will REPLACE all existing data in Neon.")

        response = input("\nMigrate data from SQLite to Neon? [y/N]: ").strip().lower()

        if response == "y":
            try:
                migrate_data(sqlite_engine, pg_engine)
            except Exception as e:
                print(f"\n❌ Migration failed: {e}")
                import traceback

                traceback.print_exc()
                return 1
        else:
            print("\nSkipping data migration. Fresh database initialized.")
    else:
        print("\n📋 Step 5: No data to migrate - fresh database ready!")

    # Final summary
    print("\n" + "=" * 60)
    print("✅ MIGRATION COMPLETE!")
    print("=" * 60)

    # Show final state
    success, final_tables = check_database_connection(pg_engine, "Neon")
    if success:
        final_counts = get_table_row_counts(pg_engine, final_tables)
        final_total = sum(final_counts.values())
        print(f"\nNeon database now has {final_total} total rows:")
        for table, count in sorted(final_counts.items()):
            print(f"   - {table}: {count} rows")

    print("\n🚀 Your MasterCP backend is now using Neon PostgreSQL!")
    print("\nYou can start the server with:")
    print("  cd backend && uvicorn app.main:app --reload")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

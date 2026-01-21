# Switching to Neon PostgreSQL Database

This guide helps you migrate from SQLite to Neon PostgreSQL.

## Step 1: Add DATABASE_URL to .env

Open your `.env` file and add your Neon connection string:

```bash
# .env file
API_KEY=your_openrouter_key_here

# Add this line with your Neon database URL:
DATABASE_URL=postgresql://user:password@ep-xxx-xxx.us-east-2.aws.neon.tech/mastercp?sslmode=require

# Your Codeforces cookies (if any)
CODEFORCES_COOKIES="your_cookies_here"
```

**Format**: `postgresql://[user]:[password]@[host]/[database]?sslmode=require`

You can get this from Neon dashboard → Connection Details → Connection String

## Step 2: Install PostgreSQL Driver

```bash
cd backend
pip install psycopg2-binary
```

## Step 3: Run Migration Script

```bash
python migrate_to_neon.py
```

This will:
- ✅ Test database connection
- ✅ Create all tables (users, contests, problems, reflections, etc.)
- ✅ Verify setup

## Step 4: Start Your Server

```bash
uvicorn app.main:app --reload
```

## Verification

Test that it's working:
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

## What Changes?

### Before (SQLite):
- Database file: `mastercp.db` (local file)
- Connection: File-based
- Good for: Development only

### After (Neon PostgreSQL):
- Database: Cloud-hosted on Neon
- Connection: Network-based (SSL encrypted)
- Good for: Production deployment
- Benefits:
  - ✅ No data loss when redeploying
  - ✅ Can scale vertically
  - ✅ Automatic backups
  - ✅ Access from anywhere
  - ✅ Free tier (512MB)

## Troubleshooting

### "Connection refused" or "could not connect"
- Check your DATABASE_URL is correct
- Verify Neon database is running (check Neon dashboard)
- Make sure `?sslmode=require` is at the end

### "relation does not exist"
- Run `python migrate_to_neon.py` to create tables

### "password authentication failed"
- Double-check username and password in DATABASE_URL
- Regenerate password in Neon if needed

## Rollback to SQLite

If you need to go back to SQLite temporarily:

1. Comment out DATABASE_URL in .env:
   ```bash
   # DATABASE_URL=postgresql://...
   ```

2. Restart server - it will use SQLite by default

## Next Steps

After migration:
1. Test all API endpoints
2. Create a test user and contest
3. Verify reflections work
4. Deploy your backend to a platform (Railway, Render, fly.io)

## Important Notes

- 🔒 **Never commit `.env` file** - it's in .gitignore
- 📊 **Free tier limits**: 512MB storage, 3GB bandwidth/month
- 🔄 **Database branching**: Neon has Git-like branching for dev/staging
- 💾 **Backups**: Neon automatically backs up your data

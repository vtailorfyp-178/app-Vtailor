#!/usr/bin/env python3
"""Create an admin user in MongoDB (run once before first admin login).

Usage (from backend/app-Vtailor):
  python scripts/create_admin.py admin@example.com
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db.mongodb import connect_to_mongo, close_mongo_connection, get_database


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_admin.py <email>")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    if "@" not in email:
        print("Invalid email")
        sys.exit(1)

    await connect_to_mongo()
    db = get_database()

    existing = await db.users.find_one({"email": email, "role": "admin"})
    if existing:
        print(f"Admin already exists: {email} (id={existing['_id']})")
        await close_mongo_connection()
        return

    doc = {
        "email": email,
        "role": "admin",
        "name": "Platform Admin",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.users.insert_one(doc)
    print(f"Admin created: {email}")
    print(f"User id: {result.inserted_id}")
    print("Login at http://localhost:8000/admin with OTP (role=admin).")
    await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(main())

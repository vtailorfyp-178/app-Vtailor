# vTailor Admin Dashboard

Simple web panel served by the FastAPI backend.

## Setup (one time)

1. Start MongoDB and the API (`.\start-api.ps1` or `docker-compose up`).
2. Create an admin account:

```bash
cd backend/app-Vtailor
python scripts/create_admin.py your-email@example.com
```

3. Open **http://localhost:8000/admin** (or `https://app-vtailor.onrender.com/admin` in production).
4. Login with the same email — Stytch sends OTP. Use role **admin** (handled automatically by the dashboard).

## Features

- **Overview** — user and order counts
- **Users** — list customers/tailors, activate/deactivate accounts
- **Orders** — view all platform orders and statuses

## API endpoints (admin JWT required)

- `GET /app/api/v1/admin/stats`
- `GET /app/api/v1/admin/users`
- `GET /app/api/v1/admin/orders`
- `PUT /app/api/v1/users/{id}` — toggle `is_active`

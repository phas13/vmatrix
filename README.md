# VMatrix — Competency Matrix Platform

AI-powered competency matrix assessment platform for engineering teams.

## Quick Start

```bash
cp .env.example .env
# Edit .env with your values
docker compose up
```

Services:
- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- Health check: http://localhost:8000/api/v1/health

## Structure

```
vmatrix/
├── backend/        # FastAPI + SQLAlchemy + Alembic
├── frontend/       # React 18 + TypeScript + Vite + MUI
├── .github/        # CI/CD workflows
├── docker-compose.yml
└── .env.example
```

## Development

See `backend/` and `frontend/` for per-service setup instructions.

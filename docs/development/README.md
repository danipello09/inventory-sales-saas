# Phase 2 development setup

This repository currently contains a minimal Django/DRF backend and React/TypeScript/Vite frontend. No commercial functionality has been implemented.

## Backend

```bash
cd backend
python -m venv .venv
# activate virtual environment
python -m pip install -r requirements.txt
python manage.py check
python -m pytest
python manage.py runserver
```

Smoke endpoint: `http://127.0.0.1:8000/health/`.

## Frontend

```bash
cd frontend
npm install
npm run lint
npm test
npm run build
npm run dev
```

Frontend: `http://localhost:5173`.

## Known gaps

- Docker Compose and GitHub Actions are separate issues #5 and #6.
- Generate and commit `package-lock.json` before using `npm ci` in CI.
- Django uses SQLite only for standalone smoke checks when DATABASE_HOST is unset; integrated development will use PostgreSQL.
- Settings and dependencies need verification in a clean environment before merge.
- No login, catalog, stock or sales endpoints exist.

Follow issue -> branch -> PR -> verified checks -> review -> merge. Do not claim checks passed unless executed.
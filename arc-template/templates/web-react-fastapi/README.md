# Generated Website Application

This project is initialized from the `web-react-fastapi` generation template.

## Stack

- Frontend: Vite + React + React Router + TypeScript + TailwindCSS
- Backend: FastAPI
- Tests: pytest, Vitest, Playwright

## Commands

```bash
npm --prefix frontend install
npm --prefix frontend run dev
npm --prefix frontend run test
npm --prefix frontend run e2e
npm --prefix frontend run build
uvicorn app.main:app --app-dir backend --reload
pytest -q
```

Generation agents should keep implementation inside the template structure:

- UI: `frontend/src`
- API routes: `backend/app/routes.py`
- Function/service logic: `backend/app`
- Local persistence: `backend/app/repository.py`
- Backend tests: `backend/tests`
- Frontend component tests: `frontend/src/**/*.test.tsx`
- Browser E2E tests: `frontend/e2e`

#!/usr/bin/env bash
# Start TitanTool backend and (optionally) frontend dev server.
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Load .env if it exists
if [ -f "$ROOT/.env" ]; then
  export $(grep -v '^#' "$ROOT/.env" | xargs)
fi

echo "==> Starting TitanTool backend on http://localhost:8000"
cd "$ROOT"
uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!

echo "==> Starting TitanTool frontend on http://localhost:5173"
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait

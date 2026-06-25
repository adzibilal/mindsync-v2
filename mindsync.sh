#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

case "${1:-help}" in
  up)
    echo "🚀 Starting MindSync..."
    docker compose up -d
    echo "⏳ Waiting for services..."
    sleep 3

    # Backend
    source .venv/bin/activate
    cd backend
    setsid python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/mindsync-be.log 2>&1 &
    disown
    cd ..
    echo "✅ Backend running on http://localhost:8000"

    # Frontend
    cd frontend
    setsid npm run dev -- -p 3000 > /tmp/mindsync-fe.log 2>&1 &
    disown
    cd ..
    echo "✅ Frontend running on http://localhost:3000"

    echo ""
    echo "📖 API docs: http://localhost:8000/docs"
    echo "🖥️  Dashboard: http://localhost:3000"
    echo ""
    echo "Next steps:"
    echo "  1. Open http://localhost:3000 and login"
    echo "  2. Go to WhatsApp Session to scan QR"
    echo "  3. Upload a document via Knowledge Base"
    echo "  4. Test RAG via Playground"
    ;;
  down)
    echo "🛑 Stopping MindSync..."
    pkill -f "uvicorn app.main" 2>/dev/null || true
    pkill -f "next dev" 2>/dev/null || true
    docker compose down
    echo "✅ Stopped"
    ;;
  logs-be)
    tail -f /tmp/mindsync-be.log
    ;;
  logs-fe)
    tail -f /tmp/mindsync-fe.log
    ;;
  logs)
    echo "=== Backend ===" && tail -f /tmp/mindsync-be.log
    ;;
  status)
    echo "=== Backend ==="
    curl -s http://localhost:8000/health || echo "❌ Not running"
    echo ""
    echo "=== Frontend ==="
    curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:3000 || echo "❌ Not running"
    echo ""
    echo "=== Docker ==="
    docker compose ps
    ;;
  *)
    echo "Usage: $0 {up|down|logs|logs-be|logs-fe|status}"
    echo ""
    echo "  up         Start all services (Docker + Backend + Frontend)"
    echo "  down       Stop all services"
    echo "  logs       Tail backend logs"
    echo "  logs-be    Tail backend logs"
    echo "  logs-fe    Tail frontend logs"
    echo "  status     Check service status"
    ;;
esac

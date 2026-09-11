#!/bin/bash
# NIRMAN — Startup Script
# SIH 2026 Prototype

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
DB_FILE="$BACKEND_DIR/nirman.db"
PORT=${PORT:-5001}

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         NIRMAN — SIH 2026 Prototype             ║"
echo "║   One Platform for Smarter Business Approvals   ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.9+"
    exit 1
fi

# Install dependencies
echo "📦 Checking dependencies..."
pip3 install -q flask flask-sqlalchemy flask-jwt-extended flask-cors flask-migrate bcrypt pillow pytesseract qrcode 2>&1 | grep -E "Installing|Successfully|already" | head -10

# Seed database if needed
if [ ! -f "$DB_FILE" ]; then
    echo "🌱 First run — seeding database with demo data..."
    cd "$BACKEND_DIR" && python3 seed.py
else
    echo "✅ Database found: $DB_FILE"
fi

# Start server
echo ""
echo "🚀 Starting NIRMAN server on port $PORT..."
echo "📡 URL: http://localhost:$PORT"
echo ""
echo "📋 DEMO CREDENTIALS:"
echo "   👤 Applicant: applicant@demo.com / Demo@1234"
echo "   🔍 Inspector: inspector@demo.com / Demo@1234"
echo "   ⚙️  Admin:     admin@demo.com / Demo@1234"
echo "   🤖 AI Agent:  system role — enter via the 'AI DEMO' button in the app"
echo ""
echo "⚠️  SIH PROTOTYPE — Demo data only. Not connected to real systems."
echo ""

cd "$BACKEND_DIR" && PORT=$PORT python3 run.py

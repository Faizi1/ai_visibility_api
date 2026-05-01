#!/usr/bin/env bash
# setup.sh — one-command local setup
# Usage: bash setup.sh

set -e  # stop on any error

echo ""
echo "==================================================="
echo "  AI Visibility Intelligence API — Setup Script"
echo "==================================================="
echo ""

# 1. Check Python version
python_version=$(python3 --version 2>&1)
echo "✓ Using $python_version"

# 2. Create virtual environment
if [ ! -d "venv" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
echo "✓ Virtual environment activated"

# 3. Install dependencies
echo "→ Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# 4. Create .env from example if it doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✓ Created .env file from .env.example"
    echo ""
    echo "  ⚠  IMPORTANT: Open .env and add your ANTHROPIC_API_KEY before continuing!"
    echo ""
else
    echo "✓ .env file already exists"
fi

# 5. Set FLASK_APP
export FLASK_APP=run.py

# 6. Run database migrations
echo "→ Setting up database..."
flask db init 2>/dev/null || true   # already initialised? that's fine
flask db migrate -m "initial schema" 2>/dev/null || true
flask db upgrade
echo "✓ Database ready"

echo ""
echo "==================================================="
echo "  Setup complete! Start the server with:"
echo "    source venv/bin/activate"
echo "    python run.py"
echo ""
echo "  Then test it:"
echo "    curl -X POST http://localhost:5000/api/v1/profiles \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d '{\"name\":\"Frase\",\"domain\":\"frase.io\",\"industry\":\"SEO Content\"}'"
echo "==================================================="

"""
run.py  —  entry point for local development

Usage:
    python run.py

For production, use gunicorn:
    gunicorn "app:create_app()" --bind 0.0.0.0:5000 --workers 2
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True gives you auto-reload and pretty error pages locally
    # Never use debug=True in production
    app.run(debug=True, host="0.0.0.0", port=5000)

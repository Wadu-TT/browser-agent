# Use Playwright's official Python image — includes all browser binaries and
# system dependencies. This eliminates the most common "works locally, fails
# in Docker" problem for Playwright-based projects.
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium --with-deps

# Copy application code
COPY app/ ./app/
COPY frontend/ ./frontend/

# Create logs directory
RUN mkdir -p logs

# Expose API port
EXPOSE 8000

# Health check — pings /health every 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]

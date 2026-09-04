# AI Browser Automation Agent

An AI agent that controls a real web browser using natural language. Give it a task — it navigates, clicks, types, extracts data, and returns structured results.

**Powered by:** Groq API (free) · Playwright · LangGraph · FastAPI

## ✨ Features

- **ReAct loop**: Observe page → LLM decides action → Execute → Repeat
- **100% free**: Uses Groq API (llama-3.3-70b-versatile) — no OpenAI credits needed
- **Smart perception**: DOM simplifier extracts only useful page content (no raw HTML noise)
- **Resilient actions**: Semantic locators (text, role, label) before CSS class fallbacks
- **Structured logging**: Every step logged as JSON for debugging
- **Frontend UI**: Built-in dark-mode web interface

## 🚀 Quick Start

### 1. Get a Groq API key (free)
Go to [console.groq.com](https://console.groq.com) → sign up → create API key.

### 2. Setup
```bash
# Clone and enter project
cd browser-agent

# Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Install Playwright Chromium
playwright install chromium --with-deps

# Copy and edit .env
copy .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 3. Run locally
```bash
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) for the UI, or [http://localhost:8000/docs](http://localhost:8000/docs) for Swagger.

### 4. Run a task via API
```bash
curl -X POST http://localhost:8000/run-task \
  -H "Content-Type: application/json" \
  -d '{"task": "List the top 5 books with prices", "start_url": "https://books.toscrape.com"}'
```

## 🐳 Docker

```bash
# Build and run
docker-compose up --build

# Or run directly
docker build -t browser-agent .
docker run -p 8000:8000 -e GROQ_API_KEY=your_key browser-agent
```

## 🧪 Tests

```bash
pytest tests/ -v
```

## 📁 Project Structure

```
browser-agent/
├── app/
│   ├── main.py                  # FastAPI app + /run-task endpoint
│   ├── graph.py                 # LangGraph ReAct loop
│   ├── state.py                 # BrowserState TypedDict
│   ├── config.py                # Settings from env vars
│   ├── perception/
│   │   └── dom_simplifier.py    # Page → compact text for LLM
│   ├── planner/
│   │   └── planner_agent.py     # Groq LLM action planner
│   ├── actions/
│   │   ├── __init__.py          # Action dispatcher
│   │   ├── browser_controller.py
│   │   ├── click.py
│   │   ├── type_text.py
│   │   ├── navigate.py
│   │   ├── extract_text.py
│   │   └── scroll.py
│   └── logging/
│       └── step_logger.py       # Structured JSON step logs
├── frontend/
│   └── index.html               # Web UI
├── tests/
├── Dockerfile
├── docker-compose.yml
├── render.yaml                  # Free Render.com deployment
└── requirements.txt
```

## 🌐 Deploy to Render.com (Free)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Select **Docker** as runtime
5. Add environment variable: `GROQ_API_KEY = your_key`
6. Deploy!

The `render.yaml` file in this repo handles the rest automatically.

> **Note:** Render free tier sleeps after 15 min inactivity (~30s cold start). Use `/health` to wake it.

## ⚙️ Configuration

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | (required) | Free at console.groq.com |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |
| `MAX_STEPS` | `20` | Step cap per agent run |
| `HEADLESS` | `true` | Browser headless mode |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## 📊 Groq Free Tier Limits

| Model | Req/min | Req/day |
|---|---|---|
| llama-3.3-70b-versatile | 30 | 14,400 |
| llama3-8b-8192 | 30 | 14,400 |

At 1 LLM call per step, a 20-step task = 20 requests → **720 full runs/day for free**.

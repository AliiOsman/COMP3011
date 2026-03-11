# F1 Strategic Intelligence API

> COMP3011 · University of Leeds · 2026

A RESTful API providing Formula 1 race strategy intelligence and analytics. Built with FastAPI, PostgreSQL, JWT authentication, and real race data from 2023–2024.

**Live API:** https://comp3011-f1-api.onrender.com  
**Interactive Docs:** https://comp3011-f1-api.onrender.com/docs  
**Frontend Dashboard:** https://f1-dashboard-1ula.onrender.com  
**Repository:** https://github.com/AliiOsman/COMP3011

> **Note:** The free Render tier sleeps after 15 minutes of inactivity. The first request after sleep takes ~30 seconds to wake the server.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Tech Stack](#tech-stack)
3. [Data Sources](#data-sources)
4. [Setup Instructions](#setup-instructions)
5. [Running Tests](#running-tests)
6. [Authentication](#authentication)
7. [API Endpoints](#api-endpoints)
8. [Deployment](#deployment)
9. [Project Structure](#project-structure)
10. [API Documentation](#api-documentation)

---

## Project Overview

This project delivers a production-deployed REST API that combines historical F1 data with advanced strategy models. Key capabilities include:

- **Constructor Elo Ratings** — pairwise Elo system computed across all race results (K-factor 32, base rating 1500)
- **Wet Weather Scoring** — normalised driver performance in rain, weighted by starting grid position delta
- **Pit Window Calculator** — optimal pit lap recommendations using compound-specific tyre degradation regression models
- **Tyre Degradation Model** — quadratic regression on OpenF1 stint data per circuit per compound
- **Head-to-Head Rivalry Analyser** — direct driver comparisons across all shared race starts with dominance scoring
- **AI Strategy Advisor** — LLaMA 3.1 via Groq, seeded with live Elo + pit data + 2026 regulation context
- **MCP Compatibility** — structured manifest for AI agent tool discovery (Claude, GPT, etc.)

### Architecture

```
┌──────────────────────────────────────────────────────┐
│                  FastAPI Application                 │
├─────────────────┬────────────────┬───────────────────┤
│   Auth Router   │ Strategy       │ Analytics         │
│   JWT + Argon2  │ Router         │ Router            │
├─────────────────┴────────────────┴───────────────────┤
│            Repository Pattern (Services)             │
├──────────────────────────────────────────────────────┤
│          SQLAlchemy Async ORM + asyncpg              │
├──────────────────────────────────────────────────────┤
│                  PostgreSQL Database                 │
└──────────────────────────────────────────────────────┘
```
```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│   Browser Dashboard   ·   curl / Postman   ·   AI Agent (MCP)       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTPS
┌───────────────────────────────▼─────────────────────────────────────┐
│                      RENDER (Production)                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    FastAPI (ASGI / uvicorn)                 │    │
│  │  ┌──────────┐  ┌─────────────┐  ┌───────────┐  ┌────────┐   │    │
│  │  │   Auth   │  │  Strategy   │  │ Analytics │  │  MCP   │   │    │
│  │  │  Router  │  │   Router    │  │  Router   │  │ Router │   │    │
│  │  └────┬─────┘  └──────┬──────┘  └─────┬─────┘  └───┬────┘   │    │
│  │       │               │               │            │        │    │
│  │  ┌────▼───────────────▼───────────────▼────────────▼──────┐ │    │
│  │  │                  Service Layer                         │ │    │
│  │  │  elo_service · pit_window · wet_weather · ai_strategist│ │    │
│  │  └────────────────────────┬───────────────────────────────┘ │    │
│  │                           │                                 │    │
│  │  ┌────────────────────────▼────────────────────────────────┐│    │
│  │  │         SQLAlchemy Async ORM (asyncpg)                  ││    │
│  │  └────────────────────────┬────────────────────────────────┘│    │
│  └───────────────────────────│─────────────────────────────────┘    │
│                              │                                      │
│  ┌───────────────────────────▼───────────────┐                      │
│  │        Render Managed PostgreSQL          │                      │
│  │  drivers · races · results · pitstops     │                      │
│  │  tyre_stints · weather_snapshots · users  │                      │
│  └───────────────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Groq API (LLaMA 3.1)│
                    │   Ollama (local dev)  │
                    └───────────────────────┘
________________________________________

```
---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI + Python 3.11 |
| Database | PostgreSQL 14 (asyncpg) |
| ORM | SQLAlchemy 2.0 async |
| Validation | Pydantic v2 + pydantic-settings |
| Auth | JWT Bearer (HS256) + Argon2id |
| AI Provider | Groq / LLaMA 3.1-8b-instant |
| Rate Limiting | slowapi (Starlette middleware) |
| Deployment | Render (auto-deploy from `main`) |
| Testing | pytest · ~120 tests · ~80% coverage |
| Architecture | Repository Pattern + MCP Compatible |

---

## Data Sources

| Source | Coverage | Data Included |
|--------|----------|---------------|
| Kaggle F1 Historical Dataset | 1950–2023 | Race results, constructors, drivers, circuits, pit stop times, qualifying |
| Jolpica / Ergast API | 2024 season | Race results, championship standings, constructor points |
| OpenF1 Telemetry API | 2023–2024 | Tyre stint data (compound, lap range), weather telemetry per session |


---

## Setup Instructions

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Git
- Groq API key — free at [console.groq.com](https://console.groq.com)

### 1. Clone the Repository

```bash
git clone https://github.com/AliiOsman/COMP3011.git
cd COMP3011
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/f1_strategy
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
GROQ_API_KEY=your-groq-api-key
```

> Generate a strong secret key with: `openssl rand -hex 32`

### 5. Create the Database

```bash
createdb f1_strategy
```

### 6. Run Migrations

```bash
alembic upgrade head
```

### 7. Seed the Database

```bash
python scripts/seed_ergast.py
```

The seeder runs three phases:

1. **Phase 1 — Kaggle CSVs:** circuits, constructors, drivers, races 2018–2023, results, pit stops
2. **Phase 2 — Jolpica/Ergast API:** 2024 season races and results
3. **Phase 3 — OpenF1 API:** tyre stints and weather snapshots for 2023–2024 sessions

### 8. Start the Server

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Running Tests

```bash
pytest                                          # Run all tests
pytest -v                                       # Verbose output
pytest tests/test_strategy.py -v               # Specific module
pytest --cov=app --cov-report=term-missing     # With coverage
```

Expected: ~120 tests, ~80% coverage.

> Rate-limit tests require `TESTING=true` in the environment to bypass per-minute throttling. This is handled automatically by `conftest.py`.

---

## Authentication

All strategy and analytics endpoints require a JWT Bearer token. The API uses OAuth2 password flow.

### Register

```bash
curl -X POST https://comp3011-f1-api.onrender.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "myuser", "password": "mypassword123"}'
```

### Login

```bash
curl -X POST https://comp3011-f1-api.onrender.com/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=myuser&password=mypassword123"
```

### Use Token

```bash
curl https://comp3011-f1-api.onrender.com/api/v1/strategy/constructor-elo \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## API Endpoints

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/auth/register` | Public | Create a new user account |
| `POST` | `/api/v1/auth/token` | Public | Exchange credentials for a JWT token |
| `GET` | `/api/v1/auth/me` | Required | Return the current authenticated user |

### Drivers

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/drivers/` | Public | List all drivers (`skip`, `limit` up to 500) |
| `POST` | `/api/v1/drivers/` | Required | Create a new driver record |
| `GET` | `/api/v1/drivers/search?nationality=` | Public | Search drivers by nationality |
| `GET` | `/api/v1/drivers/{driver_id}` | Public | Get a specific driver by ID |
| `PUT` | `/api/v1/drivers/{driver_id}` | Required | Update a driver record |
| `DELETE` | `/api/v1/drivers/{driver_id}` | Required | Delete a driver record |

### Races

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/races/` | Public | List races (filter by `season`, `circuit_id`; limit 200) |
| `POST` | `/api/v1/races/` | Required | Create a new race record |
| `GET` | `/api/v1/races/{race_id}` | Public | Get a specific race by ID |
| `PUT` | `/api/v1/races/{race_id}` | Required | Update a race record |
| `DELETE` | `/api/v1/races/{race_id}` | Required | Delete a race record |

### Pit Stops

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/pitstops/` | Public | List pit stops (filter by `race_id`, `driver_id`; limit 500) |
| `POST` | `/api/v1/pitstops/` | Required | Create a pit stop record |
| `GET` | `/api/v1/pitstops/{pitstop_id}` | Public | Get a specific pit stop by ID |
| `PUT` | `/api/v1/pitstops/{pitstop_id}` | Required | Update a pit stop record |
| `DELETE` | `/api/v1/pitstops/{pitstop_id}` | Required | Delete a pit stop record |

### Strategy Intelligence

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/strategy/constructor-elo` | Public | Pairwise Elo ratings for all constructors (K=32, base 1500) |
| `GET` | `/api/v1/strategy/wet-weather-scores` | Public | Normalised driver wet weather performance rankings |
| `GET` | `/api/v1/strategy/pit-window/{race_id}/{driver_id}` | Public | Optimal pit lap recommendations with stint analysis |
| `GET` | `/api/v1/strategy/tyre-model/{circuit_id}/{compound}` | Public | Quadratic degradation curve for a compound at a circuit |

> Compound accepts `SOFT`, `MEDIUM`, `HARD`, `INTERMEDIATE`, or `WET`.

### Analytics

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/analytics/pit-crew-performance` | Public | Constructors ranked by pit stop speed — mean, min, std deviation |
| `GET` | `/api/v1/analytics/circuit-overtaking-difficulty` | Public | Circuits ranked by mean position change (grid → finish) |
| `GET` | `/api/v1/analytics/tyre-degradation` | Public | Regression on stint data — requires `circuit_id` and `compound` query params |
| `GET` | `/api/v1/analytics/driver-season-summary/{driver_id}` | Public | Season stats: points, wins, podiums, DNFs, avg finishing position |
| `GET` | `/api/v1/analytics/head-to-head/{driver_a_id}/{driver_b_id}` | Public | Head-to-head rivalry with dominance score and conditions breakdown |
| `GET` | `/api/v1/analytics/ai-strategy/{constructor}/{circuit}` | Public | LLaMA 3.1 + Elo data + 2026 regulation strategic advice |

### MCP & Utility

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/mcp/manifest` | Public | MCP tool manifest for AI agent integration |
| `GET` | `/mcp/health` | Public | Health check endpoint for MCP agent polling |
| `GET` | `/` | Public | Root — full API metadata as structured JSON |
| `GET` | `/docs` | Public | Interactive Swagger UI |
| `GET` | `/redoc` | Public | ReDoc API documentation |

### Rate Limits

| Endpoint | Limit |
|----------|-------|
| `POST /api/v1/auth/register` | 5 / minute |
| `POST /api/v1/auth/token` | 10 / minute |
| `GET /api/v1/strategy/*` | 30 / minute |
| `GET /api/v1/analytics/*` | 30 / minute |

---

## Deployment

The application is deployed on Render using the `render.yaml` configuration. Auto-deploy is enabled — every push to `main` triggers a new build and deployment.

### Environment Variables

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Render PostgreSQL internal URL (set automatically) |
| `SECRET_KEY` | Random secure string — `openssl rand -hex 32` |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` |
| `GROQ_API_KEY` | From [console.groq.com](https://console.groq.com) |
| `PYTHON_VERSION` | `3.11.9` |

---

## Project Structure

```
COMP3011/
├── app/
│   ├── main.py               # FastAPI app, CORS, rate limiter, middleware
│   ├── config.py             # Settings via pydantic-settings
│   ├── database.py           # Async SQLAlchemy engine and session factory
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── driver.py
│   │   ├── race.py
│   │   ├── result.py
│   │   ├── pitstop.py        # table: pitstops
│   │   ├── stint.py          # table: tyre_stints
│   │   └── constructor.py
│   ├── routers/              # FastAPI route handlers
│   │   ├── auth.py
│   │   ├── strategy.py
│   │   ├── analytics.py
│   │   └── mcp.py
│   └── services/             # Business logic (repository pattern)
│       ├── pit_window.py
│       ├── elo_service.py
│       ├── wet_weather.py
│       └── ai_strategist.py
├── scripts/
│   └── seed_ergast.py        # 3-phase database seeder
├── tests/                    # pytest test suite (~120 tests)
│   └── conftest.py
├── frontend/
│   └── index.html            # Dashboard UI (6 tabs)
├── render.yaml               # Render deployment config
├── runtime.txt               # Python 3.11.9 pin
├── requirements.txt
└── README.md
```

---

## API Documentation

Full interactive documentation is available at:

| Interface | URL |
|-----------|-----|
| Swagger UI | https://comp3011-f1-api.onrender.com/docs |
| ReDoc | https://comp3011-f1-api.onrender.com/redoc |
| OpenAPI JSON | https://comp3011-f1-api.onrender.com/openapi.json |

[View the API DOC](./API_DOC.pdf)
---

## License

Academic project — COMP3011, University of Leeds, 2026. MIT License.

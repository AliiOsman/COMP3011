# COMP3011
## Live API
Base URL:   https://comp3011-f1-api.onrender.com
Documentation:   https://comp3011-f1-api.onrender.com/docs
Front end: https://f1-dashboard-1ula.onrender.com

---

## Marking Scheme Dissected

| Criterion | Marks | What To Do |
|---|---|---|
| API Functionality & Implementation | 25 | Novel endpoints, not just CRUD. Analytical depth. |
| Code Quality & Architecture | 20 | Modular, layered, professional patterns |
| Documentation | 12 | Publication-quality, Swagger + written |
| Version Control & Deployment | 6 | Consistent commits, live deployment |
| Testing & Error Handling | 6 | Pytest suite, edge cases, demonstrated coverage |
| Creativity & GenAI Usage | 6 | AI used to explore alternatives, not just write code |
| Presentation | 15 | Visual demos, architecture diagrams, confident delivery |
| Q&A | 10 | Defend every decision under expert questioning |


---

## The Architecture

```
F1 Strategic Intelligence API
├── Core CRUD layer 
│ ├── Drivers
│ ├── Circuits
│ ├── Races
│ └── PitStops
│
├── Intelligence Layer
│ ├── Optimal Pit Window Calculator
│ ├── Undercut/Overcut Opportunity Detector
│ ├── Tyre Degradation Modeller
│ ├── Driver Wet Weather Performance Scorer
│ └── Constructor Elo Rating Engine
│
└── Data Fusion Layer (novel multi-dataset integration)
    ├── Ergast F1 historical data (seeded into PostgreSQL)
    └── OpenWeatherMap historical weather at race circuits
```

---

## Tech Stack 

| Component | Choice | Justification |
|---|---|---|
| Framework | **FastAPI** | Async-native, auto-generates OpenAPI docs, modern —  active choice over Django |
| Database | **PostgreSQL** | SQL required, relational integrity, indexing strategies |
| ORM | **SQLAlchemy 2.0** (async) | State-of-the-art, async sessions, typed |
| Data Seeding | **FastF1 + Ergast** | FastF1 is what real F1 engineers use |
| Auth | **JWT via python-jose + passlib** | Industry standard, demonstrable RBAC |
| Validation | **Pydantic v2** | Built into FastAPI, strict typing, custom validators |
| Testing | **Pytest + HTTPX AsyncClient** | Async testing, proper integration tests |
| Docs | **Swagger UI (auto) + ReDoc** | Two documentation interfaces out of the box |
| Deployment | **Railway** | Free PostgreSQL, GitHub integration, professional URLs |
| Rate Limiting | **slowapi** | FastAPI-native rate limiting middleware |
| Caching | **Redis via upstash (free tier)** | Cache expensive analytical computations |
| CI/CD | **GitHub Actions** | Auto-run tests on push — visible in repo |

---

## Complete Endpoint Design

### CRUD Layer

```
POST   /api/v1/drivers              Create driver
GET    /api/v1/drivers              List all drivers (paginated)
GET    /api/v1/drivers/{id}         Get driver by ID
PUT    /api/v1/drivers/{id}         Update driver
DELETE /api/v1/drivers/{id}         Delete driver (admin only)

POST   /api/v1/races                Create race entry
GET    /api/v1/races                List races (filterable by season, circuit)
GET    /api/v1/races/{id}           Get race details
PUT    /api/v1/races/{id}           Update race
DELETE /api/v1/races/{id}           Delete race

POST   /api/v1/pitstops             Log pit stop
GET    /api/v1/pitstops/{race_id}   Get all pit stops for a race
PUT    /api/v1/pitstops/{id}        Update pit stop record
DELETE /api/v1/pitstops/{id}        Delete pit stop
```

### Intelligence Endpoints

```
GET /api/v1/strategy/optimal-pit-window/{race_id}/{driver_id}
    → Returns calculated optimal pit lap based on tyre age,
      gap to cars ahead/behind, historical undercut data

GET /api/v1/strategy/undercut-threat/{race_id}/{driver_id}
    → Calculates whether driver ahead is vulnerable to undercut
      given current gap and pit stop delta at this circuit

GET /api/v1/strategy/tyre-degradation/{circuit_id}/{compound}
    → Models expected lap time degradation curve for a tyre
      compound at a specific circuit (regression-based)

GET /api/v1/analytics/driver-wet-performance
    → Scores all drivers on wet weather performance using
      weighted position delta (qualifying vs race result
      in rain-affected races, cross-referenced with weather data)

GET /api/v1/analytics/constructor-elo
    → Returns current Elo ratings for all constructors,
      updated race-by-race since 2018

GET /api/v1/analytics/pit-crew-performance/{constructor_id}
    → Ranks pit stop execution speed with statistical
      outlier detection (fastest stops, consistency score)

GET /api/v1/analytics/circuit-overtaking-difficulty
    → Scores circuits by overtaking opportunity using
      position change data, DRS zones, safety car frequency

GET /api/v1/predict/race-strategy/{circuit_id}
    → Given circuit characteristics and current season
      tyre data, predicts likely optimal strategy (1-stop vs 2-stop)
```

---

## Database Schema (Normalised)

```sql
-- Core tables
drivers (id, forename, surname, nationality, dob, career_points)
constructors (id, name, nationality, founded_year)
circuits (id, name, country, city, lat, lng, length_km, overtaking_score)
seasons (id, year)
races (id, season_id, circuit_id, name, date, weather_condition, rainfall_mm)

-- Performance tables
results (id, race_id, driver_id, constructor_id, grid, position,
         points, laps, status, fastest_lap_time)
pitstops (id, race_id, driver_id, stop_number, lap, duration_seconds,
          tyre_compound, tyre_age_laps)
lap_times (id, race_id, driver_id, lap, time_seconds)

-- Intelligence tables (your novel contribution)
constructor_elo (id, constructor_id, race_id, elo_before, elo_after, date)
tyre_degradation_models (id, circuit_id, compound, coeff_a, coeff_b,
                          coeff_c, r_squared, computed_at)
weather_snapshots (id, race_id, temperature_c, humidity_pct,
                   wind_speed_kmh, rainfall_mm, fetched_from_api)
```

**Key indexing strategy to mention in your report and Q&A:**
- Composite index on `(race_id, driver_id)` for results and pitstops
- Index on `(circuit_id, compound)` for tyre degradation lookups
- Index on `constructor_id, date` for Elo time-series queries

---

## The Algorithms You'll Implement

### 1. Constructor Elo Rating
Adapt standard Elo but use *points scored vs expected points* as the performance metric rather than win/loss. K-factor varies by race importance (title decider races weight more). This is defensible, original, and analytically interesting.

### 2. Optimal Pit Window
```
pit_score(lap) = position_risk(gap_behind, avg_pit_delta)
              + tyre_performance_loss(compound, age)
              - undercut_threat(gap_ahead, pit_delta_circuit)
```
Return the lap where `pit_score` is maximised. Simple enough to build in a week, complex enough to explain for 5 minutes.

### 3. Wet Weather Performance Score
```
wet_score(driver) = mean(qualifying_position - race_position)
                    for all races where rainfall_mm > threshold
weighted by field_size and season_recency
```
Positive score = driver gains positions in wet conditions relative to their qualifying pace.

### 4. Tyre Degradation Curve
Fit a quadratic regression (`numpy.polyfit`) on lap time vs tyre age for each compound/circuit combination. Store coefficients in the `tyre_degradation_models` table. Endpoint returns predicted lap time at age N laps. This is lightweight ML that you can fully explain.

---

## Project Folder Structure

```
f1-strategy-api/
├── app/
│   ├── main.py                 # FastAPI app factory
│   ├── config.py               # Settings via pydantic-settings
│   ├── database.py             # Async SQLAlchemy engine
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── driver.py
│   │   ├── race.py
│   │   ├── pitstop.py
│   │   └── elo.py
│   ├── schemas/                # Pydantic v2 schemas (request/response)
│   ├── routers/                # FastAPI routers by domain
│   │   ├── drivers.py
│   │   ├── races.py
│   │   ├── strategy.py         # Intelligence endpoints
│   │   └── analytics.py
│   ├── services/               # Business logic layer
│   │   ├── pit_window.py
│   │   ├── elo_engine.py
│   │   ├── tyre_model.py
│   │   └── weather_service.py
│   ├── repositories/           # Database access layer
│   └── middleware/             # Rate limiting, auth, logging
├── scripts/
│   ├── seed_ergast.py          # Pulls and seeds F1 data
│   └── seed_weather.py         # Fetches historical weather
├── tests/
│   ├── test_crud.py
│   ├── test_strategy.py
│   └── test_analytics.py
├── docs/
│   └── api_documentation.pdf
├── .github/workflows/
│   └── test.yml                # CI/CD pipeline
├── README.md
├── requirements.txt
└── docker-compose.yml          # Local dev environment
```

This layered architecture (Router → Service → Repository → Model) is a professional pattern you can name and defend: it's the **Repository Pattern with Service Layer**.

## GenAI Usage Strategy (6 marks — this is where most students leave marks)

**Conversation 1:** Ask AI to propose three different architectural patterns for the API (Repository Pattern vs Active Record vs CQRS) and critically evaluate which suits this project — then explain why you rejected CQRS as overengineered.

**Conversation 2:** Ask AI to propose alternative algorithms for pit window optimisation. Critically compare a rule-based approach vs a regression model vs a Monte Carlo simulation. Justify why you chose regression.

**Conversation 3:** Ask AI to critique your schema design and find normalisation flaws. Show you evaluated its suggestions and selectively applied them.

**Conversation 4:** Ask AI whether FastAPI vs Django REST Framework vs Litestar was the right framework choice, with specific pros/cons for this use case.

Export all of these as conversation logs. This is literally what the marking rubric rewards. You're doing it right now — export this conversation.

---

## Testing Strategy (6 marks)

```python
# tests/test_strategy.py — example structure

async def test_pit_window_returns_valid_lap_number():
    # Given a race with pit stop data seeded
    # When calling /strategy/optimal-pit-window
    # Then response contains lap number within race lap range

async def test_pit_window_with_no_data_returns_404():
    # Edge case: race has no pit stop history

async def test_elo_updates_after_race_seeding():
    # Given constructors with pre-seeded results
    # When Elo engine runs
    # Then Elo values change in expected direction

async def test_wet_score_negative_for_dry_specialist():
    # Hamilton should score positive, some drivers negative
```

Use `pytest-cov` to generate coverage report. Aim for 70%+ coverage. Screenshot it for your presentation.

---

## Build Timeline (3 weeks to deadline)

**Week 1 — Foundation**
- Days 1–2: Set up FastAPI, PostgreSQL, SQLAlchemy async, JWT auth
- Days 3–4: Implement all CRUD endpoints with Pydantic validation
- Day 5: Seed database from Ergast, write seed scripts

**Week 2 — Intelligence Layer**
- Days 1–2: Constructor Elo engine
- Days 3–4: Pit window calculator + tyre degradation model
- Day 5: Wet weather scorer + OpenWeatherMap integration

**Week 3 — Polish**
- Day 1: Rate limiting, error handling, API versioning (`/api/v1/`)
- Day 2: Tests and CI/CD GitHub Actions
- Day 3: Deploy to Railway, generate Swagger PDF
- Day 4: Technical report (5 pages)
- Day 5: Presentation slides + rehearsal

---

## What to Say in the Q&A (Pre-empt Every Hard Question)

**"Why FastAPI over Django?"** — Async-native for I/O-bound analytical endpoints, automatic OpenAPI generation, Pydantic v2 native integration, better performance for concurrent requests.

**"Why PostgreSQL over SQLite?"** — ACID compliance, proper indexing, production-grade, concurrent connections for deployment.

**"How does your Elo algorithm handle new constructors?"** — Initialise at 1500 (standard), apply dampened K-factor for first 5 races to avoid volatility from small sample size.

**"What are the limitations of your pit window model?"** — It's retrospective (uses historical data), doesn't model safety car probability, doesn't account for virtual safety cars, and relies on Ergast data which has occasional gaps pre-2011.

**"How did you use AI critically?"** — I used it to propose three architectural alternatives, then rejected two with specific reasoning. I also asked it to attack my schema design and found it missed a denormalisation opportunity in the lap_times table.

---

## The One Thing That Will Separate You from 85% Students

Every endpoint in your intelligence layer must have a **documented mathematical justification** in your technical report. One paragraph per algorithm explaining the formula, why you chose it, what its limitations are, and what you'd replace it with given more time (e.g., "replace quadratic regression with a Gaussian process for uncertainty quantification").

That is what "genuine research curiosity" and "publication-quality documentation" looks like to an examiner. Nobody else will do this.

---
## BUILD UI TO INTERACT WITH API

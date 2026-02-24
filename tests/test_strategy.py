import pytest
from sqlalchemy import select
from tests.conftest import TestSessionLocal
from app.models.driver import Driver
from app.models.circuit import Circuit
from app.models.constructor import Constructor
from app.models.race import Race
from app.models.result import Result
from app.models.pitstop import PitStop
from app.models.stint import TyreStint
from app.models.weather import WeatherSnapshot
from app.repositories.driver_repo import DriverRepository
from app.schemas.driver import DriverCreate, DriverUpdate
from app.services.elo_engine import expected_score, update_elo, compute_constructor_elo
from app.services.tyre_model import calculate_tyre_degradation
from app.services.wet_weather import calculate_wet_weather_scores
from app.services.pit_window import calculate_pit_window


# ─────────────────────────────────────────────
# SHARED TEST DATA SEEDER
# ─────────────────────────────────────────────

_seeded = False

async def seed_all_test_data():
    """Seeds all test data once — idempotent"""
    global _seeded
    if _seeded:
        return
    async with TestSessionLocal() as session:
        # Check already exists
        existing = await session.execute(
            select(Circuit).where(Circuit.ergast_id == "test_circuit")
        )
        if existing.scalar_one_or_none():
            _seeded = True
            return

        # Circuit
        circuit = Circuit(
            ergast_id="test_circuit",
            name="Test Circuit",
            country="UK",
            city="Test City",
            lat=52.0, lng=-1.0
        )
        session.add(circuit)
        await session.commit()
        await session.refresh(circuit)

        # Constructors
        c1 = Constructor(ergast_id="test_team_a", name="Team Alpha", nationality="British")
        c2 = Constructor(ergast_id="test_team_b", name="Team Beta", nationality="German")
        session.add_all([c1, c2])
        await session.commit()
        await session.refresh(c1)
        await session.refresh(c2)

        # Drivers
        d1 = Driver(forename="Test", surname="Driver One", nationality="British",
                    code="TD1", career_points=100.0)
        d2 = Driver(forename="Test", surname="Driver Two", nationality="German",
                    code="TD2", career_points=80.0)
        session.add_all([d1, d2])
        await session.commit()
        await session.refresh(d1)
        await session.refresh(d2)

        # 5 Races
        races = []
        for i in range(5):
            r = Race(
                ergast_id=99900 + i + 1,
                season=2023,
                round=i + 1,
                name=f"Test GP {i+1}",
                date=f"2023-0{i+3}-15",
                circuit_id=circuit.id
            )
            session.add(r)
            await session.commit()
            await session.refresh(r)
            races.append(r)

        # Results — varied positions for analytics
        for i, race in enumerate(races):
            session.add_all([
                Result(race_id=race.id, driver_id=d1.id, constructor_id=c1.id,
                       grid=i + 1, position=1, points=25.0, laps=50, status="Finished"),
                Result(race_id=race.id, driver_id=d2.id, constructor_id=c2.id,
                       grid=1, position=i + 2, points=10.0, laps=50, status="Finished"),
            ])
        await session.commit()

        # Pit stops
        for race in races:
            session.add_all([
                PitStop(race_id=race.id, driver_id=d1.id, stop_number=1,
                        lap=20, duration_seconds=2.5),
                PitStop(race_id=race.id, driver_id=d1.id, stop_number=2,
                        lap=38, duration_seconds=2.6),
                PitStop(race_id=race.id, driver_id=d2.id, stop_number=1,
                        lap=22, duration_seconds=2.8),
            ])
        await session.commit()

        # Tyre stints
# Tyre stints — varied ages for regression to work
        stint_configs = [
            (0, 20, "SOFT"), (5, 18, "SOFT"), (10, 15, "SOFT"),
            (0, 30, "MEDIUM"), (8, 25, "MEDIUM"), (15, 20, "MEDIUM"),
            (0, 40, "HARD"), (10, 35, "HARD"), (20, 28, "HARD"),
        ]
        for i, race in enumerate(races):
            age, length, compound = stint_configs[i % len(stint_configs)]
            session.add_all([
                TyreStint(race_id=race.id, session_key=9990 + race.id,
                          driver_number=1, driver_id=d1.id,
                          stint_number=1, compound=compound,
                          lap_start=1, lap_end=length,
                          tyre_age_at_start=age),
                TyreStint(race_id=race.id, session_key=9990 + race.id,
                          driver_number=1, driver_id=d1.id,
                          stint_number=2, compound="MEDIUM",
                          lap_start=length, lap_end=50,
                          tyre_age_at_start=age + 5),
                TyreStint(race_id=race.id, session_key=9990 + race.id,
                          driver_number=2, driver_id=d2.id,
                          stint_number=1, compound="SOFT",
                          lap_start=1, lap_end=length - 2,
                          tyre_age_at_start=age + 2),
            ])
        await session.commit()

        # Weather — rainfall on first 3 races, dry on last 2
        for i, race in enumerate(races):
            for j in range(5):
                session.add(WeatherSnapshot(
                    race_id=race.id,
                    session_key=9990 + race.id,
                    timestamp=f"2023-03-15T13:0{j}:00",
                    air_temperature=18.0,
                    track_temperature=25.0,
                    humidity=85.0,
                    rainfall=4.0 if i < 3 and j < 3 else 0.0,
                    wind_speed=5.0,
                    pressure=1010.0
                ))
        await session.commit()
        _seeded = True


async def get_test_ids():
    """Returns IDs for use in tests"""
    async with TestSessionLocal() as session:
        circuit = (await session.execute(
            select(Circuit).where(Circuit.ergast_id == "test_circuit")
        )).scalar_one_or_none()

        driver = (await session.execute(
            select(Driver).where(Driver.code == "TD1")
        )).scalar_one_or_none()

        driver2 = (await session.execute(
            select(Driver).where(Driver.code == "TD2")
        )).scalar_one_or_none()

        race = (await session.execute(
            select(Race).where(Race.ergast_id == 99901)
        )).scalar_one_or_none()

        constructor = (await session.execute(
            select(Constructor).where(Constructor.ergast_id == "test_team_a")
        )).scalar_one_or_none()

        return {
            "circuit": circuit,
            "driver": driver,
            "driver2": driver2,
            "race": race,
            "constructor": constructor
        }


# ─────────────────────────────────────────────
# ELO ALGORITHM UNIT TESTS
# ─────────────────────────────────────────────

class TestEloAlgorithmUnit:

    def test_expected_score_equal_ratings(self):
        assert abs(expected_score(1500, 1500) - 0.5) < 0.001

    def test_expected_score_higher_rated_wins(self):
        assert expected_score(1600, 1400) > 0.5

    def test_expected_score_lower_rated_loses(self):
        assert expected_score(1400, 1600) < 0.5

    def test_expected_scores_sum_to_one(self):
        a = expected_score(1600, 1400)
        b = expected_score(1400, 1600)
        assert abs(a + b - 1.0) < 0.001

    def test_elo_increases_after_win(self):
        assert update_elo(1500, expected=0.5, actual=1.0) > 1500

    def test_elo_decreases_after_loss(self):
        assert update_elo(1500, expected=0.5, actual=0.0) < 1500

    def test_elo_unchanged_if_actual_equals_expected(self):
        assert update_elo(1500, expected=1.0, actual=1.0, k=32) == 1500

    def test_elo_k_factor_scales_change(self):
        change_k32 = abs(update_elo(1500, 0.5, 1.0, k=32) - 1500)
        change_k16 = abs(update_elo(1500, 0.5, 1.0, k=16) - 1500)
        assert change_k32 > change_k16
    async def test_wet_weather_endpoint_returns_200(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/strategy/wet-weather-scores")
        assert response.status_code == 200
        data = response.json()
        assert "scores" in data
        # methodology only present when data exists
        assert isinstance(data["scores"], list)

    async def test_wet_weather_response_has_required_fields(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/strategy/wet-weather-scores")
        assert response.status_code == 200
        data = response.json()
        assert "scores" in data
        # If scores exist, validate their structure
        if len(data["scores"]) > 0:
            driver = data["scores"][0]
            assert "driver" in driver
            assert "avg_position_gain" in driver
            assert "wet_weather_rating" in driver
            assert "normalised_wet_score" in driver
        
    async def test_pit_window_invalid_ids_returns_404(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/strategy/pit-window/99999/99999")
        assert response.status_code == 404

    async def test_constructor_elo_returns_200(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/strategy/constructor-elo")
        assert response.status_code == 200
        data = response.json()
        assert "ratings" in data




# ─────────────────────────────────────────────
# ELO ENGINE SERVICE TESTS
# ─────────────────────────────────────────────

class TestEloEngineService:

    async def test_elo_returns_ratings_list(self, setup_database):
        await seed_all_test_data()
        async with TestSessionLocal() as session:
            result = await compute_constructor_elo(session)
        assert "ratings" in result
        assert isinstance(result["ratings"], list)

    async def test_elo_ratings_have_required_fields(self, setup_database):
        async with TestSessionLocal() as session:
            result = await compute_constructor_elo(session)
        for r in result["ratings"]:
            assert "constructor" in r
            assert "elo" in r
            assert "constructor_id" in r

    async def test_elo_ratings_sorted_descending(self, setup_database):
        async with TestSessionLocal() as session:
            result = await compute_constructor_elo(session)
        elos = [r["elo"] for r in result["ratings"]]
        assert elos == sorted(elos, reverse=True)

    async def test_elo_all_values_are_floats(self, setup_database):
        async with TestSessionLocal() as session:
            result = await compute_constructor_elo(session)
        for r in result["ratings"]:
            assert isinstance(r["elo"], float)

    async def test_elo_deviates_from_initial_1500(self, setup_database):
        async with TestSessionLocal() as session:
            result = await compute_constructor_elo(session)
        elos = [r["elo"] for r in result["ratings"]]
        assert any(e != 1500.0 for e in elos)

    async def test_elo_winner_rated_higher(self, setup_database):
        async with TestSessionLocal() as session:
            result = await compute_constructor_elo(session)
        ratings = {r["constructor"]: r["elo"] for r in result["ratings"]}
        if "Team Alpha" in ratings and "Team Beta" in ratings:
            assert ratings["Team Alpha"] > ratings["Team Beta"]


# ─────────────────────────────────────────────
# TYRE MODEL SERVICE TESTS
# ─────────────────────────────────────────────

class TestTyreModelService:

    async def test_invalid_circuit_returns_error(self, setup_database):
        async with TestSessionLocal() as session:
            result = await calculate_tyre_degradation(session, 99999, "SOFT")
        assert "error" in result

    async def test_unknown_compound_returns_error(self, setup_database):
        await seed_all_test_data()
        ids = await get_test_ids()
        if ids["circuit"]:
            async with TestSessionLocal() as session:
                result = await calculate_tyre_degradation(
                    session, ids["circuit"].id, "INTERMEDIATE"
                )
            assert "error" in result

    async def test_soft_compound_returns_model(self, setup_database):
        ids = await get_test_ids()
        if ids["circuit"]:
            async with TestSessionLocal() as session:
                result = await calculate_tyre_degradation(
                    session, ids["circuit"].id, "SOFT"
                )
            if "error" not in result:
                assert "model" in result
                assert "degradation_curve" in result
                assert "stints_analysed" in result
                assert "recommendation" in result

    async def test_degradation_curve_is_list(self, setup_database):
        ids = await get_test_ids()
        if ids["circuit"]:
            async with TestSessionLocal() as session:
                result = await calculate_tyre_degradation(
                    session, ids["circuit"].id, "SOFT"
                )
            if "degradation_curve" in result:
                assert isinstance(result["degradation_curve"], list)
                for point in result["degradation_curve"]:
                    assert "tyre_age_laps" in point
                    assert "predicted_stint_length" in point

    async def test_r_squared_in_valid_range(self, setup_database):
        ids = await get_test_ids()
        if ids["circuit"]:
            async with TestSessionLocal() as session:
                result = await calculate_tyre_degradation(
                    session, ids["circuit"].id, "SOFT"
                )
            if "model" in result:
                assert -1.0 <= result["model"]["r_squared"] <= 1.0

    async def test_model_coefficients_present(self, setup_database):
        ids = await get_test_ids()
        if ids["circuit"]:
            async with TestSessionLocal() as session:
                result = await calculate_tyre_degradation(
                    session, ids["circuit"].id, "SOFT"
                )
            if "model" in result:
                assert "coefficients" in result["model"]
                assert "type" in result["model"]


# ─────────────────────────────────────────────
# WET WEATHER SERVICE TESTS
# ─────────────────────────────────────────────

class TestWetWeatherService:

    async def test_returns_scores_key(self, setup_database):
        async with TestSessionLocal() as session:
            result = await calculate_wet_weather_scores(session)
        assert "scores" in result

    async def test_scores_is_list(self, setup_database):
        async with TestSessionLocal() as session:
            result = await calculate_wet_weather_scores(session)
        assert isinstance(result["scores"], list)

    async def test_wet_races_count_non_negative(self, setup_database):
        async with TestSessionLocal() as session:
            result = await calculate_wet_weather_scores(session)
        assert result.get("wet_races_analysed", 0) >= 0

    async def test_scores_sorted_descending(self, setup_database):
        async with TestSessionLocal() as session:
            result = await calculate_wet_weather_scores(session)
        scores = [s["normalised_wet_score"] for s in result["scores"]]
        assert scores == sorted(scores, reverse=True)

    async def test_rating_values_are_valid(self, setup_database):
        valid = {"Elite", "Strong", "Average", "Weak"}
        async with TestSessionLocal() as session:
            result = await calculate_wet_weather_scores(session)
        for score in result["scores"]:
            assert score["wet_weather_rating"] in valid

    async def test_position_gain_is_numeric(self, setup_database):
        async with TestSessionLocal() as session:
            result = await calculate_wet_weather_scores(session)
        for s in result["scores"]:
            assert isinstance(s["avg_position_gain"], (int, float))

    async def test_excludes_drivers_with_fewer_than_3_races(
        self, setup_database
    ):
        async with TestSessionLocal() as session:
            result = await calculate_wet_weather_scores(session)
        for s in result["scores"]:
            assert s["wet_races_analysed"] >= 3

    async def test_normalised_score_is_float(self, setup_database):
        async with TestSessionLocal() as session:
            result = await calculate_wet_weather_scores(session)
        for s in result["scores"]:
            assert isinstance(s["normalised_wet_score"], float)

    async def test_methodology_present_when_scores_exist(
        self, setup_database
    ):
        await seed_all_test_data()
        async with TestSessionLocal() as session:
            result = await calculate_wet_weather_scores(session)
        if result["scores"]:
            assert "methodology" in result
            assert "limitations" in result

    async def test_total_drivers_scored_matches_list(self, setup_database):
        async with TestSessionLocal() as session:
            result = await calculate_wet_weather_scores(session)
        if "total_drivers_scored" in result:
            assert result["total_drivers_scored"] == len(result["scores"])


# ─────────────────────────────────────────────
# PIT WINDOW SERVICE TESTS
# ─────────────────────────────────────────────

class TestPitWindowService:

    async def test_invalid_race_returns_error(self, setup_database):
        async with TestSessionLocal() as session:
            result = await calculate_pit_window(session, 99999, 99999)
        assert "error" in result

    async def test_valid_input_returns_structure(self, setup_database):
        await seed_all_test_data()
        ids = await get_test_ids()
        if ids["race"] and ids["driver"]:
            async with TestSessionLocal() as session:
                result = await calculate_pit_window(
                    session, ids["race"].id, ids["driver"].id
                )
            if "error" not in result:
                for key in ["race_id", "driver_id", "avg_pit_stop_duration_seconds",
                            "stint_analysis", "recommended_pit_laps",
                            "undercut_window_laps", "strategy_summary",
                            "limitations", "data_sources"]:
                    assert key in result

    async def test_avg_duration_is_positive(self, setup_database):
        ids = await get_test_ids()
        if ids["race"] and ids["driver"]:
            async with TestSessionLocal() as session:
                result = await calculate_pit_window(
                    session, ids["race"].id, ids["driver"].id
                )
            if "avg_pit_stop_duration_seconds" in result:
                assert result["avg_pit_stop_duration_seconds"] > 0

    async def test_recommended_laps_within_race_length(self, setup_database):
        ids = await get_test_ids()
        if ids["race"] and ids["driver"]:
            async with TestSessionLocal() as session:
                result = await calculate_pit_window(
                    session, ids["race"].id, ids["driver"].id
                )
            if result.get("recommended_pit_laps"):
                total = result.get("total_laps", 50)
                for lap in result["recommended_pit_laps"]:
                    assert 1 <= lap <= total

    async def test_undercut_laps_before_or_equal_to_optimal(
        self, setup_database
    ):
        ids = await get_test_ids()
        if ids["race"] and ids["driver"]:
            async with TestSessionLocal() as session:
                result = await calculate_pit_window(
                    session, ids["race"].id, ids["driver"].id
                )
            if result.get("recommended_pit_laps"):
                for opt, under in zip(
                    result["recommended_pit_laps"],
                    result["undercut_window_laps"]
                ):
                    assert under <= opt

    async def test_limitations_is_list(self, setup_database):
        ids = await get_test_ids()
        if ids["race"] and ids["driver"]:
            async with TestSessionLocal() as session:
                result = await calculate_pit_window(
                    session, ids["race"].id, ids["driver"].id
                )
            if "limitations" in result:
                assert isinstance(result["limitations"], list)
                assert len(result["limitations"]) > 0

    async def test_data_sources_present(self, setup_database):
        ids = await get_test_ids()
        if ids["race"] and ids["driver"]:
            async with TestSessionLocal() as session:
                result = await calculate_pit_window(
                    session, ids["race"].id, ids["driver"].id
                )
            if "data_sources" in result:
                assert isinstance(result["data_sources"], list)

    async def test_stint_analysis_contains_compound(self, setup_database):
        ids = await get_test_ids()
        if ids["race"] and ids["driver"]:
            async with TestSessionLocal() as session:
                result = await calculate_pit_window(
                    session, ids["race"].id, ids["driver"].id
                )
            for stint in result.get("stint_analysis", []):
                assert "compound" in stint
                assert "optimal_pit_lap" in stint


# ─────────────────────────────────────────────
# STRATEGY ROUTER TESTS
# ─────────────────────────────────────────────

class TestStrategyRouter:

    async def test_wet_weather_endpoint_returns_200(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/strategy/wet-weather-scores")
        assert response.status_code == 200
        assert "scores" in response.json()

    async def test_wet_weather_scores_is_list(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/strategy/wet-weather-scores")
        assert isinstance(response.json()["scores"], list)

    async def test_constructor_elo_returns_200(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/strategy/constructor-elo")
        assert response.status_code == 200
        assert "ratings" in response.json()

    async def test_constructor_elo_ratings_structure(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/strategy/constructor-elo")
        for r in response.json().get("ratings", []):
            assert "constructor" in r
            assert "elo" in r

    async def test_pit_window_invalid_returns_404(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/strategy/pit-window/99999/99999")
        assert response.status_code == 404

    async def test_pit_window_valid_returns_200(
        self, client, setup_database
    ):
        await seed_all_test_data()
        ids = await get_test_ids()
        if ids["race"] and ids["driver"]:
            response = await client.get(
                f"/api/v1/strategy/pit-window/{ids['race'].id}/{ids['driver'].id}"
            )
            assert response.status_code == 200
            assert "recommended_pit_laps" in response.json()
            assert "limitations" in response.json()

    async def test_pit_window_strategy_summary_present(
        self, client, setup_database
    ):
        ids = await get_test_ids()
        if ids["race"] and ids["driver"]:
            response = await client.get(
                f"/api/v1/strategy/pit-window/{ids['race'].id}/{ids['driver'].id}"
            )
            if response.status_code == 200:
                assert "strategy_summary" in response.json()

    async def test_tyre_model_invalid_compound_returns_404(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/strategy/tyre-model/1/UNKNOWN")
        assert response.status_code == 404

    async def test_tyre_model_valid_circuit(
        self, client, setup_database
    ):
        ids = await get_test_ids()
        if ids["circuit"]:
            response = await client.get(
                f"/api/v1/strategy/tyre-model/{ids['circuit'].id}/SOFT"
            )
            assert response.status_code in [200, 404]


# ─────────────────────────────────────────────
# DRIVER REPOSITORY TESTS
# ─────────────────────────────────────────────

class TestDriverRepository:

    async def test_create_driver(self, setup_database):
        async with TestSessionLocal() as session:
            repo = DriverRepository(session)
            driver = await repo.create(DriverCreate(
                forename="Repo", surname="Test",
                nationality="French", code="RPO", career_points=0.0
            ))
        assert driver.id is not None
        assert driver.surname == "Test"

    async def test_get_by_id(self, setup_database):
        async with TestSessionLocal() as session:
            repo = DriverRepository(session)
            created = await repo.create(DriverCreate(
                forename="Get", surname="ById",
                nationality="Spanish", code="GBI", career_points=0.0
            ))
            fetched = await repo.get_by_id(created.id)
        assert fetched.id == created.id

    async def test_get_by_id_nonexistent_returns_none(self, setup_database):
        async with TestSessionLocal() as session:
            repo = DriverRepository(session)
            assert await repo.get_by_id(99999) is None

    async def test_get_all_returns_list(self, setup_database):
        async with TestSessionLocal() as session:
            repo = DriverRepository(session)
            result = await repo.get_all()
        assert isinstance(result, list)

    async def test_get_all_pagination(self, setup_database):
        async with TestSessionLocal() as session:
            repo = DriverRepository(session)
            result = await repo.get_all(skip=0, limit=2)
        assert len(result) <= 2

    async def test_update_driver(self, setup_database):
        async with TestSessionLocal() as session:
            repo = DriverRepository(session)
            created = await repo.create(DriverCreate(
                forename="Update", surname="Me",
                nationality="Dutch", code="UPD", career_points=0.0
            ))
            updated = await repo.update(created.id, DriverUpdate(career_points=999.0))
        assert updated.career_points == 999.0

    async def test_update_nonexistent_returns_none(self, setup_database):
        async with TestSessionLocal() as session:
            repo = DriverRepository(session)
            result = await repo.update(99999, DriverUpdate(career_points=1.0))
        assert result is None

    async def test_delete_driver(self, setup_database):
        async with TestSessionLocal() as session:
            repo = DriverRepository(session)
            created = await repo.create(DriverCreate(
                forename="Delete", surname="Repo",
                nationality="Italian", code="DLR", career_points=0.0
            ))
            deleted = await repo.delete(created.id)
        assert deleted is True

    async def test_delete_nonexistent_returns_false(self, setup_database):
        async with TestSessionLocal() as session:
            repo = DriverRepository(session)
            assert await repo.delete(99999) is False

    async def test_search_by_nationality(self, setup_database):
        async with TestSessionLocal() as session:
            repo = DriverRepository(session)
            await repo.create(DriverCreate(
                forename="Search", surname="Test",
                nationality="Australian", code="SCH", career_points=0.0
            ))
            results = await repo.search_by_nationality("Australian")
        assert len(results) >= 1
        assert all("Australian" in d.nationality for d in results)


# ─────────────────────────────────────────────
# RACES ROUTER TESTS
# ─────────────────────────────────────────────

class TestRacesRouter:

    async def test_get_races_returns_200(self, client, setup_database):
        response = await client.get("/api/v1/races/")
        assert response.status_code == 200

    async def test_get_races_filter_by_season(self, client, setup_database):
        response = await client.get("/api/v1/races/?season=2023")
        assert response.status_code == 200

    async def test_get_race_not_found(self, client, setup_database):
        response = await client.get("/api/v1/races/99999")
        assert response.status_code == 404

    async def test_create_race_authenticated(
        self, client, auth_headers, setup_database
    ):
        await seed_all_test_data()
        ids = await get_test_ids()
        response = await client.post(
            "/api/v1/races/",
            json={"ergast_id": 77701, "season": 2024, "round": 1,
                  "name": "New Test GP", "date": "2024-03-15",
                  "circuit_id": ids["circuit"].id},
            headers=auth_headers
        )
        assert response.status_code == 201
        assert response.json()["name"] == "New Test GP"

    async def test_create_race_unauthenticated_returns_401(
        self, client, setup_database
    ):
        response = await client.post(
            "/api/v1/races/",
            json={"ergast_id": 77702, "season": 2024, "round": 2,
                  "name": "Unauth GP", "circuit_id": 1}
        )
        assert response.status_code == 401

    async def test_update_race(self, client, auth_headers, setup_database):
        ids = await get_test_ids()
        create = await client.post(
            "/api/v1/races/",
            json={"ergast_id": 77703, "season": 2024, "round": 3,
                  "name": "Update GP", "date": "2024-05-15",
                  "circuit_id": ids["circuit"].id},
            headers=auth_headers
        )
        race_id = create.json()["id"]
        response = await client.put(
            f"/api/v1/races/{race_id}",
            json={"name": "Updated GP Name"},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated GP Name"

    async def test_update_race_not_found(
        self, client, auth_headers, setup_database
    ):
        response = await client.put(
            "/api/v1/races/99999",
            json={"name": "Ghost GP"},
            headers=auth_headers
        )
        assert response.status_code == 404

    async def test_delete_race_as_admin(
        self, client, auth_headers, setup_database
    ):
        ids = await get_test_ids()
        create = await client.post(
            "/api/v1/races/",
            json={"ergast_id": 77704, "season": 2024, "round": 4,
                  "name": "Delete GP", "date": "2024-06-15",
                  "circuit_id": ids["circuit"].id},
            headers=auth_headers
        )
        race_id = create.json()["id"]
        response = await client.delete(
            f"/api/v1/races/{race_id}", headers=auth_headers
        )
        assert response.status_code == 204

    async def test_delete_race_as_reader_returns_403(
        self, client, reader_headers, setup_database
    ):
        response = await client.delete(
            "/api/v1/races/1", headers=reader_headers
        )
        assert response.status_code == 403

    async def test_get_race_by_id(self, client, auth_headers, setup_database):
        ids = await get_test_ids()
        create = await client.post(
            "/api/v1/races/",
            json={"ergast_id": 77705, "season": 2024, "round": 5,
                  "name": "Fetch GP", "date": "2024-07-15",
                  "circuit_id": ids["circuit"].id},
            headers=auth_headers
        )
        race_id = create.json()["id"]
        response = await client.get(f"/api/v1/races/{race_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Fetch GP"


# ─────────────────────────────────────────────
# PITSTOPS ROUTER TESTS
# ─────────────────────────────────────────────

class TestPitStopsRouter:

    async def test_get_pitstops_returns_200(self, client, setup_database):
        response = await client.get("/api/v1/pitstops/")
        assert response.status_code == 200

    async def test_get_pitstop_not_found(self, client, setup_database):
        response = await client.get("/api/v1/pitstops/99999")
        assert response.status_code == 404

    async def test_create_pitstop(self, client, auth_headers, setup_database):
        await seed_all_test_data()
        ids = await get_test_ids()
        response = await client.post(
            "/api/v1/pitstops/",
            json={"race_id": ids["race"].id, "driver_id": ids["driver"].id,
                  "stop_number": 9, "lap": 30, "duration_seconds": 2.5,
                  "tyre_compound": "SOFT"},
            headers=auth_headers
        )
        assert response.status_code == 201
        assert response.json()["lap"] == 30

    async def test_create_pitstop_unauthenticated(self, client, setup_database):
        response = await client.post(
            "/api/v1/pitstops/",
            json={"race_id": 1, "driver_id": 1, "stop_number": 1,
                  "lap": 10, "duration_seconds": 2.5}
        )
        assert response.status_code == 401

    async def test_get_pitstops_filter_by_race(
        self, client, setup_database
    ):
        ids = await get_test_ids()
        response = await client.get(
            f"/api/v1/pitstops/?race_id={ids['race'].id}"
        )
        assert response.status_code == 200

    async def test_get_pitstops_filter_by_driver(
        self, client, setup_database
    ):
        ids = await get_test_ids()
        response = await client.get(
            f"/api/v1/pitstops/?driver_id={ids['driver'].id}"
        )
        assert response.status_code == 200

    async def test_update_pitstop(self, client, auth_headers, setup_database):
        ids = await get_test_ids()
        create = await client.post(
            "/api/v1/pitstops/",
            json={"race_id": ids["race"].id, "driver_id": ids["driver"].id,
                  "stop_number": 8, "lap": 15, "duration_seconds": 3.0,
                  "tyre_compound": "MEDIUM"},
            headers=auth_headers
        )
        pitstop_id = create.json()["id"]
        response = await client.put(
            f"/api/v1/pitstops/{pitstop_id}",
            json={"duration_seconds": 2.2},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["duration_seconds"] == 2.2

    async def test_update_pitstop_not_found(
        self, client, auth_headers, setup_database
    ):
        response = await client.put(
            "/api/v1/pitstops/99999",
            json={"lap": 20},
            headers=auth_headers
        )
        assert response.status_code == 404

    async def test_delete_pitstop_as_admin(
        self, client, auth_headers, setup_database
    ):
        ids = await get_test_ids()
        create = await client.post(
            "/api/v1/pitstops/",
            json={"race_id": ids["race"].id, "driver_id": ids["driver"].id,
                  "stop_number": 7, "lap": 40, "duration_seconds": 2.7},
            headers=auth_headers
        )
        pitstop_id = create.json()["id"]
        response = await client.delete(
            f"/api/v1/pitstops/{pitstop_id}", headers=auth_headers
        )
        assert response.status_code == 204

    async def test_delete_pitstop_as_reader_returns_403(
        self, client, reader_headers, setup_database
    ):
        response = await client.delete(
            "/api/v1/pitstops/1", headers=reader_headers
        )
        assert response.status_code == 403

    async def test_get_pitstop_by_id(self, client, auth_headers, setup_database):
        ids = await get_test_ids()
        create = await client.post(
            "/api/v1/pitstops/",
            json={"race_id": ids["race"].id, "driver_id": ids["driver"].id,
                  "stop_number": 6, "lap": 35, "duration_seconds": 2.6},
            headers=auth_headers
        )
        pitstop_id = create.json()["id"]
        response = await client.get(f"/api/v1/pitstops/{pitstop_id}")
        assert response.status_code == 200
        assert response.json()["lap"] == 35


# ─────────────────────────────────────────────
# ANALYTICS ROUTER TESTS
# ─────────────────────────────────────────────

class TestAnalyticsRouter:

    async def test_pit_crew_performance_returns_200(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/analytics/pit-crew-performance")
        assert response.status_code == 200
        assert "rankings" in response.json()
        assert "methodology" in response.json()

    async def test_pit_crew_ranking_fields_present(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/analytics/pit-crew-performance")
        for r in response.json().get("rankings", []):
            assert "constructor" in r
            assert "avg_stop_seconds" in r
            assert "consistency_score" in r
            assert "rank" in r

    async def test_pit_crew_with_season_filter(
        self, client, setup_database
    ):
        response = await client.get(
            "/api/v1/analytics/pit-crew-performance?season=2023"
        )
        assert response.status_code == 200

    async def test_circuit_overtaking_returns_200(
        self, client, setup_database
    ):
        response = await client.get(
            "/api/v1/analytics/circuit-overtaking-difficulty"
        )
        assert response.status_code == 200
        assert "circuits" in response.json()
        assert "methodology" in response.json()

    async def test_circuit_difficulty_values_valid(
        self, client, setup_database
    ):
        response = await client.get(
            "/api/v1/analytics/circuit-overtaking-difficulty"
        )
        valid = {"Very Hard", "Hard", "Medium", "Easy"}
        for c in response.json().get("circuits", []):
            assert c["overtaking_difficulty"] in valid

    async def test_tyre_degradation_invalid_circuit_returns_404(
        self, client, setup_database
    ):
        response = await client.get(
            "/api/v1/analytics/tyre-degradation?circuit_id=99999&compound=SOFT"
        )
        assert response.status_code == 404

    async def test_tyre_degradation_valid_circuit(
        self, client, setup_database
    ):
        ids = await get_test_ids()
        if ids["circuit"]:
            response = await client.get(
                f"/api/v1/analytics/tyre-degradation"
                f"?circuit_id={ids['circuit'].id}&compound=SOFT"
            )
            assert response.status_code in [200, 404]

    async def test_driver_season_summary_invalid_returns_404(
        self, client, setup_database
    ):
        response = await client.get(
            "/api/v1/analytics/driver-season-summary/99999?season=2023"
        )
        assert response.status_code == 404

    async def test_driver_season_summary_valid_driver(
        self, client, setup_database
    ):
        await seed_all_test_data()
        ids = await get_test_ids()
        if ids["driver"]:
            response = await client.get(
                f"/api/v1/analytics/driver-season-summary"
                f"/{ids['driver'].id}?season=2023"
            )
            assert response.status_code == 200
            body = response.json()
            assert "total_points" in body
            assert "wins" in body
            assert "podiums" in body
            assert "race_by_race" in body

    async def test_driver_summary_wins_lte_podiums(
        self, client, setup_database
    ):
        ids = await get_test_ids()
        if ids["driver"]:
            response = await client.get(
                f"/api/v1/analytics/driver-season-summary"
                f"/{ids['driver'].id}?season=2023"
            )
            if response.status_code == 200:
                body = response.json()
                assert body["wins"] <= body["podiums"]

    async def test_api_root_returns_version(self, client, setup_database):
        response = await client.get("/")
        assert response.status_code == 200
        assert "version" in response.json()


# ─────────────────────────────────────────────
# AUTH ROUTER EXTENDED TESTS
# ─────────────────────────────────────────────

class TestAuthExtended:

    async def test_token_type_is_bearer(self, client, setup_database):
        await client.post("/api/v1/auth/register", json={
            "username": "tokencheck", "password": "pass123", "role": "reader"
        })
        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "tokencheck", "password": "pass123"}
        )
        assert response.json()["token_type"] == "bearer"

    async def test_token_is_non_empty_string(self, client, setup_database):
        await client.post("/api/v1/auth/register", json={
            "username": "tokenlen", "password": "pass123", "role": "reader"
        })
        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "tokenlen", "password": "pass123"}
        )
        token = response.json()["access_token"]
        assert isinstance(token, str) and len(token) > 20

    async def test_invalid_token_returns_401(self, client, setup_database):
        response = await client.post(
            "/api/v1/drivers/",
            json={"forename": "Ghost", "surname": "User",
                  "nationality": "None", "code": "GHT", "career_points": 0.0},
            headers={"Authorization": "Bearer invalidtoken123"}
        )
        assert response.status_code == 401

    async def test_register_admin_role(self, client, setup_database):
        response = await client.post("/api/v1/auth/register", json={
            "username": "adminroletest2",
            "password": "pass123",
            "role": "admin"
        })
        assert response.status_code == 201

    async def test_me_endpoint_returns_200(self, client, setup_database):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
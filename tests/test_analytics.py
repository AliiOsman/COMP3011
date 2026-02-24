import pytest

class TestAnalyticsEndpoints:

    async def test_pit_crew_performance_returns_200(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/analytics/pit-crew-performance")
        assert response.status_code == 200
        data = response.json()
        assert "rankings" in data
        assert "methodology" in data

    async def test_circuit_overtaking_returns_200(
        self, client, setup_database
    ):
        response = await client.get(
            "/api/v1/analytics/circuit-overtaking-difficulty"
        )
        assert response.status_code == 200
        data = response.json()
        assert "circuits" in data
        assert "methodology" in data

    async def test_tyre_degradation_invalid_circuit_returns_404(
        self, client, setup_database
    ):
        response = await client.get(
            "/api/v1/analytics/tyre-degradation?circuit_id=99999&compound=SOFT"
        )
        assert response.status_code == 404

    async def test_driver_season_summary_invalid_driver_returns_404(
        self, client, setup_database
    ):
        response = await client.get(
            "/api/v1/analytics/driver-season-summary/99999?season=2023"
        )
        assert response.status_code == 404

    async def test_pit_crew_performance_with_season_filter(
        self, client, setup_database
    ):
        response = await client.get(
            "/api/v1/analytics/pit-crew-performance?season=2023"
        )
        assert response.status_code == 200

    async def test_races_filter_by_season(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/races/?season=2023")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_api_root_returns_200(self, client, setup_database):
        response = await client.get("/")
        assert response.status_code == 200
        assert "version" in response.json()
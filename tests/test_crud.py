import pytest

class TestDriverCRUD:

    async def test_create_driver_authenticated_returns_201(
        self, client, auth_headers, setup_database
    ):
        response = await client.post(
            "/api/v1/drivers/",
            json={
                "forename": "Max",
                "surname": "Verstappen",
                "nationality": "Dutch",
                "code": "VER",
                "career_points": 2586.5
            },
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["surname"] == "Verstappen"
        assert data["code"] == "VER"
        assert "id" in data

    async def test_create_driver_unauthenticated_returns_401(
        self, client, setup_database
    ):
        response = await client.post(
            "/api/v1/drivers/",
            json={
                "forename": "Charles",
                "surname": "Leclerc",
                "nationality": "Monegasque",
                "code": "LEC",
                "career_points": 1051.0
            }
        )
        assert response.status_code == 401

    async def test_get_driver_by_id_returns_correct_driver(
        self, client, sample_driver, setup_database
    ):
        driver_id = sample_driver["id"]
        response = await client.get(f"/api/v1/drivers/{driver_id}")
        assert response.status_code == 200
        assert response.json()["surname"] == "Hamilton"

    async def test_get_nonexistent_driver_returns_404(
        self, client, setup_database
    ):
        response = await client.get("/api/v1/drivers/99999")
        assert response.status_code == 404

    async def test_get_all_drivers_returns_list(
        self, client, sample_driver, setup_database
    ):
        response = await client.get("/api/v1/drivers/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    async def test_update_driver_returns_updated_data(
        self, client, sample_driver, auth_headers, setup_database
    ):
        driver_id = sample_driver["id"]
        response = await client.put(
            f"/api/v1/drivers/{driver_id}",
            json={"career_points": 5000.0},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["career_points"] == 5000.0

    async def test_delete_driver_as_admin_returns_204(
        self, client, auth_headers, setup_database
    ):
        create = await client.post(
            "/api/v1/drivers/",
            json={
                "forename": "Delete",
                "surname": "Me",
                "nationality": "British",
                "code": "DEL",
                "career_points": 0.0
            },
            headers=auth_headers
        )
        driver_id = create.json()["id"]
        response = await client.delete(
            f"/api/v1/drivers/{driver_id}",
            headers=auth_headers
        )
        assert response.status_code == 204

    async def test_delete_driver_as_reader_returns_403(
        self, client, sample_driver, reader_headers, setup_database
    ):
        driver_id = sample_driver["id"]
        response = await client.delete(
            f"/api/v1/drivers/{driver_id}",
            headers=reader_headers
        )
        assert response.status_code == 403

    async def test_create_driver_empty_name_returns_422(
        self, client, auth_headers, setup_database
    ):
        response = await client.post(
            "/api/v1/drivers/",
            json={
                "forename": "",
                "surname": "Test",
                "nationality": "British",
                "code": "TST",
                "career_points": 0.0
            },
            headers=auth_headers
        )
        assert response.status_code == 422

    async def test_search_drivers_by_nationality(
        self, client, sample_driver, setup_database
    ):
        response = await client.get(
            "/api/v1/drivers/search?nationality=British"
        )
        assert response.status_code == 200
        results = response.json()
        assert all("British" in d["nationality"] for d in results)
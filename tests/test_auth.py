import pytest

class TestAuthentication:

    async def test_register_new_user_returns_201(self, client, setup_database):
        response = await client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "password": "password123",
            "role": "reader"
        })
        assert response.status_code == 201

    async def test_register_duplicate_username_returns_400(self, client, setup_database):
        await client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "password123",
            "role": "reader"
        })
        response = await client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "password123",
            "role": "reader"
        })
        assert response.status_code == 400

    async def test_login_valid_credentials_returns_token(self, client, setup_database):
        await client.post("/api/v1/auth/register", json={
            "username": "loginuser",
            "password": "password123",
            "role": "reader"
        })
        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "loginuser", "password": "password123"}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["token_type"] == "bearer"

    async def test_login_wrong_password_returns_401(self, client, setup_database):
        await client.post("/api/v1/auth/register", json={
            "username": "wrongpass",
            "password": "correct123",
            "role": "reader"
        })
        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "wrongpass", "password": "wrongpassword"}
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user_returns_401(self, client, setup_database):
        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "ghost", "password": "doesntexist"}
        )
        assert response.status_code == 401
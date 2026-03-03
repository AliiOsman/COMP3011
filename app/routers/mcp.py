from fastapi import APIRouter

router = APIRouter()

@router.get("/manifest")
async def get_mcp_manifest():
    """
    MCP-compatible tool manifest for AI agent integration.
    Describes available tools and their schemas for use with
    Claude, GPT, and other MCP-compatible AI assistants.
    """
    return {
        "schema_version": "1.0",
        "name": "f1-strategy-intelligence",
        "description": (
            "Formula 1 race strategy intelligence API. Provides pit window "
            "optimization, constructor Elo ratings, wet weather driver scoring, "
            "tyre degradation models, and comprehensive F1 analytics."
        ),
        "tools": [
            {
                "name": "get_optimal_pit_window",
                "description": (
                    "Calculate the optimal pit stop window for a driver in a specific race. "
                    "Returns recommended pit laps, undercut windows, and stint analysis "
                    "based on tyre compound degradation models and historical pit data."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "race_id": {
                            "type": "integer",
                            "description": "The database ID of the race"
                        },
                        "driver_id": {
                            "type": "integer",
                            "description": "The database ID of the driver"
                        }
                    },
                    "required": ["race_id", "driver_id"]
                },
                "endpoint": "/api/v1/strategy/pit-window/{race_id}/{driver_id}",
                "method": "GET"
            },
            {
                "name": "get_constructor_elo_ratings",
                "description": (
                    "Get current Elo ratings for all F1 constructors based on "
                    "historical race results. Higher Elo indicates stronger "
                    "historical performance."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {}
                },
                "endpoint": "/api/v1/strategy/constructor-elo",
                "method": "GET"
            },
            {
                "name": "get_wet_weather_scores",
                "description": (
                    "Score all F1 drivers on wet weather performance. "
                    "Uses position delta analysis normalised for grid position "
                    "to identify drivers who genuinely excel in rain."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {}
                },
                "endpoint": "/api/v1/strategy/wet-weather-scores",
                "method": "GET"
            },
            {
                "name": "get_tyre_degradation_model",
                "description": (
                    "Get a quadratic regression model for tyre degradation "
                    "at a specific circuit for a given compound. Returns "
                    "degradation curve and model coefficients."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "circuit_id": {
                            "type": "integer",
                            "description": "The database ID of the circuit"
                        },
                        "compound": {
                            "type": "string",
                            "description": "Tyre compound: SOFT, MEDIUM, or HARD",
                            "enum": ["SOFT", "MEDIUM", "HARD"]
                        }
                    },
                    "required": ["circuit_id", "compound"]
                },
                "endpoint": "/api/v1/strategy/tyre-model/{circuit_id}/{compound}",
                "method": "GET"
            },
            {
                "name": "get_driver_season_summary",
                "description": (
                    "Get a complete season performance summary for a driver "
                    "including wins, podiums, DNFs, points and race-by-race breakdown."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "driver_id": {
                            "type": "integer",
                            "description": "The database ID of the driver"
                        },
                        "season": {
                            "type": "integer",
                            "description": "The season year e.g. 2023"
                        }
                    },
                    "required": ["driver_id", "season"]
                },
                "endpoint": "/api/v1/analytics/driver-season-summary/{driver_id}",
                "method": "GET"
            },
            {
                "name": "get_circuit_overtaking_difficulty",
                "description": (
                    "Score all circuits by overtaking difficulty using mean "
                    "position change between qualifying and race finish."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {}
                },
                "endpoint": "/api/v1/analytics/circuit-overtaking-difficulty",
                "method": "GET"
            },
            {
                "name": "get_pit_crew_performance",
                "description": (
                    "Rank constructors by pit crew execution speed and consistency. "
                    "Optionally filter by season."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "season": {
                            "type": "integer",
                            "description": "Optional season filter e.g. 2023"
                        }
                    }
                },
                "endpoint": "/api/v1/analytics/pit-crew-performance",
                "method": "GET"
            },
            {
                "name": "search_drivers",
                "description": "Search for F1 drivers by nationality.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "nationality": {
                            "type": "string",
                            "description": "Driver nationality e.g. British, Dutch, Spanish"
                        }
                    },
                    "required": ["nationality"]
                },
                "endpoint": "/api/v1/drivers/search",
                "method": "GET"
            }
        ]
    }


@router.get("/health")
async def mcp_health():
    """Health check endpoint for MCP agent polling"""
    return {
        "status": "healthy",
        "service": "f1-strategy-intelligence",
        "version": "1.0.0",
        "mcp_compatible": True
    }
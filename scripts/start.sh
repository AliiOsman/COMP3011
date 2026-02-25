#!/bin/bash
echo "Starting F1 Strategy API..."
uvicorn app.main:app --host 0.0.0.0 --port $PORT
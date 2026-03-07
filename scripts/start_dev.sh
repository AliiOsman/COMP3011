#!/bin/bash
sudo service postgresql start
source venv/bin/activate
ollama serve &
uvicorn app.main:app --reload
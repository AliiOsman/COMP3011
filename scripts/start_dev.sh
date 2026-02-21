#!/bin/bash
sudo service postgresql start
source venv/bin/activate
uvicorn app.main:app --reload
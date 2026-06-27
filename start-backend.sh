#!/bin/bash
cd backend
source .venv/bin/activate
python main.py
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

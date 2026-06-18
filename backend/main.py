"""
main.py — FastAPI entry point for the RevFit recommender system.

Run with:
    uvicorn main:app --reload

Swagger UI: http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import users, workouts, meals, feedback, meal_plan, pose
from pose_analysis import POSE_OUTPUT_DIR

app = FastAPI(
    title="RevFit API",
    description="Fitness & nutrition recommendation engine",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router,     prefix="/users",     tags=["Users"])
app.include_router(workouts.router,  prefix="/workouts",  tags=["Workouts"])
app.include_router(meals.router,     prefix="/meals",     tags=["Meals"])
app.include_router(meal_plan.router, prefix="/meal-plan", tags=["Meal Plan"])
app.include_router(feedback.router,  prefix="/feedback",  tags=["Feedback"])
app.include_router(pose.router,      prefix="/pose",      tags=["Pose Analysis"])

# Serve annotated correction videos as static files
app.mount("/pose-outputs", StaticFiles(directory=POSE_OUTPUT_DIR), name="pose-outputs")


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "RevFit API is running"}


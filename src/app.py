"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import re
from pathlib import Path

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Competitive soccer training and matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["lucas@mergington.edu"]
    },
    "Swimming Club": {
        "description": "Swim practice and competitive meets",
        "schedule": "Mondays and Wednesdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore painting, drawing, and mixed media techniques",
        "schedule": "Wednesdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["isabella@mergington.edu"]
    },
    "Drama Club": {
        "description": "Theater performance, acting, and stage production",
        "schedule": "Mondays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 20,
        "participants": ["mia@mergington.edu"]
    },
    "Math Olympiad": {
        "description": "Advanced math problem-solving and competition preparation",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ethan@mergington.edu"]
    },
    "Debate Team": {
        "description": "Public speaking, argumentation, and debate competitions",
        "schedule": "Tuesdays, 3:30 PM - 5:00 PM",
        "max_participants": 16,
        "participants": ["liam@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


# Day name mapping for schedule parsing
DAY_NAMES = {
    "mondays": "monday", "monday": "monday",
    "tuesdays": "tuesday", "tuesday": "tuesday",
    "wednesdays": "wednesday", "wednesday": "wednesday",
    "thursdays": "thursday", "thursday": "thursday",
    "fridays": "friday", "friday": "friday",
}


def parse_time_to_minutes(time_str):
    """Convert a time string like '3:30 PM' to minutes since midnight."""
    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", time_str.strip(), re.IGNORECASE)
    if not match:
        return 0
    hours, minutes, period = int(match.group(1)), int(match.group(2)), match.group(3).upper()
    if period == "PM" and hours != 12:
        hours += 12
    elif period == "AM" and hours == 12:
        hours = 0
    return hours * 60 + minutes


def parse_schedule(schedule_str):
    """Parse a schedule string into a set of (day, start_minutes, end_minutes) tuples."""
    # Split into days part and time part at the last comma before the time range
    match = re.match(r"(.+),\s*(\d{1,2}:\d{2}\s*[AP]M\s*-\s*\d{1,2}:\d{2}\s*[AP]M)", schedule_str, re.IGNORECASE)
    if not match:
        return set()

    days_part = match.group(1)
    time_part = match.group(2)

    start_str, end_str = time_part.split("-")
    start = parse_time_to_minutes(start_str)
    end = parse_time_to_minutes(end_str)

    # Extract day names
    slots = set()
    for word in re.split(r"[,\s]+", days_part.lower()):
        word = word.strip()
        if word in DAY_NAMES:
            slots.add((DAY_NAMES[word], start, end))

    return slots


def find_schedule_conflict(email, target_activity_name):
    """Check if a student has a schedule conflict with the target activity."""
    target_slots = parse_schedule(activities[target_activity_name]["schedule"])
    if not target_slots:
        return None

    for name, details in activities.items():
        if name == target_activity_name:
            continue
        if email not in details["participants"]:
            continue

        existing_slots = parse_schedule(details["schedule"])
        for t_day, t_start, t_end in target_slots:
            for e_day, e_start, e_end in existing_slots:
                if t_day == e_day and t_start < e_end and e_start < t_end:
                    return name
    return None


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]
    
    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(status_code=400, detail="Student already signed up for this activity")

    # Check for schedule conflicts with other enrolled activities
    conflicting = find_schedule_conflict(email, activity_name)
    if conflicting:
        raise HTTPException(
            status_code=409,
            detail=f"Schedule conflict with {conflicting}"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/signup")
def unregister_from_activity(activity_name: str, email: str):
    """Remove a student from an activity"""
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    activity = activities[activity_name]

    if email not in activity["participants"]:
        raise HTTPException(status_code=404, detail="Student not found in this activity")

    activity["participants"].remove(email)
    return {"message": f"Removed {email} from {activity_name}"}

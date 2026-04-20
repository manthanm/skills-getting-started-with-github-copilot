import copy
import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset the in-memory activities database before each test."""
    original = copy.deepcopy(activities)
    yield
    activities.clear()
    activities.update(original)


# ---- GET / (root redirect) ----


def test_root_redirects_to_index(client):
    # Arrange — nothing to set up

    # Act
    response = client.get("/", follow_redirects=False)

    # Assert
    assert response.status_code == 307
    assert "/static/index.html" in response.headers["location"]


# ---- GET /activities (happy path) ----


def test_get_activities_returns_all(client):
    # Arrange
    expected_keys = {
        "Chess Club", "Programming Class", "Gym Class",
        "Soccer Team", "Swimming Club", "Art Club",
        "Drama Club", "Math Olympiad", "Debate Team",
    }

    # Act
    response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == expected_keys


def test_get_activities_structure(client):
    # Arrange
    required_fields = {"description", "schedule", "max_participants", "participants"}

    # Act
    response = client.get("/activities")
    data = response.json()

    # Assert
    for name, details in data.items():
        assert required_fields.issubset(details.keys()), f"{name} missing fields"


def test_get_activities_participants_is_list(client):
    # Arrange — nothing to set up

    # Act
    response = client.get("/activities")
    data = response.json()

    # Assert
    for name, details in data.items():
        assert isinstance(details["participants"], list), f"{name} participants is not a list"


# ---- POST /activities/{name}/signup (happy path) ----


def test_signup_success(client):
    # Arrange
    activity = "Chess Club"
    email = "new_student@mergington.edu"

    # Act
    response = client.post(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == f"Signed up {email} for {activity}"
    assert email in activities[activity]["participants"]


def test_signup_adds_to_correct_activity(client):
    # Arrange
    activity = "Chess Club"
    other_activity = "Gym Class"
    email = "new_student@mergington.edu"
    other_participants_before = list(activities[other_activity]["participants"])

    # Act
    client.post(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert email in activities[activity]["participants"]
    assert activities[other_activity]["participants"] == other_participants_before


def test_signup_increments_participant_count(client):
    # Arrange
    activity = "Chess Club"
    email = "new_student@mergington.edu"
    count_before = len(activities[activity]["participants"])

    # Act
    client.post(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert len(activities[activity]["participants"]) == count_before + 1


# ---- POST /activities/{name}/signup (error cases) ----


def test_signup_nonexistent_activity(client):
    # Arrange
    activity = "Nonexistent Club"
    email = "student@mergington.edu"

    # Act
    response = client.post(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_signup_duplicate_email(client):
    # Arrange
    activity = "Chess Club"
    email = "michael@mergington.edu"  # already a participant

    # Act
    response = client.post(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert response.status_code == 400
    assert response.json()["detail"] == "Student already signed up for this activity"


def test_signup_duplicate_after_fresh_signup(client):
    # Arrange
    activity = "Chess Club"
    email = "fresh_student@mergington.edu"
    client.post(f"/activities/{activity}/signup?email={email}")

    # Act
    response = client.post(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert response.status_code == 400
    assert response.json()["detail"] == "Student already signed up for this activity"


# ---- DELETE /activities/{name}/signup (happy path) ----


def test_unregister_success(client):
    # Arrange
    activity = "Chess Club"
    email = "michael@mergington.edu"  # existing participant

    # Act
    response = client.delete(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == f"Removed {email} from {activity}"
    assert email not in activities[activity]["participants"]


def test_unregister_decrements_participant_count(client):
    # Arrange
    activity = "Chess Club"
    email = "michael@mergington.edu"
    count_before = len(activities[activity]["participants"])

    # Act
    client.delete(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert len(activities[activity]["participants"]) == count_before - 1


def test_unregister_only_removes_target(client):
    # Arrange
    activity = "Chess Club"
    email = "michael@mergington.edu"
    other_email = "daniel@mergington.edu"

    # Act
    client.delete(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert email not in activities[activity]["participants"]
    assert other_email in activities[activity]["participants"]


# ---- DELETE /activities/{name}/signup (error cases) ----


def test_unregister_nonexistent_activity(client):
    # Arrange
    activity = "Nonexistent Club"
    email = "student@mergington.edu"

    # Act
    response = client.delete(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_unregister_email_not_in_activity(client):
    # Arrange
    activity = "Chess Club"
    email = "unknown@mergington.edu"

    # Act
    response = client.delete(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found in this activity"


def test_unregister_already_removed(client):
    # Arrange
    activity = "Chess Club"
    email = "michael@mergington.edu"
    client.delete(f"/activities/{activity}/signup?email={email}")

    # Act
    response = client.delete(f"/activities/{activity}/signup?email={email}")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found in this activity"


# ---- Sequence / lifecycle tests ----


def test_full_lifecycle_signup_then_unregister(client):
    # Arrange
    activity = "Chess Club"
    email = "lifecycle@mergington.edu"

    # Act — signup
    signup_resp = client.post(f"/activities/{activity}/signup?email={email}")

    # Assert — signup succeeded and visible in GET
    assert signup_resp.status_code == 200
    get_resp = client.get("/activities")
    assert email in get_resp.json()[activity]["participants"]

    # Act — unregister
    unreg_resp = client.delete(f"/activities/{activity}/signup?email={email}")

    # Assert — unregister succeeded and no longer visible in GET
    assert unreg_resp.status_code == 200
    get_resp = client.get("/activities")
    assert email not in get_resp.json()[activity]["participants"]


def test_unregister_then_re_signup(client):
    # Arrange
    activity = "Chess Club"
    email = "michael@mergington.edu"  # existing participant

    # Act — unregister then re-signup
    unreg_resp = client.delete(f"/activities/{activity}/signup?email={email}")
    signup_resp = client.post(f"/activities/{activity}/signup?email={email}")

    # Assert — both succeed, email is back in participants
    assert unreg_resp.status_code == 200
    assert signup_resp.status_code == 200
    assert email in activities[activity]["participants"]


def test_signup_unregister_signup_again(client):
    # Arrange
    activity = "Chess Club"
    email = "cycle@mergington.edu"

    # Act — full signup → unregister → signup cycle
    first_signup = client.post(f"/activities/{activity}/signup?email={email}")
    unreg = client.delete(f"/activities/{activity}/signup?email={email}")
    second_signup = client.post(f"/activities/{activity}/signup?email={email}")

    # Assert — all three operations succeed, no duplicate error on re-signup
    assert first_signup.status_code == 200
    assert unreg.status_code == 200
    assert second_signup.status_code == 200
    assert email in activities[activity]["participants"]


# ---- Schedule conflict tests ----


def test_signup_conflict_partial_time_overlap(client):
    # Arrange — Programming Class: Tue/Thu 3:30-4:30, Soccer Team: Tue/Thu 4:00-5:30
    email = "emma@mergington.edu"  # already in Programming Class

    # Act
    response = client.post(f"/activities/Soccer Team/signup?email={email}")

    # Assert — 409 because Tue/Thu 4:00-4:30 overlaps
    assert response.status_code == 409
    assert "Schedule conflict" in response.json()["detail"]
    assert "Programming Class" in response.json()["detail"]


def test_signup_conflict_full_time_overlap(client):
    # Arrange — Swimming Club: Mon/Wed 3:30-5:00, Art Club: Wed 3:30-5:00
    email = "ava@mergington.edu"  # already in Swimming Club

    # Act
    response = client.post(f"/activities/Art Club/signup?email={email}")

    # Assert — 409 because Wed 3:30-5:00 fully overlaps
    assert response.status_code == 409
    assert "Schedule conflict" in response.json()["detail"]
    assert "Swimming Club" in response.json()["detail"]


def test_signup_conflict_mentions_conflicting_activity(client):
    # Arrange — Chess Club: Fri 3:30-5:00, Drama Club: Mon/Fri 3:30-5:00
    email = "michael@mergington.edu"  # already in Chess Club

    # Act
    response = client.post(f"/activities/Drama Club/signup?email={email}")

    # Assert — message names the blocking activity
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "Schedule conflict with Chess Club" in detail


def test_signup_no_conflict_different_days(client):
    # Arrange — Chess Club: Fri 3:30-5:00, Debate Team: Tue 3:30-5:00
    email = "michael@mergington.edu"  # already in Chess Club

    # Act
    response = client.post(f"/activities/Debate Team/signup?email={email}")

    # Assert — no conflict, different days
    assert response.status_code == 200
    assert email in activities["Debate Team"]["participants"]


def test_signup_no_conflict_same_day_no_time_overlap(client):
    # Arrange — Gym Class: Mon/Wed/Fri 2:00-3:00, Drama Club: Mon/Fri 3:30-5:00
    email = "john@mergington.edu"  # already in Gym Class

    # Act
    response = client.post(f"/activities/Drama Club/signup?email={email}")

    # Assert — same days but times don't overlap (3:00 ends before 3:30 starts)
    assert response.status_code == 200
    assert email in activities["Drama Club"]["participants"]


def test_signup_conflict_after_unregister_clears(client):
    # Arrange — emma in Programming Class (Tue/Thu 3:30-4:30), conflicts with Soccer Team (Tue/Thu 4:00-5:30)
    email = "emma@mergington.edu"

    # Confirm conflict exists
    conflict_resp = client.post(f"/activities/Soccer Team/signup?email={email}")
    assert conflict_resp.status_code == 409

    # Act — unregister from Programming Class, then retry Soccer Team
    client.delete(f"/activities/Programming Class/signup?email={email}")
    response = client.post(f"/activities/Soccer Team/signup?email={email}")

    # Assert — conflict is cleared, signup succeeds
    assert response.status_code == 200
    assert email in activities["Soccer Team"]["participants"]


def test_signup_conflict_multiple_activities(client):
    # Arrange — enroll student in two activities, then try a third that conflicts with one
    email = "multi@mergington.edu"
    # Sign up for Chess Club (Fri 3:30-5:00) — no conflicts
    resp1 = client.post(f"/activities/Chess Club/signup?email={email}")
    assert resp1.status_code == 200
    # Sign up for Debate Team (Tue 3:30-5:00) — no conflict with Chess Club
    resp2 = client.post(f"/activities/Debate Team/signup?email={email}")
    assert resp2.status_code == 200

    # Act — try Programming Class (Tue/Thu 3:30-4:30) which conflicts with Debate Team on Tue
    response = client.post(f"/activities/Programming Class/signup?email={email}")

    # Assert — 409 due to Debate Team conflict
    assert response.status_code == 409
    assert "Schedule conflict with Debate Team" in response.json()["detail"]

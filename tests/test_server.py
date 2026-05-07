import time
import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient

# load server module from src/deploy/server.py
repo_root = Path(__file__).resolve().parents[1]
server_path = repo_root / "src" / "deploy" / "server.py"
spec = importlib.util.spec_from_file_location("server_mod", str(server_path))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
app = server.app

client = TestClient(app)


def test_cars_endpoint():
    r = client.get("/api/cars")
    assert r.status_code == 200
    data = r.json()
    assert "cars" in data
    assert len(data["cars"]) == 20
    assert "icon_url" in data["cars"][0]


def test_compute_empty_selection():
    r = client.post("/api/compute", json={"selected": []})
    assert r.status_code == 400


def test_nearest_validation():
    # missing required fields -> pydantic validation error (422)
    r = client.post("/api/nearest", json={})
    assert r.status_code == 422


def test_leaderboard_post_and_get():
    name = f"testuser_{int(time.time())}"
    r = client.post("/api/leaderboard", json={"name": name, "score": 1.234})
    assert r.status_code == 200
    data = r.json()
    assert "leaderboard" in data
    assert any(item.get("Name") == name for item in data["leaderboard"])


def test_compute_start_and_result_lifecycle():
    # start a job with the initial 5 indices
    r = client.post("/api/compute_start", json={"selected": [0, 1, 2, 3, 4]})
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data
    job_id = data["job_id"]

    # poll for result (timeout ~15s)
    deadline = time.time() + 15
    while time.time() < deadline:
        r2 = client.get("/api/compute_result", params={"job_id": job_id})
        if r2.status_code == 200:
            res = r2.json()
            if res.get("ready"):
                assert "user_steps" in res
                return
        time.sleep(0.5)
    raise AssertionError("Background job did not finish in time")

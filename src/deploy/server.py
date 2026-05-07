from fastapi import FastAPI, Body, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, DotProduct
from sklearn.linear_model import Ridge
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error
from typing import List
import csv
from fastapi import HTTPException
import threading
import uuid
import logging
import tempfile
import time
import os


# Use environment variable to control static serving
NO_STATIC = os.environ.get("NO_STATIC", "0") == "1"

app = FastAPI()

# allow local testing from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# determine directories relative to this file so server works when started from project root
BASE_DIR = Path(__file__).parent.resolve()
REPO_ROOT = BASE_DIR.parent.parent.resolve()
STATIC_DIR = BASE_DIR / "static"


# configure logging
logging.basicConfig(level=logging.INFO)


# simple in-memory job store and lock
RESULTS = {}
RESULTS_LOCK = threading.Lock()

# Results cleanup policy (seconds)
RESULTS_TTL = int(os.environ.get("RESULTS_TTL", "3600"))
RESULTS_CLEANUP_INTERVAL = int(os.environ.get("RESULTS_CLEANUP_INTERVAL", "600"))


def _results_cleanup_worker():
    while True:
        now = time.time()
        with RESULTS_LOCK:
            keys = list(RESULTS.keys())
            for k in keys:
                entry = RESULTS.get(k)
                if not entry:
                    continue
                ts = entry.get("_ts")
                if ts and now - ts > RESULTS_TTL:
                    try:
                        del RESULTS[k]
                        logging.info("Cleaned up RESULT %s", k)
                    except KeyError:
                        pass
        time.sleep(RESULTS_CLEANUP_INTERVAL)


# start cleanup thread
cleanup_thread = threading.Thread(target=_results_cleanup_worker, daemon=True)
cleanup_thread.start()


def braking_distance(v_kmh, m, brake_force=5000):
    v = v_kmh / 3.6
    a = brake_force / m
    s = v**2 / (2 * a)
    return s


def create_cars():
    cars = []
    id_counter = 0
    path = "icons/auto.png"
    weight = 1000
    for i in [20, 50, 60, 100]:
        cars.append(
            {
                "id": id_counter,
                "path": path,
                "name": "Kleinwagen",
                "gewicht": weight,
                "geschwindigkeit": i,
                "label": braking_distance(v_kmh=i, m=weight),
            }
        )
        id_counter += 1
    path = "icons/kleinbus.png"
    weight = 2300
    for i in [30, 40, 70, 90]:
        cars.append(
            {
                "id": id_counter,
                "path": path,
                "name": "Bulli",
                "gewicht": weight,
                "geschwindigkeit": i,
                "label": braking_distance(v_kmh=i, m=weight),
            }
        )
        id_counter += 1
    path = "icons/pickup.png"
    weight = 2000
    for i in [10, 30, 50, 100]:
        cars.append(
            {
                "id": id_counter,
                "path": path,
                "name": "Pickup",
                "gewicht": weight,
                "geschwindigkeit": i,
                "label": braking_distance(v_kmh=i, m=weight),
            }
        )
        id_counter += 1
    path = "icons/lastwagen.png"
    weight = 3000
    for i in [20, 30, 60, 100]:
        cars.append(
            {
                "id": id_counter,
                "path": path,
                "name": "Transporter",
                "gewicht": weight,
                "geschwindigkeit": i,
                "label": braking_distance(v_kmh=i, m=weight),
            }
        )
        id_counter += 1
    path = "icons/sportwagen.png"
    weight = 1500
    for i in [30, 60, 70, 100]:
        cars.append(
            {
                "id": id_counter,
                "path": path,
                "name": "Sportwagen",
                "gewicht": weight,
                "geschwindigkeit": i,
                "label": braking_distance(v_kmh=i, m=weight),
            }
        )
        id_counter += 1
    return cars


def compute_test_data(v_min=5, v_max=105, m_min=900, m_max=3100, n_points=100):
    v_range = np.linspace(v_min, v_max, n_points)
    m_range = np.linspace(m_min, m_max, n_points)
    V, M = np.meshgrid(v_range, m_range)
    S = braking_distance(V, M)
    return V, M, S


def scale_data(V, M, X_train):
    scaler = MinMaxScaler()
    scaler.fit(np.c_[V.ravel(), M.ravel()])
    VM_transformed = scaler.transform(np.c_[V.ravel(), M.ravel()])
    X_train_transformed = scaler.transform(X_train)
    return VM_transformed, X_train_transformed, scaler


def train_model_and_predict_grid(X_train, y_train, VM, y_true, linear_model=False):
    if linear_model:
        model = Ridge()
    else:
        model = GaussianProcessRegressor(
            normalize_y=True, kernel=1.0 * DotProduct(sigma_0=1.0) ** 2
        )
    model.fit(X_train, y_train)
    y_pred = model.predict(VM)
    y_pred = y_pred.reshape(y_true.shape)
    rmse = mean_absolute_error(y_true=y_true.flatten(), y_pred=y_pred.flatten())
    return y_pred, rmse


def train_model_with_uncertainty(
    X_train, y_train, VM_transformed, y_true, linear_model=False
):
    # uses GP to return mean, std, rmse
    if linear_model:
        model = Ridge()
        y_pred = model.fit(X_train, y_train).predict(VM_transformed)
        y_std = np.zeros_like(y_pred)
    else:
        model = GaussianProcessRegressor(
            normalize_y=True,
            kernel=RBF(length_scale=0.5, length_scale_bounds=(1e-1, 2)),
        )
        model.fit(X_train, y_train)
        y_pred, y_std = model.predict(VM_transformed, return_std=True)

    y_pred = y_pred.reshape(y_true.shape)
    y_std = y_std.reshape(y_true.shape)
    rmse = mean_absolute_error(y_true=y_true.flatten(), y_pred=y_pred.flatten())
    return y_pred, y_std, rmse


def compute_scores_for_cars(
    selected_cars_trans, selected_labels, VM_transformed, y_true
):
    if len(selected_cars_trans) == 0:
        return []
    # after state
    _, after_rmse = train_model_and_predict_grid(
        X_train=selected_cars_trans,
        y_train=selected_labels,
        VM=VM_transformed,
        y_true=y_true,
    )
    scores = []
    for idx in range(len(selected_cars_trans)):
        mask = [i for i in range(len(selected_cars_trans)) if i != idx]
        X_before = selected_cars_trans[mask]
        y_before = selected_labels[mask]
        if len(X_before) == 0:
            before_rmse = after_rmse
        else:
            _, before_rmse = train_model_and_predict_grid(
                X_train=X_before, y_train=y_before, VM=VM_transformed, y_true=y_true
            )
        improvement = before_rmse - after_rmse
        scores.append(improvement)
    scores = np.array(scores)
    if scores.max() != 0:
        scores = scores / np.max(scores) * 10
    scores[scores < 0] = 0
    return scores.tolist()


def active_learner_query(selected_idx: List[int], n_queries: int = 2):
    cars = create_cars()
    X = np.array([[a["geschwindigkeit"], a["gewicht"]] for a in cars])
    y = np.array([a["label"] for a in cars])

    # training set from selected indices
    X_train = X[selected_idx]
    y_train = y[selected_idx]

    # build unselected pool
    unselected = [c for c in cars if c["id"] not in selected_idx]
    if len(unselected) == 0:
        return []
    unselected_pool = np.array(
        [[c["geschwindigkeit"], c["gewicht"]] for c in unselected]
    )
    unselected_labels = np.array([c["label"] for c in unselected])

    # scale data using grid scaler
    V, M, _ = compute_test_data()
    VM_transformed, X_train_transformed, scaler = scale_data(V, M, X_train)
    unselected_scaled = scaler.transform(unselected_pool)

    queried = []
    for i in range(n_queries):
        model = GaussianProcessRegressor(
            normalize_y=True,
            kernel=RBF(length_scale=0.5, length_scale_bounds=(1e-1, 2)),
        )
        model.fit(X_train_transformed, y_train)
        _, y_std = model.predict(unselected_scaled, return_std=True)
        qidx = int(np.argmax(y_std))
        queried.append(unselected[qidx])
        # add to training
        X_train_transformed = np.append(
            X_train_transformed, [unselected_scaled[qidx]], axis=0
        )
        y_train = np.append(y_train, unselected_labels[qidx])
        # remove from pool
        # convert to list if needed and remove by index
        if isinstance(unselected, np.ndarray):
            unselected = np.delete(unselected, qidx, axis=0)
        else:
            unselected = [u for j, u in enumerate(unselected) if j != qidx]
        unselected_scaled = np.delete(unselected_scaled, qidx, axis=0)
        unselected_labels = np.delete(unselected_labels, qidx, axis=0)

    # return ids and meta
    results = []
    for q in queried:
        results.append(
            {
                "id": int(q["id"]),
                "geschwindigkeit": q["geschwindigkeit"],
                "gewicht": q["gewicht"],
                "label": float(q["label"]),
            }
        )
    return results


# Leaderboard helpers
LEADERBOARD_FILE = REPO_ROOT / "leaderboard.csv"
LEADERBOARD_LOCK = threading.Lock()


def _validate_indices(selected_idx: List[int], n: int):
    for i in selected_idx:
        try:
            ii = int(i)
        except Exception:
            raise HTTPException(status_code=400, detail=f"invalid selection index: {i}")
        if ii < 0 or ii >= n:
            raise HTTPException(
                status_code=400, detail=f"selection index out of range: {ii}"
            )


def load_leaderboard():
    if not LEADERBOARD_FILE.exists():
        return []
    rows = []
    try:
        with LEADERBOARD_FILE.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    score = float(r.get("Score", r.get("score", "0")))
                except Exception:
                    score = 0.0
                rows.append(
                    {"Name": r.get("Name", r.get("name", "Anonymous")), "Score": score}
                )
    except Exception:
        logging.exception("Failed to load leaderboard")
        return []
    # sort ascending (lower score better)
    rows.sort(key=lambda x: x["Score"])
    return rows


def save_leaderboard_entry(name: str, score: float):
    with LEADERBOARD_LOCK:
        rows = load_leaderboard()
        # remove existing name
        rows = [r for r in rows if r["Name"] != name]
        rows.append({"Name": name, "Score": float(score)})
        rows.sort(key=lambda x: x["Score"])
        # write back atomically
        tmp = None
        try:
            dirpath = LEADERBOARD_FILE.parent
            tf = tempfile.NamedTemporaryFile(
                "w", delete=False, dir=str(dirpath), newline="", encoding="utf-8"
            )
            tmp = tf.name
            writer = csv.DictWriter(tf, fieldnames=["Name", "Score"])
            writer.writeheader()
            for r in rows:
                writer.writerow({"Name": r["Name"], "Score": r["Score"]})
            tf.close()
            os.replace(tmp, str(LEADERBOARD_FILE))
        except Exception:
            logging.exception("Failed to save leaderboard entry")
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        return rows


class Selection(BaseModel):
    selected: List[int]


class LeaderEntry(BaseModel):
    name: str
    score: float


@app.get("/api/cars")
def api_cars(request: Request):
    cars = create_cars()
    # expose icon URLs resolved against the request root_path
    for c in cars:
        icon_name = c["path"].split("/")[-1]
        try:
            c["icon_url"] = str(request.url_for("get_icon", icon_name=icon_name))
        except Exception:
            # fallback to absolute-root path
            c["icon_url"] = f"/icons/{icon_name}"
    return JSONResponse(content={"cars": cars})


@app.post("/api/compute")
def api_compute(request: Request, payload: Selection = Body(...)):
    cars = create_cars()
    selected_ids = payload.selected
    if not selected_ids:
        return JSONResponse(content={"error": "no selection"}, status_code=400)

    X = np.array([[a["geschwindigkeit"], a["gewicht"]] for a in cars])
    y = np.array([a["label"] for a in cars])

    _validate_indices(selected_ids, len(cars))
    selected_idx = [int(i) for i in selected_ids]
    X_train = X[selected_idx]
    y_train = y[selected_idx]

    V, M, S = compute_test_data()
    VM_transformed, X_train_transformed, scaler = scale_data(V, M, X_train)
    y_pred, user_rmse = train_model_and_predict_grid(
        X_train_transformed, y_train, VM_transformed, S
    )
    y_pred[y_pred < 0] = 0

    # compute scores (use transformed selected points)
    scores = compute_scores_for_cars(X_train_transformed, y_train, VM_transformed, S)

    # compute gif urls for selected (resolve against request root_path)
    gifs = []
    for sid in selected_idx:
        car = cars[sid]
        velocity = car["geschwindigkeit"]
        base = car["path"].split("/")[-1][:-4]
        try:
            gifs.append(
                str(request.url_for("get_gif", gif_name=f"{base}_{velocity}.gif"))
            )
        except Exception:
            gifs.append(f"/gifs/{base}_{velocity}.gif")

    return JSONResponse(
        content={
            "V": V.tolist(),
            "M": M.tolist(),
            "y_pred": y_pred.tolist(),
            "user_rmse": float(user_rmse),
            "scores": scores,
            "gifs": gifs,
        }
    )


def _compute_worker(job_id: str, selected_idx: List[int]):
    try:
        cars = create_cars()
        X = np.array([[a["geschwindigkeit"], a["gewicht"]] for a in cars])
        y = np.array([a["label"] for a in cars])

        X_train = X[selected_idx]
        y_train = y[selected_idx]

        V, M, S = compute_test_data()

        # determine initial (first 5) and additional indices
        initial_idx = selected_idx[:5]
        additional_idx = selected_idx[5:]

        # scale once (scaler fitted on grid)
        VM_transformed, _, scaler = scale_data(V, M, X_train[:1])

        # prepare user-stepwise retraining: start with initial 5, then add each additional sequentially
        user_steps = []
        # build initial training arrays
        X_init = X[initial_idx]
        y_init = y[initial_idx]

        # transform initial
        X_init_trans = scaler.transform(X_init)

        # step 0: initial model
        y_pred0, y_std0, rmse0 = train_model_with_uncertainty(
            X_init_trans, y_init, VM_transformed, S
        )
        y_pred0[y_pred0 < 0] = 0
        user_steps.append(
            {
                "y_pred": y_pred0.tolist(),
                "y_std": y_std0.tolist(),
                "rmse": float(rmse0),
                "train_ids": initial_idx,
            }
        )

        # iterative additional points
        current_X = X_init.copy()
        current_y = y_init.copy()
        for add_id in additional_idx:
            # append new point
            pt = X[int(add_id)].reshape(1, -1)
            lab = y[int(add_id)]
            current_X = np.append(current_X, pt, axis=0)
            current_y = np.append(current_y, lab)
            # transform with same scaler
            current_X_trans = scaler.transform(current_X)
            y_pred_i, y_std_i, rmse_i = train_model_with_uncertainty(
                current_X_trans, current_y, VM_transformed, S
            )
            y_pred_i[y_pred_i < 0] = 0
            # collect step
            # train ids are initial + already added ones
            ids = initial_idx + additional_idx[: list(additional_idx).index(add_id) + 1]
            user_steps.append(
                {
                    "y_pred": y_pred_i.tolist(),
                    "y_std": y_std_i.tolist(),
                    "rmse": float(rmse_i),
                    "train_ids": ids,
                }
            )

        # final model is last in user_steps
        y_pred = np.array(user_steps[-1]["y_pred"])
        user_rmse = float(user_steps[-1]["rmse"])

        # compute scores using final transformed X
        final_X_trans = scaler.transform(current_X)
        scores = compute_scores_for_cars(final_X_trans, current_y, VM_transformed, S)

        gifs = []
        for sid in selected_idx:
            car = cars[sid]
            velocity = car["geschwindigkeit"]
            base = car["path"].split("/")[-1][:-4]
            # store filename only in background results; resolution happens when serving results
            gifs.append(f"{base}_{velocity}.gif")

        # prepare training points metadata (mark first 5 as initial, rest as additional)
        train_points = []
        for idx, sid in enumerate(selected_idx):
            car = cars[sid]
            role = "initial" if idx < 5 else "additional"
            train_points.append(
                {
                    "id": int(car["id"]),
                    "geschwindigkeit": float(car["geschwindigkeit"]),
                    "gewicht": float(car["gewicht"]),
                    "role": role,
                }
            )

        # compute active learner steps (simulate AL adding two queried points based on initial set)
        try:
            queried = active_learner_query(initial_idx, n_queries=2)
            al_steps = []
            # start from initial
            X_al_current = X_init.copy()
            y_al_current = y_init.copy()
            # step 0: initial al model
            y_al0, y_alstd0, rmse_al0 = train_model_with_uncertainty(
                scaler.transform(X_al_current), y_al_current, VM_transformed, S
            )
            y_al0[y_al0 < 0] = 0
            al_steps.append(
                {
                    "y_pred": y_al0.tolist(),
                    "y_std": y_alstd0.tolist(),
                    "rmse": float(rmse_al0),
                    "train_ids": initial_idx,
                }
            )
            # sequentially add queried points
            for qi, q in enumerate(queried):
                pt = np.array([[q["geschwindigkeit"], q["gewicht"]]])
                lab = q["label"]
                X_al_current = np.append(X_al_current, pt, axis=0)
                y_al_current = np.append(y_al_current, lab)
                y_al_i, y_alstd_i, rmse_ali = train_model_with_uncertainty(
                    scaler.transform(X_al_current), y_al_current, VM_transformed, S
                )
                y_al_i[y_al_i < 0] = 0
                al_ids = initial_idx + [int(qq["id"]) for qq in queried[: qi + 1]]
                al_steps.append(
                    {
                        "y_pred": y_al_i.tolist(),
                        "y_std": y_alstd_i.tolist(),
                        "rmse": float(rmse_ali),
                        "train_ids": al_ids,
                    }
                )
        except Exception as e:
            logging.exception("Active learner simulation failed")
            queried = []
            al_steps = []

        # store result including ground truth and active learner outputs
        with RESULTS_LOCK:
            RESULTS[job_id] = {
                "ready": True,
                "V": V.tolist(),
                "M": M.tolist(),
                "user_steps": user_steps,
                "scores": scores,
                "gifs": gifs,
                "train_points": train_points,
                "ground_truth": S.tolist(),
                "al_steps": al_steps,
                "_ts": time.time(),
            }
    except Exception as e:
        logging.exception("Error in _compute_worker for job %s", job_id)
        with RESULTS_LOCK:
            RESULTS[job_id] = {"ready": True, "error": str(e), "_ts": time.time()}


# RESULTS is defined earlier; no-op here


@app.post("/api/compute_start")
def api_compute_start(request: Request, payload: Selection = Body(...)):
    selected_ids = payload.selected
    if not selected_ids:
        raise HTTPException(status_code=400, detail="no selection")
    selected_idx = [int(i) for i in selected_ids]
    cars = create_cars()
    _validate_indices(selected_idx, len(cars))
    # create job id
    job_id = str(uuid.uuid4())
    with RESULTS_LOCK:
        RESULTS[job_id] = {"ready": False, "_ts": time.time()}

    # compute gifs quickly to return immediately (resolve against request root_path)
    cars = create_cars()
    gifs = []
    for sid in selected_idx:
        car = cars[sid]
        velocity = car["geschwindigkeit"]
        base = car["path"].split("/")[-1][:-4]
        try:
            gifs.append(
                str(request.url_for("get_gif", gif_name=f"{base}_{velocity}.gif"))
            )
        except Exception:
            gifs.append(f"/gifs/{base}_{velocity}.gif")

    # start background thread
    thread = threading.Thread(target=_compute_worker, args=(job_id, selected_idx))
    thread.daemon = True
    thread.start()

    return JSONResponse(content={"job_id": job_id, "gifs": gifs})


@app.get("/api/compute_result")
def api_compute_result(request: Request, job_id: str):
    with RESULTS_LOCK:
        if job_id not in RESULTS:
            raise HTTPException(status_code=404, detail="job not found")
        res = RESULTS[job_id].copy()
    # hide internal timestamp
    res.pop("_ts", None)
    # resolve gif filenames (background worker stores filenames only)
    if "gifs" in res and isinstance(res["gifs"], list):
        resolved = []
        for g in res["gifs"]:
            # g may be stored as filename or as a path; normalize
            gif_name = g.split("/")[-1]
            try:
                resolved.append(str(request.url_for("get_gif", gif_name=gif_name)))
            except Exception:
                resolved.append(f"/gifs/{gif_name}")
        res["gifs"] = resolved
    return JSONResponse(content=res)


class NearestPayload(BaseModel):
    x: float
    y: float
    selected: List[int] = []


@app.post("/api/nearest")
def api_nearest(request: Request, payload: NearestPayload = Body(...)):
    x = float(payload.x)
    y = float(payload.y)
    selected = payload.selected or []

    cars = create_cars()
    X = np.array([[a["geschwindigkeit"], a["gewicht"]] for a in cars])
    pt = np.array([x, y])
    distances = np.sqrt(np.sum((X - pt) ** 2, axis=1))
    mask = np.array([False] * len(distances))
    _validate_indices(selected, len(mask))
    for s in selected:
        mask[int(s)] = True
    distances[mask] = np.inf
    nearest_idx = int(np.argmin(distances))
    car = cars[nearest_idx]
    velocity = car["geschwindigkeit"]
    base = car["path"].split("/")[-1][:-4]
    gif_name = f"{base}_{velocity}.gif"
    try:
        gif = str(request.url_for("get_gif", gif_name=gif_name))
    except Exception:
        gif = f"/gifs/{gif_name}"
    icon_name = car["path"].split("/")[-1]
    try:
        icon_url = str(request.url_for("get_icon", icon_name=icon_name))
    except Exception:
        icon_url = f"/icons/{icon_name}"
    return JSONResponse(
        content={
            "car": {
                "id": int(car["id"]),
                "name": car["name"],
                "gewicht": car["gewicht"],
                "geschwindigkeit": car["geschwindigkeit"],
                "icon_url": icon_url,
            },
            "gif": gif,
        }
    )


# Serve static and asset files only if not disabled
if not NO_STATIC:

    @app.get("/")
    def index():
        logging.info("Serving index.html")
        file = STATIC_DIR / "index.html"
        if not file.exists():
            raise HTTPException(status_code=404, detail="index not found")
        return FileResponse(str(file))

    @app.get("/styles.css")
    def styles():
        file = STATIC_DIR / "styles.css"
        if not file.exists():
            raise HTTPException(status_code=404, detail="styles.css not found")
        return FileResponse(str(file))

    @app.get("/app.js")
    def app_js():
        file = STATIC_DIR / "app.js"
        if not file.exists():
            raise HTTPException(status_code=404, detail="app.js not found")
        return FileResponse(str(file))

    @app.get("/vendor/plotly-3.5.1.min.js")
    def plotly_js():
        file = STATIC_DIR / "vendor" / "plotly-3.5.1.min.js"
        if not file.exists():
            raise HTTPException(status_code=404, detail="plotly lib not found")
        return FileResponse(str(file))

    @app.get("/gifs/{gif_name}")
    def get_gif(gif_name: str):
        file = STATIC_DIR / "gifs" / gif_name
        if not file.exists():
            raise HTTPException(status_code=404, detail="gif not found")
        return FileResponse(str(file))

    @app.get("/icons/{icon_name}")
    def get_icon(icon_name: str):
        file = STATIC_DIR / "icons" / icon_name
        if not file.exists():
            raise HTTPException(status_code=404, detail="icon not found")
        return FileResponse(str(file))

    @app.get("/favicon.ico")
    def favicon():
        file = STATIC_DIR / "favicon.ico"
        if not file.exists():
            raise HTTPException(status_code=404, detail="favicon not found")
        return FileResponse(str(file))

    @app.get("/images/{image_name}")
    def get_image(image_name: str):
        file = STATIC_DIR / "images" / image_name
        if not file.exists():
            raise HTTPException(status_code=404, detail="image not found")
        return FileResponse(str(file))


@app.post("/api/active")
def api_active(payload: Selection = Body(...)):
    selected_ids = payload.selected
    if not selected_ids:
        raise HTTPException(status_code=400, detail="no selection")
    cars = create_cars()
    _validate_indices(selected_ids, len(cars))
    selected_idx = [int(i) for i in selected_ids]
    results = active_learner_query(selected_idx)
    return JSONResponse(content={"queried": results})


@app.get("/api/leaderboard")
def api_leaderboard_get():
    rows = load_leaderboard()
    return JSONResponse(content={"leaderboard": rows})


@app.post("/api/leaderboard")
def api_leaderboard_post(entry: LeaderEntry = Body(...)):
    rows = save_leaderboard_entry(entry.name, entry.score)
    return JSONResponse(content={"leaderboard": rows})

import base64
import time
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, DotProduct
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error
from sklearn.preprocessing import MinMaxScaler
from st_click_detector import click_detector


# -----------------------------
# utility functions
# -----------------------------


@st.cache_data
def img_to_datauri(path: str) -> str:
    b = Path(path).read_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode()


@st.cache_data
def make_html(cars, selected):
    html = """
    <style>
        .container {
            display: grid;
            grid-template-columns: repeat(4, minmax(140px, 1fr));
            gap: 10px;
            justify-items: stretch;   /* Karten füllen die Spalten */
            justify-content: start;   /* Grid klebt links */
            width: 100% !important;   /* volle Breite nutzen */
            margin: 0 !important;     /* Auto-Margins killen */
        }
        .card { 
            border: 3px solid lightgray; 
            border-radius: 8px; 
            padding: 6px; 
            text-align: center; 
            width: 100%; 
            box-sizing: border-box;
        }
        
        .card img { 
            width: 80px; 
            height: auto; 
            display: block; 
            margin: 0 auto 2px; 
        }
        
        .card div { 
            font-size: 1rem; 
            line-height: 1.0; 
        }
        .card.selected { 
            border-color: green; 
            box-shadow: 0 0 8px rgba(0,128,0,0.25); 
        }
    </style>
    <div class="container">
    """
    for c in cars:
        datauri = img_to_datauri(c["path"])
        selected_cls = "selected" if c["id"] in selected else ""
        html += f"""
        <div class="card {selected_cls}">
            <b>{c["name"]}</b>
            <div>{c["gewicht"]} kg</div>
            <a href="#" id="auto_{c["id"]}">
                <img src="{datauri}">
            </a>
            <div><b>{c["geschwindigkeit"]} km/h</b></div>
        </div>
        """
    html += "</div>"
    return html


@st.cache_data
def make_html_single_car(car, datauri, selected=False):
    html = (
        """
        <style>
            .container {
                display: grid;
                grid-template-columns: repeat(4, minmax(140px, 1fr));
                gap: 10px;
                justify-items: stretch;   /* Karten füllen die Spalten */
                justify-content: start;   /* Grid klebt links */
                width: 100% !important;   /* volle Breite nutzen */
                margin: 0 !important;     /* Auto-Margins killen */
            }
            .card { 
                border: 3px solid lightgray; 
                border-radius: 8px; 
                padding: 6px; 
                text-align: center; 
                width: 120px; 
                box-sizing: border-box;
            }
    
            .card img { 
                width: 80px; 
                height: auto; 
                display: block; 
                margin: 0 auto 2px; 
            }
    
            .card div { 
                font-size: 1rem; 
                line-height: 1.0; 
            }
            .card.selected { 
                border-color: green; 
                box-shadow: 0 0 8px rgba(0,128,0,0.25); 
            }
        </style>
    """
        + f"""
        <div class="container">
            <div class="card {"selected" if selected else ""}">
                <b>{car["name"]}</b>
                <div>{car["gewicht"]} kg</div>
                <a href="#" id="auto_{car["id"]}">
                    <img src="{datauri}">
                </a>
                <div><b>{car["geschwindigkeit"]} km/h</b></div>
            </div>
        </div>
    """
    )
    return html


@st.cache_data
def get_gif(car_id):
    # get the path of the GIF matching the car specified in car_id
    car = cars[car_id]
    car_type = car["name"]
    velocity = car["geschwindigkeit"]
    path = Path.cwd().joinpath(f"gifs/{car['path'].split('/')[-1][:-4]}_{velocity}.gif")
    return car_type, velocity, path


@st.cache_data
def braking_distance(v_kmh, m, brake_force=5000):
    # base formula: v**2/(2*a)
    # "a" differs for different cars because we assume a constant brake force
    # velocity (v) from km/h in m/s
    v = v_kmh / 3.6
    # compute brake-acceleration
    a = brake_force / m
    # compute the distance
    s = v**2 / (2 * a)
    return s


@st.cache_data
def create_cars():
    cars = []
    id_counter = 0
    # add normal cars
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
    # add "bullis"
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
    # add pickups
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
    # add lkws
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
    # add sports cars
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


@st.cache_data
def compute_test_data(v_min=5, v_max=105, m_min=900, m_max=3100, n_points=100):
    # create test data
    v_range = np.linspace(v_min, v_max, n_points)
    m_range = np.linspace(m_min, m_max, n_points)
    V, M = np.meshgrid(v_range, m_range)
    S = braking_distance(V, M)
    return V, M, S


@st.cache_data
def scale_data(V, M, X_train):
    scaler = MinMaxScaler()
    scaler.fit(np.c_[V.ravel(), M.ravel()])
    VM_transformed = scaler.transform(np.c_[V.ravel(), M.ravel()])
    X_train_transformed = scaler.transform(X_train)
    return VM_transformed, X_train_transformed


@st.cache_data
def train_model_and_predict_grid(X_train, y_train, VM, y_true, linear_model=False):
    # define model
    if linear_model:
        model = Ridge()
    else:
        # model = GaussianProcessRegressor(normalize_y=True, kernel=RBF(length_scale=0.5, length_scale_bounds=(1e-1, 2)))
        model = GaussianProcessRegressor(
            normalize_y=True, kernel=1.0 * DotProduct(sigma_0=1.0) ** 2
        )
    # train model
    model.fit(X_train, y_train)

    # compute error
    y_pred = model.predict(VM)
    y_pred = y_pred.reshape(V.shape)
    rmse = mean_absolute_error(y_true=y_true.flatten(), y_pred=y_pred.flatten())

    return y_pred, rmse


@st.cache_data
def plot_user_figure(V, M, S, X_train, scores):
    # define a figure
    fig = go.Figure()

    # make a grid of invisible points for selection
    fig.add_trace(
        go.Scatter(
            x=V.ravel(),
            y=M.ravel(),
            mode="markers",
            marker=dict(size=12, color="rgba(0,0,0,0)"),
            name="Klickpunkte",
            showlegend=False,
            hoverinfo="none",
            zorder=20,
        )
    )
    # Kontur der Modellvorhersage
    fig.add_trace(
        go.Contour(
            z=S,
            x=V[0],
            y=M[:, 0],
            colorscale="jet",
            contours=dict(
                start=0,
                end=271,
                size=8,
                # coloring='heatmap',
                showlines=False,
            ),
            colorbar=dict(
                title=dict(
                    text="Bremsweg",  # title here
                    side="right",
                    font=dict(size=20, family="Arial, sans-serif"),
                ),
                nticks=10,
                ticks="outside",
                ticklen=5,
                tickwidth=1,
                tickfont=dict(
                    size=16,
                ),
                showticklabels=True,
            ),
            showscale=True,
            zorder=0,
        )
    )

    # show selected points (training points)
    # First 5
    fig.add_trace(
        go.Scatter(
            x=X_train[:5, 0],
            y=X_train[:5, 1],
            mode="markers + text",
            marker=dict(
                color="red", line=dict(width=2, color="white"), size=12, symbol="x"
            ),
            text=[
                f"Auto {idx + 1}<br>{score:.0f}/10" for idx, score in enumerate(scores)
            ],
            textposition=compute_text_position(X_train),
            textfont=dict(
                family="Arial Black",  # Schriftart
                size=14,  # Schriftgröße
                color="white",  # Textfarbe
                shadow="#000000 0px 0px 3px",
            ),
            opacity=0.8,
            name="Trainingspunkte",
            showlegend=False,
            # hoverinfo="skip",
            selected=dict(marker=dict(opacity=1)),  # bleibt voll sichtbar
            unselected=dict(marker=dict(opacity=1)),  # kein Verblassen
            zorder=1,
        )
    )

    # next points get different layout
    # plot the selection of the first and second car_id
    if len(X_train) > 5:
        fig.add_trace(
            go.Scatter(
                x=X_train[5:, 0],
                y=X_train[5:, 1],
                mode="markers",
                marker=dict(
                    color="gray", line=dict(width=3, color="white"), size=20, symbol="x"
                ),
                name="Ausgewählter Punkt",
                showlegend=False,
                hoverinfo="skip",
                selected=dict(marker=dict(opacity=1)),  # bleibt voll sichtbar
                unselected=dict(marker=dict(opacity=1)),  # kein Verblassen
                zorder=2,
            )
        )

    try:
        if st.session_state.additional_car_selection >= 1:
            fig_user_model.add_trace(
                go.Scatter(
                    x=[st.session_state.first_car["geschwindigkeit"]],
                    y=[st.session_state.first_car["gewicht"]],
                    mode="markers",
                    marker=dict(
                        color="gray",
                        line=dict(width=3, color="white"),
                        size=20,
                        symbol="x",
                    ),
                    name="Ausgewählter Punkt",
                    showlegend=False,
                    hoverinfo="skip",
                    selected=dict(marker=dict(opacity=1)),  # bleibt voll sichtbar
                    unselected=dict(marker=dict(opacity=1)),  # kein Verblassen
                    zorder=2,
                )
            )
    except:
        pass
    try:
        if st.session_state.additional_car_selection == 2:
            fig_user_model.add_trace(
                go.Scatter(
                    x=[st.session_state.second_car["geschwindigkeit"]],
                    y=[st.session_state.second_car["gewicht"]],
                    mode="markers",
                    marker=dict(
                        color="gray",
                        line=dict(width=3, color="white"),
                        size=20,
                        symbol="x",
                    ),
                    name="Ausgewählter Punkt",
                    showlegend=False,
                    hoverinfo="skip",
                    selected=dict(marker=dict(opacity=1)),  # bleibt voll sichtbar
                    unselected=dict(marker=dict(opacity=1)),  # kein Verblassen
                    zorder=2,
                )
            )
    except:
        pass

    # layout stuff
    fig = fig_layout(fig)

    return fig


@st.cache_data
def plot_ground_truth(V, M, S, X_train):
    fig = go.Figure()

    # Kontur der Modellvorhersage
    fig.add_trace(
        go.Contour(
            z=S,
            x=V[0],
            y=M[:, 0],
            colorscale="jet",
            contours=dict(
                start=0,
                end=270,
                size=8,
                # coloring='heatmap',
                showlines=False,
            ),
            colorbar=dict(
                title=dict(
                    text="Bremsweg",  # title here
                    side="right",
                    font=dict(size=20, family="Arial, sans-serif"),
                ),
                nticks=10,
                ticks="outside",
                ticklen=5,
                tickwidth=1,
                tickfont=dict(
                    size=16,
                ),
                showticklabels=True,
            ),
            showscale=True,
            zorder=0,
            hoverinfo="none",
        )
    )

    # show selected points (training points)
    fig.add_trace(
        go.Scatter(
            x=X_train[:, 0],
            y=X_train[:, 1],
            mode="markers + text",
            marker=dict(
                color="red", line=dict(width=2, color="white"), size=12, symbol="x"
            ),
            name="Trainingspunkte",
            showlegend=False,
            hoverinfo="none",
            selected=dict(marker=dict(opacity=1)),  # bleibt voll sichtbar
            unselected=dict(marker=dict(opacity=1)),  # kein Verblassen
            zorder=1,
        )
    )

    # next points get different layout
    # plot the selection of the first and second car_id
    if len(X_train) > 5:
        fig.add_trace(
            go.Scatter(
                x=X_train[5:, 0],
                y=X_train[5:, 1],
                mode="markers",
                marker=dict(
                    color="gray", line=dict(width=3, color="white"), size=20, symbol="x"
                ),
                name="Ausgewählter Punkt",
                showlegend=False,
                hoverinfo="none",
                selected=dict(marker=dict(opacity=1)),  # bleibt voll sichtbar
                unselected=dict(marker=dict(opacity=1)),  # kein Verblassen
                zorder=2,
            )
        )

    # layout stuff
    fig = fig_layout(fig)

    return fig


@st.cache_data
def plot_uncertainty(V, M, unc, X_train, selected=None):
    fig = go.Figure()

    # Kontur der Modellvorhersage
    fig.add_trace(
        go.Contour(
            z=unc,
            x=V[0],
            y=M[:, 0],
            colorscale="greens",
            contours=dict(
                showlines=False,
            ),
            colorbar=dict(
                title=dict(
                    text="Unsicherheit",  # title here
                    side="right",
                    font=dict(size=20, family="Arial, sans-serif"),
                ),
                nticks=10,
                ticks="outside",
                ticklen=5,
                tickwidth=1,
                tickfont=dict(
                    size=16,
                ),
                showticklabels=True,
            ),
            showscale=True,
            zorder=0,
            hoverinfo="none",
        )
    )

    # show selected points (training points)
    fig.add_trace(
        go.Scatter(
            x=X_train[:, 0],
            y=X_train[:, 1],
            mode="markers + text",
            marker=dict(
                color="red", line=dict(width=2, color="white"), size=12, symbol="x"
            ),
            name="Trainingspunkte",
            showlegend=False,
            hoverinfo="none",
            selected=dict(marker=dict(opacity=1)),  # bleibt voll sichtbar
            unselected=dict(marker=dict(opacity=1)),  # kein Verblassen
            zorder=3,
        )
    )

    if selected is not None:
        # selected points get different layout
        fig.add_trace(
            go.Scatter(
                x=[selected[0]],
                y=[selected[1]],
                mode="markers",
                marker=dict(
                    color="gray", line=dict(width=3, color="white"), size=20, symbol="x"
                ),
                name="Ausgewählter Punkt",
                showlegend=False,
                hoverinfo="none",
                selected=dict(marker=dict(opacity=1)),  # bleibt voll sichtbar
                unselected=dict(marker=dict(opacity=1)),  # kein Verblassen
                zorder=2,
            )
        )

    # layout stuff
    fig = fig_layout(fig)

    return fig


@st.cache_data
def fig_layout(fig):
    # layout stuff
    fig.update_layout(
        xaxis_title="Geschwindigkeit (km/h)",
        yaxis_title="Gewicht (kg)",
        height=450,
        margin={"t": 0, "l": 0, "b": 0, "r": 0},
    )
    fig.update_xaxes(
        range=[V.min(), V.max()],
        fixedrange=True,
        title_text="Geschwindigkeit (km/h)",
        title_font={"size": 20},
        tickfont={"size": 18},
        ticklabelstandoff=0,
        tickcolor="black",
        ticks="inside",
    )
    fig.update_yaxes(
        range=[M.min(), M.max()],
        fixedrange=True,
        title_text="Gewicht (kg)",
        title_font={"size": 20},
        tickfont={"size": 18},
        ticklabelstandoff=5,
        tickcolor="black",
        ticks="inside",
    )
    return fig


@st.cache_data
def compute_text_position(X_train):
    # compute text positions based on the quadrant the point is in
    positions = []
    for xi, yi in X_train:
        if yi == 1000:
            first_part = "top"
            if xi == 20:
                second_part = "center"
            elif xi == 60:
                second_part = "right"
            else:
                second_part = "left"
            positions.append(first_part + " " + second_part)
        if yi == 1500:
            first_part = "top"
            if xi == 30:
                second_part = "center"
            elif xi == 70:
                second_part = "right"
            else:
                second_part = "left"
            positions.append(first_part + " " + second_part)
        if yi == 2000:
            first_part = "bottom"
            if xi == 10:
                second_part = "right"
            elif xi == 100:
                second_part = "left"
            else:
                second_part = "center"
            positions.append(first_part + " " + second_part)
        if yi == 2300:
            first_part = "bottom"
            if xi == 30:
                second_part = "left"
            elif xi == 40:
                second_part = "right"
            else:
                second_part = "center"
            positions.append(first_part + " " + second_part)
        if yi == 3000:
            first_part = "bottom"
            if xi == 30:
                second_part = "right"
            elif xi == 60:
                second_part = "center"
            else:
                second_part = "left"
            positions.append(first_part + " " + second_part)

    return positions


def search_nearest_unselected_car(X, point_x, point_y):
    # compute the nearest car_id to selected point
    distances = np.sqrt((X[:, 0] - point_x) ** 2 + (X[:, 1] - point_y) ** 2)
    # mask all already selected cars
    mask = np.array(list(st.session_state.selected))
    distances[mask] = np.inf
    # determine nearest unselected car_id
    nearest_idx = np.argmin(distances)
    return nearest_idx


def active_learner(X_train, y_train, pool, n_queries=2):
    # define which cars from the pool can be still selected
    unselected_pool = np.zeros((len(pool) - len(X_train), 2))
    unselected_pool_labels = np.zeros(len(unselected_pool))
    i = 0
    for car in pool:
        if car["label"] not in y_train:
            unselected_pool[i] = car["geschwindigkeit"], car["gewicht"]
            unselected_pool_labels[i] = car["label"]
            i += 1

    # scale data for GP to work
    V, M, _ = compute_test_data()
    VM_transformed, unselected_pool_scaled = scale_data(V, M, unselected_pool)

    # define list for queried points and the uncertainties to plot
    queried_points = []
    uncertainty_grids = []

    # query points
    for i in range(n_queries):
        # define model
        model = GaussianProcessRegressor(
            normalize_y=True,
            kernel=RBF(length_scale=0.5, length_scale_bounds=(1e-1, 2)),
        )
        # train model
        model.fit(X_train, y_train)
        # predict std for unselected pool
        _, y_std = model.predict(unselected_pool_scaled, return_std=True)
        # predict std for grid
        _, y_std_grid = model.predict(VM_transformed, return_std=True)
        uncertainty_grids.append(y_std_grid)
        # find max uncertainty
        query_idx = np.argmax(y_std)
        # add this index to the final return value
        queried_points.append(
            (unselected_pool[query_idx], unselected_pool_labels[query_idx])
        )
        # add this index to training data
        X_train = np.append(X_train, [unselected_pool_scaled[query_idx]], axis=0)
        y_train = np.append(y_train, unselected_pool_labels[query_idx])
        # remove it from the pool
        unselected_pool = np.delete(unselected_pool, query_idx, axis=0)
        unselected_pool_scaled = np.delete(unselected_pool_scaled, query_idx, axis=0)
        unselected_pool_labels = np.delete(unselected_pool_labels, query_idx)

    # add the uncertainty after the last query to the grids
    model = GaussianProcessRegressor(
        normalize_y=True, kernel=RBF(length_scale=0.5, length_scale_bounds=(1e-1, 2))
    )
    model.fit(X_train, y_train)
    _, y_std_grid = model.predict(VM_transformed, return_std=True)
    uncertainty_grids.append(y_std_grid)

    return queried_points, uncertainty_grids


@st.cache_data
def compute_scores_for_cars(selected_cars, selected_cars_label, y_test, y_true):
    """
    Compute a score for all selected cars according to their order.
    The score is based on the normed model increase. Every point is ranked via a one vs. rest scheme.

    :returns:
        list of float: scores for cars in their order
    """

    # safety condition
    if len(selected_cars) == 0:
        return []

    # compute the "after state" (the test user_rmse with all five points)
    _, after_rmse = train_model_and_predict_grid(
        X_train=selected_cars,
        y_train=selected_cars_label,
        VM=y_test,
        y_true=y_true,
        linear_model=False,
    )

    # define the list of the scores that will be returned later
    scores = []

    for idx, car in enumerate(selected_cars):
        # select the "before state" (all points except the current one)
        other_indices = [j for j, _ in enumerate(selected_cars) if j != idx]
        X_before, y_before = (
            selected_cars[other_indices],
            selected_cars_label[other_indices],
        )

        # compute the user_rmse with these other data points
        _, before_rmse = train_model_and_predict_grid(
            X_train=X_before,
            y_train=y_before,
            VM=y_test,
            y_true=y_true,
            linear_model=False,
        )

        # compute relative improvement
        improvement = before_rmse - after_rmse
        scores.append(improvement)

    # normalize scores
    scores = np.array(scores)
    scores = scores / np.max(scores) * 10
    scores[scores < 0] = 0

    return scores.tolist()


def show_results():
    st.session_state.show_results = True


def show_al_results():
    st.session_state.show_al_results = True


# -----------------------------
# some design stuff
# -----------------------------

# create a base container so that the plots and other elements do not flicker and change position on reloads
base = st.container()

# Style the Tabs for greater font-size
css = """
    <style>
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"]
        {
            font-size:1.1rem;
        }
    </style>
"""
st.markdown(css, unsafe_allow_html=True)

# -----------------------------
# create car pool
# -----------------------------

cars = create_cars()
X = np.array([[a["geschwindigkeit"], a["gewicht"]] for a in cars])
y = np.array([a["label"] for a in cars])

# -----------------------------
# session state
# -----------------------------
if "selected" not in st.session_state:
    st.session_state.selected = []
if "confirmed" not in st.session_state:
    st.session_state.confirmed = False
if "lock_selected" not in st.session_state:
    st.session_state.lock_selected = False
if "show_plot" not in st.session_state:
    st.session_state.show_plot = False
if "additional_car_selection" not in st.session_state:
    st.session_state.additional_car_selection = 0
if "nearest_car" not in st.session_state:
    st.session_state.nearest_car = None
if "old_selection" not in st.session_state:
    st.session_state.old_selection = None
if "selection_changed" not in st.session_state:
    st.session_state.selection_changed = False
if "show_results" not in st.session_state:
    st.session_state.show_results = False
if "show_al_results" not in st.session_state:
    st.session_state.show_al_results = False

# -----------------------------
# handle onclick events
# -----------------------------
clicked = st.session_state.get("car_selector")
if clicked and not st.session_state.lock_selected:
    if clicked.startswith("auto_"):
        aid = int(clicked.split("_", 1)[1])
        if aid in st.session_state.selected:
            st.session_state.selected.remove(aid)
        else:
            if len(st.session_state.selected) < 5:
                st.session_state.selected.append(aid)

# -----------------------------
# display cars
# -----------------------------
if not st.session_state.lock_selected:
    with base:
        st.header(
            "Wähle 5 Autos aus, um Versuche für ein Bremsweg-Modell durchzuführen!"
        )
        content = make_html(cars, st.session_state.selected)
        click_detector(content, key="car_selector")


# -----------------------------
# Button for confirmation
# -----------------------------
def click_confirmation():
    st.session_state.confirmed = True
    st.session_state.lock_selected = True


if len(st.session_state.selected) == 5 and not st.session_state.lock_selected:
    base.button("Führe Versuche durch", on_click=click_confirmation)

# -----------------------------
# Show GIFs for experiments
# -----------------------------

if st.session_state.confirmed and not st.session_state.show_plot:
    with base:
        # first show GIFs that demonstrate that the experiments have to be carried out
        st.markdown("### 🚦 Durchführung der Versuche...")

        placeholder = st.empty()
        for car in st.session_state.selected:
            car_type, car_velocity, gif_path = get_gif(car)
            with placeholder:
                with st.container(horizontal_alignment="center"):
                    st.image(gif_path, caption="")
                    st.markdown(
                        f"<h4 style='text-align: center'>{car_type.capitalize()} bei {car_velocity} km/h</h4>",
                        unsafe_allow_html=True,
                    )
            time.sleep(3)
        # show GIFs only once this only once
        st.session_state.show_plot = True
        st.rerun()

# -----------------------------
# train ML model
# -----------------------------

if st.session_state.confirmed and st.session_state.show_plot:
    # get training data
    selected_idx = [int(i) for i in st.session_state.selected]
    X_train = X[selected_idx]
    y_train = y[selected_idx]

    # create test data
    V, M, S = compute_test_data()
    # scale data
    VM_transformed, X_train_transformed = scale_data(V, M, X_train)
    # train model and predict grid with model
    y_pred, user_rmse = train_model_and_predict_grid(
        X_train_transformed, y_train, VM_transformed, S
    )
    # mask all negative values with zero
    y_pred[y_pred < 0] = 0

    # -----------------------------
    # plotting stuff
    # -----------------------------

    # compute scores for the first five points
    scores = compute_scores_for_cars(
        selected_cars=X_train_transformed[:5],
        selected_cars_label=y_train[:5],
        y_test=VM_transformed,
        y_true=S,
    )

    # Plots
    fig_user_model = plot_user_figure(V, M, S=y_pred, X_train=X_train, scores=scores)

    # handle progress logic of first and second additional selection
    first_car_confirmation = st.session_state.get("first_car_confirmation")
    if first_car_confirmation:
        st.session_state.additional_car_selection = 1
    second_car_confirmation = st.session_state.get("second_car_confirmation")
    if second_car_confirmation:
        st.session_state.additional_car_selection = 2

    # get onclick-event of plot
    selected_points = st.session_state.get("fig_user_model")

    # check if the selection changed
    if st.session_state.old_selection != selected_points:
        st.session_state.selection_changed = True
    else:
        st.session_state.selection_changed = False
    st.session_state.old_selection = selected_points

    # plot the nearest car to the selection of the user
    if selected_points is not None and len(selected_points["selection"]["points"]) > 0:
        # only cover one selected point
        point_x = selected_points["selection"]["points"][0]["x"]
        point_y = selected_points["selection"]["points"][0]["y"]
        nearest_car_index = search_nearest_unselected_car(X, point_x, point_y)
        nearest_car = cars[nearest_car_index]
        st.session_state.nearest_car = nearest_car
        datauri = img_to_datauri(nearest_car["path"])
        fig_user_model.add_trace(
            go.Scatter(
                x=[nearest_car["geschwindigkeit"]],
                y=[nearest_car["gewicht"]],
                mode="markers",
                marker=dict(
                    color="gray",
                    line=dict(width=3, color="white"),
                    size=20,
                    symbol="circle",
                ),
                name="Ausgewählter Punkt",
                showlegend=False,
                hoverinfo="skip",
                selected=dict(marker=dict(opacity=1)),  # bleibt voll sichtbar
                unselected=dict(marker=dict(opacity=1)),  # kein Verblassen
                zorder=2,
            )
        )

    # if the additional cars are selected and confirmed, deactivate the selection reload proces
    with base:
        if st.session_state.show_results:
            st.header("Ergebnis Übersicht")
            tab1, tab2 = st.tabs(["Trainiertes Modell", "Tatsächliches Ergebnis"])
            tab1.plotly_chart(
                fig_user_model, key="fig_user_model", config={"displayModeBar": False}
            )
            tab2.plotly_chart(
                plot_ground_truth(V, M, S, X_train),
                key="ground_truth",
                config={"displayModeBar": False},
            )
            error_print_user, error_print_al = st.columns(2)
            error_print_user.markdown(f"##### Dein Modellfehler: {user_rmse:.2f}%")
        elif st.session_state.additional_car_selection == 2:
            # render plot
            st.header("Modellvorhersage Bremsweg")
            st.plotly_chart(
                fig_user_model, key="fig_user_model", config={"displayModeBar": False}
            )
            st.markdown("#### Deine Auswahl:")
            placeholder = st.empty()
            with placeholder:
                col1, col2 = st.columns([0.22, 0.78], vertical_alignment="bottom")
            st.button("Zeig mir das Ergebnis!", on_click=show_results)
        else:
            # render plot
            st.header("Modellvorhersage Bremsweg")
            st.plotly_chart(
                fig_user_model,
                key="fig_user_model",
                on_select="rerun",
                config={"displayModeBar": False},
            )
            st.markdown(
                "##### Klicke in den Plot, um ein neues Auto auszuwählen. "
                "Führe dann den Versuch mit einem Klick auf das Auto durch"
            )
            placeholder = st.empty()
            with placeholder:
                col1, col2 = st.columns([0.22, 0.78])
            # define columns for the additional car_id selection

        # handle selection logic of the first and second additional car_id
        # additional_car_selection == 0 means no car_id is selected yet and we display just the nearest car_id
        if not st.session_state.show_results:
            if (
                selected_points is not None
                and st.session_state.additional_car_selection == 0
            ):
                nearest_car = st.session_state.nearest_car
                datauri = img_to_datauri(nearest_car["path"])
                with col1:
                    click_detector(
                        make_html_single_car(nearest_car, datauri),
                        key="first_car_confirmation",
                    )
            # additional_car_selection == 1 means the first car_id selection is confirmed
            if st.session_state.additional_car_selection >= 1:
                if "first_car" not in st.session_state:
                    first_car = st.session_state.nearest_car
                    st.session_state.first_car = first_car
                    st.session_state.selected.append(first_car["id"])
                    # show GIF for experiment
                    car_type, car_velocity, gif_path = get_gif(first_car["id"])
                    with placeholder:
                        with st.container():
                            st.image(gif_path)
                            st.markdown(
                                f"<h4 style='text-align: center'>{car_type.capitalize()} bei {car_velocity} km/h</h4>",
                                unsafe_allow_html=True,
                            )
                    time.sleep(3.5)
                    # rerun to deactivate GIF etc.
                    st.rerun()
                else:
                    first_car = st.session_state.first_car
                datauri = img_to_datauri(first_car["path"])
                with col1:
                    click_detector(
                        make_html_single_car(first_car, datauri, selected=True),
                        key="abc",
                    )
            # additional_car_selection == 1, and another selection is present means we display the second-nearest car_id
            if (
                selected_points is not None
                and st.session_state.additional_car_selection == 1
                and st.session_state.selection_changed
            ):
                nearest_car = st.session_state.nearest_car
                datauri = img_to_datauri(nearest_car["path"])
                with col2:
                    click_detector(
                        make_html_single_car(nearest_car, datauri),
                        key="second_car_confirmation",
                    )
            # additional_car_selection == 2 means both cars are confirmed
            if st.session_state.additional_car_selection == 2:
                if "second_car" not in st.session_state:
                    second_car = st.session_state.nearest_car
                    st.session_state.second_car = second_car
                    st.session_state.selected.append(second_car["id"])
                    # show GIF for experiment
                    car_type, car_velocity, gif_path = get_gif(second_car["id"])
                    with placeholder:
                        with st.container():
                            st.image(gif_path)
                            st.markdown(
                                f"<h4 style='text-align: center'>{car_type.capitalize()} bei {car_velocity} km/h</h4>",
                                unsafe_allow_html=True,
                            )
                    time.sleep(3.5)
                    # rerun to deactivate GIF etc.
                    st.rerun()
                else:
                    second_car = st.session_state.second_car
                datauri = img_to_datauri(second_car["path"])
                with col2:
                    click_detector(
                        make_html_single_car(second_car, datauri, selected=True),
                        key="bcd",
                    )
        else:
            # -----------------------------
            # Active Learning stuff
            # -----------------------------

            if not st.session_state.show_al_results:
                with base:
                    st.button("Was macht der Aktive Lerner?", on_click=show_al_results)
            else:
                with base:
                    st.header("Aktiver Lerner (KI)")

                # define tabs for Al plots
                with base:
                    al_tab1, al_tab2, al_tab3, al_tab4 = st.tabs(
                        [
                            "Modell Aktiver Lerner",
                            "Unsicherheit 1. Punkt",
                            "Unsicherheit 2. Punkt",
                            "Unsicherheit danach",
                        ]
                    )

                # get the points that an uncertainty-based active learner would query
                queried_points, uncertainty_grids = active_learner(
                    X_train_transformed[:5], y_train[:5], pool=cars
                )
                # add queried points to a separate training set
                X_train_al = np.append(X_train[:5], [queried_points[0][0]], axis=0)
                y_train_al = np.append(y_train[:5], queried_points[0][1])
                X_train_al = np.append(X_train_al, [queried_points[1][0]], axis=0)
                y_train_al = np.append(y_train_al, queried_points[1][1])

                # scale data
                _, X_train_al_transformed = scale_data(V, M, X_train_al)
                # train model and predict grid with the model
                y_pred_al, al_rmse = train_model_and_predict_grid(
                    X_train_al_transformed, y_train_al, VM_transformed, S
                )
                # mask all negative values with zero
                y_pred_al[y_pred_al < 0] = 0

                # plot al-model prediction
                with base:
                    with al_tab1:
                        st.plotly_chart(
                            plot_ground_truth(V, M, S=y_pred_al, X_train=X_train_al),
                            key="al_model",
                            config={"displayModeBar": False},
                        )
                    # plot uncertainties from first selection
                    with al_tab2:
                        st.plotly_chart(
                            plot_uncertainty(
                                V,
                                M,
                                unc=uncertainty_grids[0].reshape(M.shape),
                                X_train=X_train_al[:5],
                                selected=X_train_al[5],
                            ),
                            key="unc_1",
                            config={"displayModeBar": False},
                        )
                    # plot uncertainties from second selection
                    with al_tab3:
                        st.plotly_chart(
                            plot_uncertainty(
                                V,
                                M,
                                unc=uncertainty_grids[1].reshape(M.shape),
                                X_train=X_train_al[:6],
                                selected=X_train_al[6],
                            ),
                            key="unc_2",
                            config={"displayModeBar": False},
                        )
                    # plot uncertainties after the second selection
                    with al_tab4:
                        st.plotly_chart(
                            plot_uncertainty(
                                V,
                                M,
                                unc=uncertainty_grids[2].reshape(M.shape),
                                X_train=X_train_al[:7],
                            ),
                            key="unc_3",
                            config={"displayModeBar": False},
                        )

                    error_print_al.markdown(
                        f"##### Modellfehler Aktiver Lerner: {al_rmse:.2f}%"
                    )
                    # st.button("Reload")
                    # switch to leaderboard page
                    if st.button("Zum Leaderboard"):
                        # save the rmse of the user in the session-state so that the leaderboard can be updated
                        st.session_state.user_rmse = user_rmse
                        st.switch_page("leaderboard.py")

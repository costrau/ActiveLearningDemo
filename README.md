# Streamlit App - Active Learning Demonstrator (Bremsweg)

Dieser Demonstrator dient dazu die Notwendigkeit von Active Learning zu verdeutlichen.

Zum Entwickeln liegen die Quellcodes unter `src/`:

- `src/python_app/` — ursprüngliche Streamlit-App (`main.py`)
- `src/create_gif.py` — GIF-Erzeuger
- `src/deploy/` — FastAPI-Backend + statische Webseite

### Demonstrator lokal ausführen
1. Installiere die Bibliotheken (per editable install oder requirements):

```bash
pip install -e .
```

2. Erstelle die nötigen GIFs (optional, nur falls noch nicht vorhanden):

```bash
python src/create_gif.py
# oder mit uv wrapper: uv run python src/create_gif.py
```

3. Streamlit-Demo starten (falls du die original Streamlit-Oberfläche verwenden willst):

```bash
streamlit run src/python_app/main.py
# oder mit uv: uv run streamlit run src/python_app/main.py
```

Die Streamlit-App ist standardmäßig unter http://localhost:8501/ erreichbar.

## Static Frontend + FastAPI Backend

Es gibt jetzt ein separates Backend + statische Frontend unter `src/deploy/`.

Empfohlene Art zu starten (arbeitet aus dem Projekt-Root):

```bash
# mit uvicorn direkt und Angabe des App-Ordners
uvicorn server:app --reload --host 0.0.0.0 --port 8000 --app-dir src/deploy

# oder, falls du den uv-Wrapper nutzt:
uv run uvicorn server:app --reload --host 0.0.0.0 --port 8000 --app-dir src/deploy
```

Die statische Oberfläche ist dann unter http://localhost:8000/ erreichbar (der Server liefert `src/deploy/static/index.html`).

Hinweis: die `--app-dir src/deploy` Option sorgt dafür, dass der Uvicorn-Import und die statischen Dateien aus `src/deploy/` geladen werden.

---

## Deployment: Frontend/Backend Separation Example

To run the backend (FastAPI) and frontend (static HTML/JS) on different machines or servers:

### 1. Start the Backend (FastAPI)
On your backend server, run:

```bash
NO_STATIC=1 uvicorn server:app --host 0.0.0.0 --port 8000 --app-dir src/deploy
```
- This exposes the API at `http://<BACKEND_IP>:8000`.
- Make sure port 8000 is open and accessible from the frontend machine.

### 2. Host the Frontend
Copy the contents of `src/deploy/static/` to your web server (e.g., Nginx, Apache, Netlify, Vercel, or any static file host).

### 3. Configure the Frontend to Use the Backend
Edit `app.js` in your static files:

```
const BACKEND_HOST = 'http://<BACKEND_IP>:8000';
```
Replace `<BACKEND_IP>` with the actual IP or domain of your backend server.

### 4. Open the Frontend
Visit your hosted frontend in the browser. All API calls will be routed to the backend server.

---

**Example:**
- Backend runs on: `http://192.168.1.100:8000`
- Frontend is hosted at: `https://your-frontend-host.com/`
- In `app.js`:
  ```js
  const BACKEND_HOST = 'http://192.168.1.100:8000';
  ```

---

**Note:**
- Ensure CORS is enabled on the FastAPI backend (see FastAPI docs for `fastapi.middleware.cors`).
- The backend must be reachable from the client browser.
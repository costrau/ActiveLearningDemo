# Streamlit App - Active Learning Demonstrator (Bremsweg)

Dieser Demonstrator dient dazu die Notwendigkeit von Active Learning zu verdeutlichen.

Zum Manageen von Abhängigkeiten wird uv benutzt. Die Installation funktioniert auch mit pip.

### Demonstrator zum Laufen bringen
1. Installiere die Bibliotheken: `pip install -e .` Ist uv installiert, wird `uv sync` bevorzugt.
2. Erstelle die nötigen Dateien (GIFs): `uv run python src/create_gif.py`
3. Starte den Demonstrator mit dem Befehl: `uv run streamlit run src/python_app/main.py`
4. Dein Browser sollte sich automatisch öffnen. Ansonsten rufe http://localhost:8501/ auf.

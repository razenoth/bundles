dev:
FLASK_APP=run.py FLASK_ENV=development flask run

test:
pytest -q

lint:
ruff check .

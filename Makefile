.PHONY: install install-dev run seed migrate test test-unit coverage clean worker

install:
	python -m venv venv
	./venv/bin/pip install -r requirements.txt

install-dev: install
	./venv/bin/pip install -r requirements-dev.txt

run:
	FLASK_APP=wsgi.py ./venv/bin/flask run --debug

seed:
	./venv/bin/python scripts/seed.py

migrate:
	FLASK_APP=wsgi.py ./venv/bin/flask db init || true
	FLASK_APP=wsgi.py ./venv/bin/flask db migrate -m "$(m)"
	FLASK_APP=wsgi.py ./venv/bin/flask db upgrade

worker:
	./venv/bin/python worker.py

test:
	./venv/bin/pytest

test-unit:
	./venv/bin/pytest tests/unit

coverage:
	./venv/bin/pytest --cov=app/services --cov-report=term-missing --cov-report=html

clean:
	rm -rf venv __pycache__ .pytest_cache .coverage htmlcov *.db
venv:
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt

format:
	venv/bin/pip install -r requirements-tests.txt
	venv/bin/black --verbose src
	venv/bin/flake8 src

format/check:
	venv/bin/pip install -r requirements-tests.txt
	venv/bin/black --verbose src --check
	venv/bin/flake8 src

run: venv
	PYTHONPATH=src venv/bin/python src/main.py

tests: venv format/check
	venv/bin/pip install -r requirements-tests.txt
	PYTHONPATH=src venv/bin/pytest src/tests

docker/build:
	docker build --no-cache	--tag=aimbot .

docker/tests:
	 docker run aimbot /bin/sh -c 'make tests'
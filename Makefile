.PHONY: lint test build format all update-requirements lint-fix install-dev

PYTHON := python3.12

tests_dir := tests

package := plutarch
package_dir := src/plutarch
setup := $(PYTHON) setup.py

PYTEST_COMMAND := $(PYTHON) -m pytest --cov=. --cov-fail-under=$(coverage_percent) --import-mode=importlib --cov-config=pyproject.toml --cov-report=xml:coverage.xml --cov-report=term-missing --cov-branch $(package_dir) $(tests_dir)
PIP_COMPILE := $(PYTHON) -m piptools compile --resolver=backtracking --no-emit-find-links --no-allow-unsafe --no-header --strip-extras --no-emit-index-url -q --no-emit-trusted-host


all: install-reqs lint test format build install-dev

update-requirements: 
	$(PIP_COMPILE) --upgrade --output-file=requirements-dev.txt $(DEV_INPUT_REQS)
	$(PIP_COMPILE) --upgrade --output-file=requirements.txt $(INPUT_REQS)

lint:
	$(PYTHON) -m ruff check $(package_dir)
	$(PYTHON) -m ruff check $(tests_dir)
	$(PYTHON) -m ruff format --check $(package_dir)
	$(PYTHON) -m ruff format --check $(tests_dir)

lint-fix:
	$(PYTHON) -m ruff check --fix-only -e $(package_dir)
	$(PYTHON) -m ruff check --fix-only -e $(tests_dir)
	$(PYTHON) -m ruff format -q $(package_dir)
	$(PYTHON) -m ruff format -q $(tests_dir)

build:
	$(setup) build
	$(PYTHON) setup.py sdist
	$(PYTHON) setup.py bdist_wheel

install-reqs: update-requirements
	$(PYTHON) -m pip install -r requirements-dev.txt -r requirements.txt
	
install-dev:
	$(PYTHON) -m pip install -e .

test:
	$(PYTEST_COMMAND)
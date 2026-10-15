VENV := .venv
TIMESTAMP := $(VENV)/.last_sync
PYTHON_VERSION := 3.13

.PHONY: .check-deps bootstrap clean format check test

.check-deps:
	@command -v git >/dev/null 2>&1 || { echo "Error: 'git' is not installed or not in PATH." >&2; exit 1; }
	@command -v uv >/dev/null 2>&1 || { echo "Error: 'uv' is not installed or not in PATH." >&2; exit 1; }

$(VENV): | .check-deps
	@if [ ! -d "$(VENV)" ]; then \
		uv venv --python $(PYTHON_VERSION) $(VENV); \
	fi

$(TIMESTAMP): pyproject.toml uv.lock | $(VENV)
	uv sync --all-groups
	uv run python -c "from pathlib import Path; p=Path('$(TIMESTAMP)'); p.parent.mkdir(parents=True, exist_ok=True); p.touch()"

bootstrap: $(TIMESTAMP)

clean:
	@# Remove .venv cross-platform (prefer Python if available, fallback to rm)
	@if command -v python3 >/dev/null 2>&1; then \
		python3 -c "import shutil; shutil.rmtree('.venv', ignore_errors=True)"; \
	elif command -v py >/dev/null 2>&1; then \
		py -3 -c "import shutil; shutil.rmtree('.venv', ignore_errors=True)"; \
	elif command -v python >/dev/null 2>&1; then \
		python -c "import shutil; shutil.rmtree('.venv', ignore_errors=True)"; \
	else \
		rm -rf .venv; \
	fi
	@# Clean untracked files but keep .venv if present
	git clean -fdx -e .venv

setup-db: bootstrap
	@if ! command -v psql; then echo "psql command missing" && exit 1; fi
	@if ! command -v createdb; then echo "createdb command missing" && exit 1; fi
	psql -h 127.0.0.1 -p 5432 -U twin4dem -tAc "SELECT 1 FROM pg_database WHERE datname='twin4dem'" | grep -q 1 \
		|| createdb -h 127.0.0.1 -p 5432 -U twin4dem twin4dem

migrations: setup-db
	uv run python src/manage.py makemigrations

db-from-scratch: migrations
	uv run python src/manage.py migrate common "zero"
	uv run python src/manage.py migrate common

su: migrations
	uv run python src/manage.py createsuperuser --username admin

format: bootstrap
	uv run black --fast .
	uv run ruff check --fix .

check: bootstrap
	uv run black --check .
	uv run ruff check .

test: bootstrap
	uv run pytest -rA -vvs --log-level INFO tests/

jupyter: bootstrap
	uv run python -m ipykernel install --user --name twin4dem
	uv run jupyter notebook notebooks/stats-demo.ipynb
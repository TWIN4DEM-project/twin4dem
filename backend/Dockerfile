FROM python:3.13-alpine AS backend_base

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# system deps
RUN apk add --no-cache build-base libffi-dev openssl-dev postgresql-client postgresql-dev

WORKDIR /backend

# uv lock dependencies
COPY backend/uv.lock backend/pyproject.toml ./
RUN pip install --no-cache-dir uv && uv sync --frozen

# ------------------------------------------------------------
# dev stage
# ------------------------------------------------------------
FROM backend_base AS backend_dev

# copy the project
COPY backend/src ./src
COPY backend/script ./script
COPY assets ../assets

EXPOSE 8000
CMD ["sh", "./script/server"]

# ------------------------------------------------------------
# test stage
# ------------------------------------------------------------
FROM backend_base AS test

COPY backend/src ./src
COPY backend/tests ./tests

# pytest uses uv environment
CMD ["uv", "run", "pytest", "-q"]

# ------------------------------------------------------------
# prod build stage – copies frontend dist from frontend_prod image
# ------------------------------------------------------------
FROM backend_base AS backend_prod

# bring backend
COPY backend/src ./src

CMD ["uv", "run", "celery", "worker", "-A", "twin4dem", "-l", "info"]

FROM backend_prod AS web_prod

ENV TWIN4DEM_BACKEND_VITE_DEV_MODE=False

COPY assets ../assets
COPY --from=frontend_prod /opt/twin4dem/frontend ../assets/frontend/

# collectstatic (into ../assets)
RUN uv run python src/manage.py compilescss && \
    uv run python src/manage.py collectstatic --no-input

EXPOSE 8000
CMD ["uv", "run", "daphne", "twin4dem.asgi:application", "--bind", "0.0.0.0"]
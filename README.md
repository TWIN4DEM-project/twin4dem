# 🌀 Twin4dem

TWIN4DEM is an innovative European research project dedicated to strengthening
democratic resilience through cutting-edge Computational Social Science (CSS)
and digital twin technology.
By combining expertise from diverse fields – social sciences, humanities, and
advanced computational methods – TWIN4DEM aims to uncover the pathways behind
democratic backsliding and provide actionable solutions to policymakers, civil
society, and technology providers.

The digital twin is a Django + React application that uses WebSockets, Celery
workers, Redis, RabbitMQ, and PostgreSQL.
This guide helps you run the full stack locally using **Docker Compose** — no
prior Docker experience required.

---

## 📂 Project Structure

```
.
├── backend/                 # Django + Channels + Celery + Daphne
│   ├── Dockerfile
│   ├── src/
│   ├── static/
│   └── tests/
├── frontend/                # React + Vite (prod build in dist/; copied automatically to backend)
│   ├── Dockerfile
│   ├── src/
│   ├── assets/
│   └── dist/
├── docker-compose.common.yaml   # shared networks + db + redis + broker
├── docker-compose.dev.yaml      # development stack
├── docker-compose.prod.yaml     # production validation stack
└── docker-bake.hcl              # production image build graph (frontend_prod, backend_prod)
```

---

# 🚀 Quickstart (Development)

To run the **backend + frontend + all required services** for development:

### 1. Install Docker Desktop  
https://www.docker.com/products/docker-desktop/

### 2. Start the dev stack

```sh
docker compose -f docker-compose.dev.yaml up --build
```

This will start:

| Service     | Description                                     |
|-------------|-------------------------------------------------|
| `frontend`  | Vite dev server (hot reload, React + TS)        |
| `backend`   | Django dev server + Celery worker (combined)    |
| `db`        | PostgreSQL 16                                   |
| `broker`    | RabbitMQ (Celery broker)                        |
| `redis`     | Redis (Channels layer)                          |

Once running:

- **Frontend:** http://localhost:3000/static
- **Backend:** http://localhost:8000

Changes to backend or frontend code update automatically. You only need to open
http://localhost:8000 in the browser.

**Note**: you will need to set up an `admin` user account. This is easily done
via the `python src/manage.py createsuperuser` command. The command can be
executed from anywhere against Django's database. 

---

# 🧪 Running Unit Tests

Both the `frontend` and the `backend` have unit tests. Both can be run by
building their respective Docker image stages.

### Build the test image

For the backend:
```sh
docker build -f backend/Dockerfile --target test -t backend-test .
```

For the frontend:

```sh
docker build -f frontend/Dockerfile --target test -t frontend-test .
```

### Run the tests

```sh
docker run -it backend-test && docker run -it frontend-test
```

# 🏭 Validating Production Builds Locally

We **do not** deploy via Docker Compose, but we **do** use Compose to validate
that production images behave correctly.

### Step 1: Build production images using BuildKit Bake

```sh
docker buildx bake
```

This builds:

- `frontend_prod`
- `backend_prod`

based on the dependency graph defined in `docker-bake.hcl`.

### Step 2: Run the production stack

```sh
docker compose -f docker-compose.prod.yaml up --build
```

The stack uses:

- `frontend_prod` → prebuilt React bundle (`dist/`)
- `backend_prod`  → Daphne production ASGI server
- Celery worker
- PostgreSQL / Redis / RabbitMQ

This is ideal for CI/CD and local validation.

---

# 🧱 Components Overview

## 🟦 Frontend (React + Vite)

- React + TypeScript
- Hot-reload in dev via Vite
- Production build created with `npm run build`
- Build artifacts copied into backend image for deployment

## 🟥 Backend (Django + Channels + Celery)

- Django 5 ASGI application
- Channels for WebSockets
- Celery for background tasks
- Redis as channel layer
- RabbitMQ as Celery AMQP broker
- PostgreSQL as primary database

## 🗄 PostgreSQL (`db`)

- Stores all persistent backend data  
- Exposed on port `5432`

## ✉️ RabbitMQ (`broker`)

- Handles Celery task distribution  
- Exposed on port `5672`

## ⚡ Redis (`redis`)

- Channels layer backend  
- Also useful for caching or ephemeral data

---

# 📚 Development Tips

Rebuild backend when Python dependencies change:

```sh
docker compose build backend
```

Rebuild frontend when JS/TS dependencies change:

```sh
docker compose build frontend
```

Clear containers & volumes:

```sh
docker compose down -v
```

View logs:

```sh
docker compose logs -f backend
```

---

# 🤝 Contributing

Contributions are welcome! Make sure you read our code of conduct.  
Please open an issue or PR if you'd like to improve documentation, fix bugs, or
add features.


# Network Labs

An interactive network simulation lab built with a **FastAPI** backend, **Vite** (JavaScript) frontend, and **PostgreSQL** database, orchestrated with **Docker Compose**. Build network topologies, manage devices and connections, run simulations in real time via WebSocket, and track lab progress — all through a clean REST + WebSocket API.

---

## Features

- **Interactive network topology builder** — create and manage labs with custom topologies
- **Real-time simulation** via WebSocket (`/ws/simulation/{simulation_id}`)
- **Device & connection management** — add, update, and remove network devices and links
- **Lab progress tracking** — record and query completion progress per lab
- **REST API + WebSocket API** — fully documented with Swagger UI and ReDoc
- **Database migrations** with Alembic — applied automatically on startup
- **Auto-seeding of lab data** — initial lab content populated on first run

---

## Prerequisites

| Requirement | Version |
|---|---|
| [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/) (or Docker Desktop) | Docker ≥ 24, Compose ≥ 2 |
| [Git](https://git-scm.com/) | any recent version |

> **For running services outside Docker (optional):**
> - Python 3.11+
> - Node.js 18+

---

## Project Structure

```
.
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── engine/
│   │   ├── main.py
│   │   ├── models/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── seed/
│   │   └── services/
│   ├── requirements.txt
│   └── tests/
├── db/
│   └── init.sql
└── frontend/
    └── (Vite-based JS app)
```

---

## Running Locally (with Docker Compose)

### 1. Clone the repository

```bash
git clone https://github.com/ralphwright/network-labs.git
cd network-labs
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and customise the values. At minimum, generate a strong `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Replace the `SECRET_KEY` placeholder in `.env` with the output.

### 3. Start all services

```bash
docker compose up --build
```

**What happens on startup:**

1. PostgreSQL (`db`) starts and passes its health check.
2. The `backend` service starts; the lifespan handler runs `alembic upgrade head` (migrations) then seeds initial lab data.
3. The `frontend` service starts once the backend is healthy.

### 4. Access the application

| Service | URL |
|---|---|
| Frontend | <http://localhost:3000> |
| Backend API | <http://localhost:8000> |
| Swagger UI (API docs) | <http://localhost:8000/docs> |
| ReDoc | <http://localhost:8000/redoc> |
| Health check | <http://localhost:8000/health> |
| WebSocket | `ws://localhost:8000/ws/simulation/{simulation_id}` |

### 5. Stop the application

```bash
# Stop containers, keep database volume
docker compose down

# Stop containers AND remove the database volume
docker compose down -v
```

---

## Running Without Docker (Manual Setup)

Use this approach for local development when you want faster iteration without rebuilding images.

### Database

1. Install and start **PostgreSQL 16**.
2. Create the database and user to match your `.env`:

```sql
CREATE USER labuser WITH PASSWORD 'labpassword';
CREATE DATABASE network_labs OWNER labuser;
```

3. Optionally run the initialisation script:

```bash
psql -U labuser -d network_labs -f db/init.sql
```

### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Point the backend at your local Postgres instance
export POSTGRES_HOST=localhost
# (set the remaining variables from .env as needed)

# Apply database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install

# Set API URLs (adjust if your backend runs on a different host/port)
export VITE_API_URL=http://localhost:8000
export VITE_WS_URL=ws://localhost:8000

npm run dev
```

The frontend dev server will be available at <http://localhost:5173>.

---

## Deployment

### Environment variables (production)

Before deploying, harden your `.env` (or your secret management system):

| Variable | Production guidance |
|---|---|
| `SECRET_KEY` | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` — never use the default |
| `DEBUG` | Set to `false` |
| `CORS_ORIGINS` | Restrict to your production frontend domain, e.g. `https://app.example.com` |
| `POSTGRES_PASSWORD` | Use a strong, unique password |

### Docker Compose (production)

Run in detached mode:

```bash
docker compose up --build -d
```

For production, consider removing `--reload` from the `command` in `docker-compose.yml` (or override it via an environment-specific compose file):

```yaml
command: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Reverse proxy (recommended)

Place **Nginx** or **Traefik** in front of the services to handle TLS/SSL termination and route traffic. Update the following variables to match your domain and scheme:

- `VITE_API_URL` — e.g. `https://api.example.com`
- `VITE_WS_URL` — e.g. `wss://api.example.com`
- `CORS_ORIGINS` — e.g. `https://app.example.com`

### Cloud deployment options

| Approach | Notes |
|---|---|
| **VPS with Docker Compose** | Copy the project to a VPS, set up a reverse proxy, run `docker compose up -d` |
| **AWS ECS / Fargate** | Push images to ECR; define task definitions for each service; use RDS for PostgreSQL |
| **Google Cloud Run** | Deploy each service as a Cloud Run service; use Cloud SQL for PostgreSQL |
| **Azure Container Apps** | Deploy containers from ACR; use Azure Database for PostgreSQL |
| **Kubernetes** | Write Helm charts or Kubernetes manifests for each service; use a managed PostgreSQL service |

> **Note:** In cloud environments, replace the `db` service with a managed PostgreSQL service (RDS, Cloud SQL, Azure Database for PostgreSQL, etc.) for reliability and easier maintenance.

---

## Running Tests

**With Docker Compose (recommended):**

```bash
docker compose exec backend pytest
```

**Locally (inside the backend virtual environment):**

```bash
cd backend
pytest
```

---

## API Reference

Interactive API documentation is available when the backend is running:

| Interface | URL |
|---|---|
| Swagger UI | <http://localhost:8000/docs> |
| ReDoc | <http://localhost:8000/redoc> |

---

## Environment Variables

All variables are defined in `.env.example`. Copy it to `.env` and adjust before running.

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_DB` | PostgreSQL database name | `network_labs` |
| `POSTGRES_USER` | PostgreSQL username | `labuser` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `labpassword` |
| `POSTGRES_HOST` | PostgreSQL host (use `db` in Docker, `localhost` outside) | `db` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `DATABASE_URL` | Full async database URL (constructed from the variables above) | `postgresql+asyncpg://labuser:labpassword@db:5432/network_labs` |
| `SECRET_KEY` | Secret key for JWT signing — **change this in production** | *(insecure placeholder)* |
| `BACKEND_HOST` | Host the backend binds to | `0.0.0.0` |
| `BACKEND_PORT` | Port the backend listens on | `8000` |
| `DEBUG` | Enable debug mode | `true` |
| `VITE_API_URL` | Frontend API base URL | `http://localhost:8000` |
| `VITE_WS_URL` | Frontend WebSocket base URL | `ws://localhost:8000` |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:3000,http://localhost:5173` |

---

## License

This project is not yet licensed. See the repository for updates.
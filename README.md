# 🎮 PC Club Booking System (API)

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-316192?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.3-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Pytest](https://img.shields.io/badge/Pytest-Coverage_79%25-green?logo=pytest&logoColor=white)](https://pytest.org/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)

A scalable RESTful API backend for managing a PC / Cyber-club. The system provides a complete lifecycle for infrastructure management (gaming zones, PCs) and seat booking, with built-in overlap protection, async email notifications, and secure multi-strategy authentication.

---

## 🚀 Key Features

### Auth & Security
- **JWT Authentication** — access + refresh token pair with UUID-based jti claim
- **Refresh Token Rotation** — every refresh call invalidates the old token and issues a new pair, preventing token reuse attacks
- **Google OAuth2** — one-click sign-in via Google; new accounts are provisioned automatically on first login
- **bcrypt** password hashing with strict Pydantic validation on registration

### Booking Engine
- **Anti-Overlap Protection** — time conflict validation at both the service and database levels
- **Pessimistic Locking** — `SELECT FOR UPDATE` on the target PC row eliminates race conditions under concurrent requests
- **`GET /pcs/available`** — find free PCs filtered by zone and time window in a single query
- **Financial Tracking** — session cost calculated automatically from zone hourly rate using `Decimal` precision

### Background Tasks (Celery + Redis)
- **Celery Beat** scheduler marks expired bookings every minute and frees up PCs
- **Email notifications** sent asynchronously via Celery task on booking creation

### Infrastructure & Quality
- **Role-Based Access Control (RBAC)** — regular users book PCs; administrators manage zones and hardware
- **CORS + Pagination** on all list endpoints
- **Pydantic validators** reject past-start and micro-duration bookings at schema level
- **79% test coverage** — integration tests for auth, booking flow, overlap edge cases, OAuth, refresh rotation, available PCs endpoint, and Celery tasks
- **CI/CD via GitHub Actions** — automated test run with isolated PostgreSQL service on every push

---

## 🏗 Database Architecture

![DB Schema]<img width="1241" height="527" alt="Screenshot 2026-03-31 211731" src="https://github.com/user-attachments/assets/76780cc0-487a-44d2-a661-0008ae4419f2" />

**Core Entities:**

| Entity | Description |
|---|---|
| **Users** | Gamer and administrator accounts; supports both password and OAuth login |
| **Zones** | Gaming areas (e.g. "General", "VIP") with individual hourly rates |
| **PCs** | Individual machines linked to a zone and identified by MAC address |
| **Bookings** | Transactions linking user ↔ PC ↔ time window ↔ calculated cost |

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI (async) |
| ORM & Driver | SQLAlchemy 2.0 (async) + asyncpg |
| Database | PostgreSQL 15 |
| Task Queue | Celery 5 + Redis (broker & result backend) |
| Migrations | Alembic |
| Auth | python-jose, passlib[bcrypt], Authlib (OAuth) |
| Testing | pytest, httpx, pytest-asyncio, pytest-cov |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

---

## ⚙️ Local Setup (Docker)

You only need **Docker** and **Docker Compose** installed.

**1. Clone the repository:**
```bash
git clone https://github.com/bogdankirich/fast_api_pc_booking_system.git
cd fast_api_pc_booking_system
```

**2. Set up environment variables:**
```bash
cp .env.example .env
# Fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SMTP settings, etc.
```

**3. Start all containers:**
```bash
docker compose up --build -d
```

**4. Verify:**
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`

---

## 🧪 Running Tests

Tests run in an isolated environment with a dedicated test database:

```bash
docker compose exec web pytest -v --cov=app --cov-report=term
```

---

## 📂 Project Structure

The project follows clean layered architecture:

```
app/
├── api/endpoints/     # Routers — HTTP request handling
├── services/          # Business logic (calculations, validations)
├── repositories/      # Repository pattern — isolated SQL queries
├── models/            # SQLAlchemy ORM models
├── schemas/           # Pydantic schemas (validation & serialization)
└── tasks/             # Celery background tasks (expiry, email)
tests/                 # Integration & unit tests
.github/workflows/     # GitHub Actions CI pipeline
```

---

## 📡 API Overview

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `POST` | `/auth/register` | Public | Register a new user |
| `POST` | `/auth/login` | Public | Get access + refresh tokens |
| `POST` | `/auth/refresh` | Public | Rotate refresh token |
| `GET` | `/auth/google/login` | Public | Redirect to Google OAuth |
| `GET` | `/auth/google/callback` | Public | Handle OAuth callback |
| `GET` | `/users/me` | User | Get current user profile |
| `GET` | `/zones` | User | List all zones (paginated) |
| `POST` | `/zones` | Admin | Create a zone |
| `GET` | `/pcs` | User | List all PCs |
| `GET` | `/pcs/available` | User | Find free PCs by zone + time |
| `POST` | `/pcs` | Admin | Add a PC |
| `GET` | `/bookings` | User | List own bookings |
| `POST` | `/bookings` | User | Create a booking |
| `DELETE` | `/bookings/{id}` | User/Admin | Cancel a booking |

---

## 🔮 Roadmap

- [ ] LiqPay payment integration
- [ ] Telegram bot notifications
- [ ] Admin dashboard statistics endpoint

---

## 📬 Contact

**Bohdan Kirichenko** — Python Backend Developer  
📧 [bogdankirich1337@gmail.com](mailto:bogdankirich1337@gmail.com) · [LinkedIn](https://www.linkedin.com/in/bogdan-kirichenko-a8486b333/)

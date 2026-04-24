# 🎮 PC Club Booking System (API)

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-316192?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.3-37814A?logo=celery&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-Coverage_79%25-green?logo=pytest&logoColor=white)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)

A scalable RESTful API backend for managing a PC/Cyber club. The system provides a complete lifecycle for infrastructure management (gaming zones, PCs) and seat booking with built-in overlapping protection.

## 🚀 Key Features

* **Secure Authentication:** JWT-based authentication with secure password hashing.
* **Role-Based Access Control (RBAC):** Strict access separation. Regular users can book PCs, while Administrators manage zones and hardware.
* **Smart Booking (Anti-Overlap):** Time validation on both business logic and database levels. The system prevents double-booking of a single PC for the same time slot.
* **Financial Tracking:** Automatic session cost calculation based on the specific gaming zone's hourly rate using precise `Decimal` types.
* **Background Tasks:** Asynchronous `Celery Beat` scheduler checks for expired sessions every minute and automatically updates their status to free up the PCs.
* **CI/CD Pipeline:** Automated testing, code coverage checks, and linting on every push to the `master` branch via GitHub Actions.

## 🏗 Database Architecture

![DB Schema] <img width="1217" height="482" alt="db_schema" src="https://github.com/user-attachments/assets/770f83b2-9c5e-463b-9310-9287b64f7fa5" />


**Core Entities:**
1. **Users:** Accounts for gamers and administrators.
2. **Zones:** Gaming areas (e.g., "General", "VIP") with different hourly rates.
3. **PCs:** Individual computers linked to a specific zone and MAC address.
4. **Bookings:** Booking transactions linking a user, a PC, timeframes, and total cost.

## 🛠 Tech Stack

* **Framework:** FastAPI (Asynchronous framework)
* **ORM & Database:** SQLAlchemy 2.0 (Async) + asyncpg + PostgreSQL 15
* **Task Queue:** Celery + Redis (Broker & Result Backend)
* **Migrations:** Alembic
* **Testing:** Pytest + httpx + pytest-asyncio + pytest-cov
* **Infrastructure:** Docker, Docker Compose, GitHub Actions

## ⚙️ Local Setup (Docker)

You only need `Docker` and `Docker Compose` installed on your machine to run this project.

**1. Clone the repository:**
```bash
git clone [https://github.com/bodankirich/fast_api_pc_booking_system.git](https://github.com/bodankirich/fast_api_pc_booking_system.git)
cd fast_api_pc_booking_system
```

**2. Set up environment variables:**
Create a `.env` file in the root directory and copy the settings from the `.env.example` template.
```bash
cp .env.example .env
```

**3. Run the containers:**
```bash
docker compose up --build -d
```

**4. Verify the deployment:**
* API is available at: `http://localhost:8000`
* Interactive Swagger UI documentation: `http://localhost:8000/docs`

## 🧪 Running Tests

Tests run in an isolated container with a dedicated test database, covering endpoints and business logic integration.

```bash
docker compose exec web pytest -v --cov=app --cov-report=term
```

## 📂 Project Structure (Layered Architecture)

The project strictly follows clean layered architecture principles:
* `app/api/endpoints` — Routers (Controllers), HTTP request handling.
* `app/services` — Isolated business logic (calculations, validations).
* `app/repositories` — Repository pattern to isolate SQL queries.
* `app/models` — SQLAlchemy ORM models.
* `app/schemas` — Pydantic models (data validation).
* `app/tasks` — Celery background tasks. 

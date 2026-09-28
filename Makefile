.PHONY: up down logs migrate test test-backend test-frontend lint

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose run --rm backend alembic upgrade head

test: test-backend test-frontend

test-backend:
	cd backend && .venv/bin/python -m pytest -v

test-frontend:
	cd frontend && npm test -- --run

lint:
	cd backend && .venv/bin/python -m compileall -q app tests
	cd frontend && npm run lint


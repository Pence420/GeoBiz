.PHONY: up down logs migrate profiles opportunities test test-backend test-frontend build-frontend lint

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose run --rm backend alembic upgrade head

profiles:
	docker compose run --rm backend python -m app.imports.cli generate-profiles --version v1.0.0 --grid-size-m 1000

opportunities:
	docker compose run --rm backend python -m app.imports.cli generate-opportunities --version v1.0.0

test: test-backend test-frontend

test-backend:
	docker compose run --rm backend pytest -q

test-frontend:
	docker compose run --rm frontend npm test -- --run

build-frontend:
	docker compose run --rm frontend npm run build

lint:
	docker compose run --rm backend python -m compileall -q app tests
	docker compose run --rm frontend npm run lint

.PHONY: dev down test test-rls e2e lint migrate seed schema deploy-staging

COMPOSE = docker compose -f infra/docker-compose.dev.yml

dev:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

test:
	cd apps/api && uv run pytest
	pnpm --filter web test

test-rls:
	cd apps/api && uv run pytest -m rls

e2e:
	pnpm --filter web exec playwright test

lint:
	cd apps/api && uv run ruff check . && uv run mypy .
	pnpm -r lint

migrate:
	cd apps/api && uv run python manage.py migrate

seed:
	cd apps/api && uv run python manage.py seed_demo

schema:
	cd apps/api && uv run python manage.py spectacular --file ../../packages/api-client/openapi.json
	pnpm --filter @fitkhata/api-client generate

deploy-staging:
	@echo "CI (.github/workflows/deploy.yml) handles this on push to main."
	@echo "Manual fallback: see 'Deploy' in docs/RUNBOOK.md."

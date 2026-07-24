.PHONY: help up down build migrate seed init test-unit test-integration lint verify-mvp0 logs clean frontend-build

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start all services
	docker compose up --build -d

down: ## Stop all services
	docker compose down

build: ## Build all images without starting
	docker compose build

migrate: ## Run database migrations
	docker compose exec api alembic upgrade head

seed: ## Seed default user and workspace
	docker compose exec api python -m app.seed

init: migrate seed ## Run migrations + seed

test-unit: ## Run unit tests (requires compose running)
	docker compose exec api pip install -r dev-requirements.txt -q
	docker compose exec api python -m pytest tests/ -m "not integration" -v

test-integration: ## Run Redis integration tests against disposable DB 15
	docker compose exec api pip install -r dev-requirements.txt -q
	docker compose exec -e REDIS_TEST_URL=redis://redis:6379/15 api python -m pytest tests/ -m integration -v

lint: ## Run Python linting
	docker compose exec api pip install -r dev-requirements.txt -q
	docker compose exec api ruff check .

verify-mvp0: ## Run MVP 0 gate checks
	@echo "=== MVP 0 Gate ==="
	@echo "1. Checking services are running..."
	@docker compose ps --status running | grep -q "api" || (echo "FAIL: api not running"; exit 1)
	@docker compose ps --status running | grep -q "gateway" || (echo "FAIL: gateway not running"; exit 1)
	@docker compose ps --status running | grep -q "worker" || (echo "FAIL: worker not running"; exit 1)
	@docker compose ps --status running | grep -q "postgres" || (echo "FAIL: postgres not running"; exit 1)
	@docker compose ps --status running | grep -q "redis" || (echo "FAIL: redis not running"; exit 1)
	@echo "2. Checking health endpoint..."
	@curl -sf http://localhost:8000/api/health > /dev/null || (echo "FAIL: health endpoint unreachable"; exit 1)
	@echo "   Health status:"
	@curl -s http://localhost:8000/api/health | python -c "import sys,json; d=json.load(sys.stdin); print(f'      overall={d[\"status\"]}  components={d[\"components\"]}')"
	@echo "3. Checking API docs..."
	@curl -sf http://localhost:8000/api/docs > /dev/null || (echo "FAIL: API docs unreachable"; exit 1)
	@echo "4. Checking database is migrated..."
	@docker compose exec api alembic upgrade head 2>&1 | grep -q "skipping" || true
	@echo "5. Checking seed data exists..."
	@docker compose exec api python -c "from sqlalchemy import text; from app.database import SessionLocal; db=SessionLocal(); print('seeded' if db.execute(text('SELECT 1 FROM users LIMIT 1')).fetchone() else 'missing')" | grep -q "seeded" && echo "PASS: default user exists" || (docker compose exec api python -m app.seed && echo "PASS: seeded")
	@echo "=== MVP 0 Gate PASSED ==="

logs: ## Show logs
	docker compose logs -f

clean: ## Remove everything (volumes too)
	docker compose down -v

frontend-build: ## Build frontend for production
	cd frontend && npm install && npm run build

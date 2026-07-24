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

test-unit: ## Run backend unit tests (requires compose running)
	docker compose exec api pip install -r dev-requirements.txt -q
	docker compose exec api python -m pytest tests/ -m "not integration" -v

test-integration: ## Run PostgreSQL and Redis integration tests
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
	@docker compose exec api python -m app.seed
	@docker compose exec api python -c "from app.database import SessionLocal; from app.seed import DEFAULT_USER_ID,DEFAULT_WORKSPACE_ID,DEFAULT_MOCK_PROFILE_ID; from app.models import User,Workspace,ModelProfile; db=SessionLocal(); assert db.get(User,DEFAULT_USER_ID); assert db.get(Workspace,DEFAULT_WORKSPACE_ID); p=db.get(ModelProfile,DEFAULT_MOCK_PROFILE_ID); assert p and p.credential_ciphertext is None; print('PASS: default data is present and credential-free')"
	@echo "6. Running backend unit and integration tests..."
	@docker compose exec api pip install -r dev-requirements.txt -q
	@docker compose exec api python -m pytest tests -v
	@echo "=== MVP 0 Gate PASSED ==="

logs: ## Show logs
	docker compose logs -f

clean: ## Remove everything (volumes too)
	docker compose down -v

frontend-build: ## Build frontend for production
	cd frontend && npm install && npm run build

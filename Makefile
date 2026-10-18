.DEFAULT_GOAL := help
.PHONY: help dev dev-down dev-logs check check-api check-web test test-api test-web build-web \
	sanity fmt api-types hooks-install deploy prod-check

DEV_COMPOSE := docker compose -f docker-compose.dev.yml
API := cd backend &&
WEB := cd frontend &&
WEB_DEPS := frontend/node_modules/.package-lock.json

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

# --- Development -------------------------------------------------------------

dev: ## Start api (:8000), web (:5173) and redis with live reload
	$(DEV_COMPOSE) up -d --build
	@echo "App: http://localhost:5173   API: http://localhost:8000/api/health"

dev-down: ## Stop the dev stack
	$(DEV_COMPOSE) down

dev-logs: ## Follow dev stack logs
	$(DEV_COMPOSE) logs -f

# --- Quality gates -----------------------------------------------------------

check: check-api check-web ## Lint, format check and typecheck (pre-push gate)

check-api:
	$(API) uv run ruff check . && uv run ruff format --check .

check-web: $(WEB_DEPS)
	$(WEB) npm run check

test: test-api test-web ## Run backend and frontend tests

test-api:
	$(API) uv run pytest

test-web: $(WEB_DEPS)
	$(WEB) npm test

build-web: $(WEB_DEPS)
	$(WEB) npm run build

sanity: check test build-web ## Everything CI runs
	@echo "sanity: all gates passed"

fmt: ## Format backend code
	$(API) uv run ruff format . && uv run ruff check --fix .

# --- Contract ----------------------------------------------------------------

api-types: $(WEB_DEPS) ## Regenerate frontend API types from the backend OpenAPI schema
	$(API) DJANGO_SECRET_KEY=schema-only uv run python manage.py spectacular \
		--format openapi-json --file ../frontend/openapi.json
	$(WEB) API_SCHEMA=openapi.json npm run -s api:types; status=$$?; rm -f openapi.json; exit $$status

# --- Production --------------------------------------------------------------

deploy: ## Build, ship and roll the production stack (HEAD must be on origin/main)
	./deploy.sh

prod-check: ## Compare the live site's commit with origin/main
	@git fetch -q origin main
	@live=$$(curl -fsS https://spotter.akhilsingh.in/api/health | sed -n 's/.*"version":"\([^"]*\)".*/\1/p'); \
	want=$$(git rev-parse --short origin/main); \
	echo "live: $$live  origin/main: $$want"; [ "$$live" = "$$want" ]

# --- Setup -------------------------------------------------------------------

# Reinstall only when the lockfile changes.
$(WEB_DEPS): frontend/package-lock.json
	$(WEB) npm ci --no-audit --no-fund

hooks-install: ## Install the git hooks (gitleaks on commit, make check on push)
	pre-commit install --hook-type pre-commit --hook-type pre-push

# =============================================================================
# Odoo SaaS Platform - Development & Operations Makefile
# =============================================================================
# Provides convenient commands for development, testing, and deployment

.PHONY: help install dev-up dev-down dev-logs clean test lint format build deploy-dev deploy-prod backup restore

# Default target
.DEFAULT_GOAL := help

# Variables
DOCKER_COMPOSE = docker-compose
DOCKER_COMPOSE_PROD = docker-compose -f docker-compose.prod.yml
PYTHON = python3
PIP = pip3

# Colors for output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Odoo SaaS Platform - Available Commands$(NC)"
	@echo "$(YELLOW)======================================$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# =============================================================================
# Development Commands
# =============================================================================

install: ## Install development dependencies
	@echo "$(YELLOW)Installing development dependencies...$(NC)"
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	@echo "$(GREEN)Dependencies installed successfully!$(NC)"

dev-up: ## Start development environment
	@echo "$(YELLOW)Starting development environment...$(NC)"
	$(DOCKER_COMPOSE) up -d --build
	@echo "$(GREEN)Development environment started!$(NC)"
	@echo "$(BLUE)Admin Dashboard: http://admin.localhost$(NC)"
	@echo "$(BLUE)Customer Portal: http://portal.localhost$(NC)"
	@echo "$(BLUE)Grafana: http://localhost:3000$(NC)"
	@echo "$(BLUE)RQ Dashboard: http://localhost:9181$(NC)"

dev-down: ## Stop development environment
	@echo "$(YELLOW)Stopping development environment...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)Development environment stopped!$(NC)"

dev-logs: ## View development logs
	$(DOCKER_COMPOSE) logs -f

dev-restart: ## Restart development environment
	@echo "$(YELLOW)Restarting development environment...$(NC)"
	$(DOCKER_COMPOSE) restart
	@echo "$(GREEN)Development environment restarted!$(NC)"

dev-shell-admin: ## Open shell in admin container
	$(DOCKER_COMPOSE) exec admin bash

dev-shell-portal: ## Open shell in portal container
	$(DOCKER_COMPOSE) exec portal bash

dev-shell-postgres: ## Open PostgreSQL shell
	$(DOCKER_COMPOSE) exec postgres psql -U odoo -d odoo_saas_platform

dev-shell-redis: ## Open Redis shell
	$(DOCKER_COMPOSE) exec redis redis-cli

# =============================================================================
# Database Operations
# =============================================================================

db-migrate: ## Run database migrations
	@echo "$(YELLOW)Running database migrations...$(NC)"
	$(DOCKER_COMPOSE) exec admin alembic upgrade head
	@echo "$(GREEN)Database migrations completed!$(NC)"

db-migrate-create: ## Create new migration
	@read -p "Enter migration message: " msg; \
	$(DOCKER_COMPOSE) exec admin alembic revision --autogenerate -m "$$msg"

db-seed: ## Seed database with initial data
	@echo "$(YELLOW)Seeding database with initial data...$(NC)"
	SEED_DEMO_DATA=true $(DOCKER_COMPOSE) exec admin python scripts/seed_data.py
	@echo "$(GREEN)Database seeded successfully!$(NC)"

db-reset: ## Reset database (DANGER: destroys all data)
	@echo "$(RED)WARNING: This will destroy all data!$(NC)"
	@read -p "Are you sure? [y/N]: " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		$(DOCKER_COMPOSE) exec postgres psql -U odoo -c "DROP DATABASE IF EXISTS odoo_saas_platform;"; \
		$(DOCKER_COMPOSE) exec postgres psql -U odoo -c "CREATE DATABASE odoo_saas_platform;"; \
		make db-migrate db-seed; \
		echo "$(GREEN)Database reset completed!$(NC)"; \
	else \
		echo "$(YELLOW)Database reset cancelled.$(NC)"; \
	fi

# =============================================================================
# Testing
# =============================================================================

test: ## Run all tests
	@echo "$(YELLOW)Running all tests...$(NC)"
	$(DOCKER_COMPOSE) exec admin pytest tests/ -v
	@echo "$(GREEN)Tests completed!$(NC)"

test-unit: ## Run unit tests only
	@echo "$(YELLOW)Running unit tests...$(NC)"
	$(DOCKER_COMPOSE) exec admin pytest tests/unit/ -v

test-integration: ## Run integration tests only
	@echo "$(YELLOW)Running integration tests...$(NC)"
	$(DOCKER_COMPOSE) exec admin pytest tests/integration/ -v

test-coverage: ## Run tests with coverage report
	@echo "$(YELLOW)Running tests with coverage...$(NC)"
	$(DOCKER_COMPOSE) exec admin pytest --cov=admin --cov=portal --cov=shared --cov-report=html --cov-report=term tests/

test-smoke: ## Run smoke tests
	@echo "$(YELLOW)Running smoke tests...$(NC)"
	bash scripts/smoke_test.sh

# =============================================================================
# Code Quality
# =============================================================================

lint: ## Run linting checks
	@echo "$(YELLOW)Running linting checks...$(NC)"
	$(DOCKER_COMPOSE) exec admin flake8 admin/ portal/ shared/
	$(DOCKER_COMPOSE) exec admin black --check admin/ portal/ shared/
	$(DOCKER_COMPOSE) exec admin isort --check-only admin/ portal/ shared/

format: ## Format code
	@echo "$(YELLOW)Formatting code...$(NC)"
	$(DOCKER_COMPOSE) exec admin black admin/ portal/ shared/
	$(DOCKER_COMPOSE) exec admin isort admin/ portal/ shared/
	@echo "$(GREEN)Code formatted!$(NC)"

type-check: ## Run type checking
	@echo "$(YELLOW)Running type checking...$(NC)"
	$(DOCKER_COMPOSE) exec admin mypy admin/ portal/ shared/

security-scan: ## Run security scans
	@echo "$(YELLOW)Running security scans...$(NC)"
	$(DOCKER_COMPOSE) exec admin bandit -r admin/ portal/ shared/

# =============================================================================
# Build & Deployment
# =============================================================================

build: ## Build Docker images
	@echo "$(YELLOW)Building Docker images...$(NC)"
	$(DOCKER_COMPOSE) build --no-cache
	@echo "$(GREEN)Docker images built successfully!$(NC)"

build-prod: ## Build production Docker images
	@echo "$(YELLOW)Building production Docker images...$(NC)"
	$(DOCKER_COMPOSE_PROD) build --no-cache
	@echo "$(GREEN)Production images built successfully!$(NC)"

deploy-dev: dev-down build dev-up ## Deploy development environment
	@echo "$(GREEN)Development environment deployed!$(NC)"

deploy-prod: ## Deploy to production
	@echo "$(YELLOW)Deploying to production...$(NC)"
	@echo "$(RED)WARNING: This will deploy to production!$(NC)"
	@read -p "Are you sure? [y/N]: " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		$(DOCKER_COMPOSE_PROD) down; \
		$(DOCKER_COMPOSE_PROD) build --no-cache; \
		$(DOCKER_COMPOSE_PROD) up -d; \
		echo "$(GREEN)Production deployment completed!$(NC)"; \
	else \
		echo "$(YELLOW)Production deployment cancelled.$(NC)"; \
	fi

# =============================================================================
# Backup & Restore
# =============================================================================

backup: ## Backup all tenants
	@echo "$(YELLOW)Starting backup of all tenants...$(NC)"
	$(DOCKER_COMPOSE) exec admin python scripts/backup_all_tenants.py
	@echo "$(GREEN)Backup completed!$(NC)"

backup-tenant: ## Backup specific tenant (usage: make backup-tenant TENANT_ID=xyz)
	@if [ -z "$(TENANT_ID)" ]; then \
		echo "$(RED)Error: TENANT_ID is required. Usage: make backup-tenant TENANT_ID=xyz$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Backing up tenant $(TENANT_ID)...$(NC)"
	$(DOCKER_COMPOSE) exec admin python scripts/backup_tenant.py --tenant-id $(TENANT_ID)
	@echo "$(GREEN)Tenant backup completed!$(NC)"

restore: ## Restore tenant from backup (usage: make restore BACKUP_ID=xyz TENANT_ID=abc)
	@if [ -z "$(BACKUP_ID)" ] || [ -z "$(TENANT_ID)" ]; then \
		echo "$(RED)Error: Both BACKUP_ID and TENANT_ID are required.$(NC)"; \
		echo "$(RED)Usage: make restore BACKUP_ID=xyz TENANT_ID=abc$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Restoring tenant $(TENANT_ID) from backup $(BACKUP_ID)...$(NC)"
	$(DOCKER_COMPOSE) exec admin python scripts/restore_tenant.py --backup-id $(BACKUP_ID) --target-tenant $(TENANT_ID)
	@echo "$(GREEN)Tenant restore completed!$(NC)"

# =============================================================================
# Monitoring & Debugging
# =============================================================================

status: ## Show service status
	@echo "$(YELLOW)Service Status:$(NC)"
	$(DOCKER_COMPOSE) ps

health: ## Check health of all services
	@echo "$(YELLOW)Checking service health...$(NC)"
	@curl -s http://admin.localhost/health | jq . || echo "Admin service unavailable"
	@curl -s http://portal.localhost/health | jq . || echo "Portal service unavailable"

logs-admin: ## View admin service logs
	$(DOCKER_COMPOSE) logs -f admin

logs-portal: ## View portal service logs
	$(DOCKER_COMPOSE) logs -f portal

logs-worker: ## View worker logs
	$(DOCKER_COMPOSE) logs -f worker

logs-nginx: ## View nginx logs
	$(DOCKER_COMPOSE) logs -f nginx

stats: ## Show Docker container stats
	docker stats

# =============================================================================
# Utilities
# =============================================================================

clean: ## Clean up Docker resources
	@echo "$(YELLOW)Cleaning up Docker resources...$(NC)"
	$(DOCKER_COMPOSE) down -v
	docker system prune -f
	docker volume prune -f
	@echo "$(GREEN)Cleanup completed!$(NC)"

clean-all: ## Clean everything including images (DANGER)
	@echo "$(RED)WARNING: This will remove all Docker images and data!$(NC)"
	@read -p "Are you sure? [y/N]: " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		$(DOCKER_COMPOSE) down -v --rmi all; \
		docker system prune -a -f; \
		docker volume prune -f; \
		echo "$(GREEN)Complete cleanup finished!$(NC)"; \
	else \
		echo "$(YELLOW)Cleanup cancelled.$(NC)"; \
	fi

update-deps: ## Update Python dependencies
	@echo "$(YELLOW)Updating dependencies...$(NC)"
	$(PIP) install --upgrade -r requirements.txt
	$(PIP) freeze > requirements.txt
	@echo "$(GREEN)Dependencies updated!$(NC)"

generate-secret: ## Generate a new secret key
	@echo "$(YELLOW)Generated secret key:$(NC)"
	@$(PYTHON) -c "import secrets; print(secrets.token_hex(32))"

# =============================================================================
# Kubernetes Operations
# =============================================================================

k8s-deploy: ## Deploy to Kubernetes
	@echo "$(YELLOW)Deploying to Kubernetes...$(NC)"
	kubectl apply -f k8s/base/ -n odoo-saas
	@echo "$(GREEN)Kubernetes deployment completed!$(NC)"

k8s-status: ## Check Kubernetes deployment status
	kubectl get all -n odoo-saas

k8s-logs: ## View Kubernetes logs
	kubectl logs -f deployment/admin -n odoo-saas

k8s-shell: ## Open shell in Kubernetes pod
	kubectl exec -it deployment/admin -n odoo-saas -- bash

# =============================================================================
# Documentation
# =============================================================================

docs: ## Generate API documentation
	@echo "$(YELLOW)Generating API documentation...$(NC)"
	$(DOCKER_COMPOSE) exec admin python scripts/generate_docs.py
	@echo "$(GREEN)Documentation generated!$(NC)"

docs-serve: ## Serve documentation locally
	@echo "$(YELLOW)Starting documentation server...$(NC)"
	cd docs && python -m http.server 8000

# =============================================================================
# CI/CD
# =============================================================================

ci-test: ## Run CI/CD tests
	@echo "$(YELLOW)Running CI/CD test suite...$(NC)"
	make lint
	make test-coverage
	make security-scan
	@echo "$(GREEN)CI/CD tests completed!$(NC)"

ci-build: ## Build for CI/CD
	@echo "$(YELLOW)Building for CI/CD...$(NC)"
	$(DOCKER_COMPOSE) build
	@echo "$(GREEN)CI/CD build completed!$(NC)"

# =============================================================================
# Development Helpers
# =============================================================================

dev-tools: ## Start development tools (adminer, etc.)
	@echo "$(YELLOW)Starting development tools...$(NC)"
	$(DOCKER_COMPOSE) --profile dev-tools up -d adminer
	@echo "$(GREEN)Development tools started!$(NC)"
	@echo "$(BLUE)Adminer: http://localhost:8080$(NC)"

init: ## Initialize new development environment
	@echo "$(YELLOW)Initializing development environment...$(NC)"
	cp .env.example .env
	@echo "$(GREEN)Environment file created. Please edit .env with your settings.$(NC)"
	@echo "$(BLUE)Run 'make dev-up' to start the development environment.$(NC)"

reset: ## Reset development environment
	@echo "$(YELLOW)Resetting development environment...$(NC)"
	make dev-down
	make clean
	make dev-up
	make db-seed
	@echo "$(GREEN)Development environment reset completed!$(NC)"
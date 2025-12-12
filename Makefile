.PHONY: help build up down logs clean test

help:
	@echo "Investment Analysis Platform - Makefile"
	@echo ""
	@echo "Available commands:"
	@echo "  make build    - Build Docker images"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make logs     - View logs from all services"
	@echo "  make clean    - Remove containers, volumes, and images"
	@echo "  make test     - Run a test analysis (requires services to be running)"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v --rmi all

test:
	@echo "Submitting test analysis for AAPL..."
	@curl -X POST "http://localhost:8000/api/analyze" \
		-H "Content-Type: application/json" \
		-d '{"ticker": "AAPL"}' | python -m json.tool
	@echo ""
	@echo "Check status at: http://localhost:8000/api/status/1"
	@echo "View API docs at: http://localhost:8000/docs"


.PHONY: up down logs test lint format

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api worker

test:
	pytest -q

lint:
	ruff check .

format:
	ruff check --fix .
	ruff format .

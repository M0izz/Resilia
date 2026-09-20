.PHONY: up down seed logs backend dashboard dev clean

## Start DynamoDB + backend
up:
	docker compose up -d dynamodb-local backend

## Start everything (including dashboard)
all:
	docker compose up -d

## Seed the database with 75 PHC records
seed:
	docker compose --profile seed run --rm seed

## Run backend locally (outside Docker)
backend:
	cd backend && uvicorn app.main:app --reload --port 8000

## Run dashboard locally (outside Docker)
dashboard:
	cd dashboard && streamlit run app.py

## Full local dev: seed + launch backend + dashboard
dev: seed
	@echo "Starting backend and dashboard..."
	@docker compose up -d

## Tail logs
logs:
	docker compose logs -f

## Tear down all containers and volumes
clean:
	docker compose down -v
	docker compose --profile seed down

## Reset: wipe DB and re-seed
reset: clean up
	@sleep 5
	@$(MAKE) seed

## Run test suite
test:
	pytest backend/tests/ -v

## Run benchmarks and backtest
benchmark:
	python backend/scripts/run_backtest.py


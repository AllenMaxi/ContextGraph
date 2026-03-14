.PHONY: test lint format serve docker-up docker-down install

install:
	pip install -e ".[server,neo4j,dev]"

test:
	python3 -m pytest tests/ -v

lint:
	ruff check contextgraph/ sdk/ tests/

format:
	ruff format contextgraph/ sdk/ tests/

serve:
	uvicorn contextgraph.main:app --reload --host 0.0.0.0 --port 8420

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

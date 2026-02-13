.PHONY: fmt lint typecheck test all

fmt:
	ruff format src tests
	ruff check --fix src tests

lint:
	ruff check src tests

typecheck:
	mypy src/pisti

test:
	pytest tests -v

all: fmt lint typecheck test

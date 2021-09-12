.PHONY: lint
lint:
	pylint *.py

.PHONY: typecheck
typecheck:
	mypy --strict *.py

.PHONY: clean
clean:
	rm -rf *~ .*~ *.pyc *.pyi .mypy_cache __pycache__ *.log

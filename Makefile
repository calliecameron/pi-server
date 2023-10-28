.PHONY: all
all: lint todo deps-graph

.PHONY: lint
lint:
	# utils/find-shell-files.sh | xargs -d '\n' shellcheck
	# utils/find-shell-files.sh | xargs -d '\n' shfmt -l -d -i 4
	pylint --score n --recursive y --ignore-paths testbed .
	pylint --score n --recursive y testbed
	utils/find-python-files.sh | xargs -d '\n' flake8
	utils/find-python-files.sh | xargs -d '\n' black --check
	utils/find-python-files.sh | xargs -d '\n' isort --check
	utils/find-python-files.sh | xargs -d '\n' mypy --strict
	# ansible-lint
	./utils/roles.py lint roles testbed/roles

.PHONY: todo
todo:
	grep -ir --exclude=Makefile --exclude-dir=.git todo

.PHONY: deps-graph
deps-graph:
	./utils/roles.py deps roles > deps-graph.txt
	dot -Tsvg -o deps-graph.svg deps-graph.txt

SUBDIR_ROOTS := ca roles stubs testbed utils
DIRS := . $(shell find $(SUBDIR_ROOTS) -type d)
CLEAN_PATTERNS := *~ .*~ *.pyc .mypy_cache .pytest_cache __pycache__ *.log
CLEAN := $(foreach DIR,$(DIRS),$(addprefix $(DIR)/,$(CLEAN_PATTERNS)))

.PHONY: clean
clean:
	@rm -rf $(CLEAN) deps-graph.txt deps-graph.svg

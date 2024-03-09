.PHONY: all
all: lint todo deps-graph

.PHONY: lint
lint:
	utils/find-shell-files.sh | xargs -d '\n' shellcheck
	utils/find-shell-files.sh | xargs -d '\n' shfmt -l -d -i 4
	utils/find-python-files.sh | xargs -d '\n' ruff check
	utils/find-python-files.sh | xargs -d '\n' ruff format --diff
	utils/find-python-files.sh | xargs -d '\n' mypy --strict --scripts-are-modules
	ansible-lint --offline
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

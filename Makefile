.PHONY: all
all: lint todo deps-graph

.PHONY: deps
deps: .deps-installed

.deps-installed: requirements.txt
	pip install -r requirements.txt
	touch .deps-installed

requirements.txt: requirements.in pyproject.toml
	pip-compile -q

.PHONY: lint
lint: deps
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
deps-graph: deps
	./utils/roles.py deps roles > deps-graph.txt
	dot -Tsvg -o deps-graph.svg deps-graph.txt

.PHONY: clean
clean:
	rm -f .deps-installed
	find . -depth '(' -type d '(' -name '.mypy_cache' -o -name '.ruff_cache' -o -name '.pytest_cache' -o -name '__pycache__' ')' ')' -exec rm -r '{}' ';'
	find . '(' -type f '(' -name '*~' -o -name '*.log' ')' ')' -delete

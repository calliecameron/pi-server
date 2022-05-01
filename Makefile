.PHONY: all
all: lint todo deps

.PHONY: lint
lint:
	ansible-lint
	./utils/roles.py lint roles testbed/roles
	cd utils && make
	cd testbed && make

.PHONY: todo
todo:
	grep -ir --exclude=Makefile --exclude-dir=.git todo

.PHONY: deps
deps:
	./utils/roles.py deps roles > deps-graph.txt
	dot -Tsvg -o deps-graph.svg deps-graph.txt

.PHONY: clean
clean:
	rm -f deps-graph.txt deps-graph.svg
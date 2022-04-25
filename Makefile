.PHONY: all
all: lint todo

.PHONY: lint
lint:
	ansible-lint
	./utils/roles.py lint roles testbed/roles
	cd utils && make
	cd testbed && make

.PHONY: todo
todo:
	grep -ir --exclude=Makefile --exclude-dir=.git todo

.PHONY: all
all: lint todo

.PHONY: lint
lint:
	ansible-lint

.PHONY: todo
todo:
	grep -ir --exclude=Makefile todo

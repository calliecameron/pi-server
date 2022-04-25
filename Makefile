.PHONY: all
all: lint

.PHONY: lint
lint:
	ansible-lint

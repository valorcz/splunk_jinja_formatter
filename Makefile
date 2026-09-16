# Text colors (POSIX printf formatting)
NO_COLOR=\033[0m
OK_COLOR=\033[32;01m
ERROR_COLOR=\033[31;01m
WARN_COLOR=\033[36;01m
ATTN_COLOR=\033[33;01m

ROOT_DIR := $(shell git rev-parse --show-toplevel)
CONTAINER_NAME := splunk-jinja2-formatter

.PHONY: all
all: test package

.PHONY: init
init:
	@printf "$(ATTN_COLOR)==> Initializing virtual environment with uv $(NO_COLOR)\n"
	@uv sync

.PHONY: test
test:
	@printf "$(ATTN_COLOR)==> Running unit tests $(NO_COLOR)\n"
	@uv run pytest

.PHONY: version
version:
	@python3 scripts/version.py

.PHONY: bump-patch
bump-patch:
	@python3 scripts/version.py patch

.PHONY: bump-minor
bump-minor:
	@python3 scripts/version.py minor

.PHONY: bump-major
bump-major:
	@python3 scripts/version.py major

.PHONY: set-version
set-version:
	@if [ -z "$(V)" ]; then echo "Error: specify V=<version>, e.g. make set-version V=1.0.7"; exit 1; fi
	@python3 scripts/version.py $(V)

.PHONY: vendor
vendor:
	@printf "$(ATTN_COLOR)==> Vendoring dependencies into jinja_formatter/lib $(NO_COLOR)\n"
	@python3 scripts/build.py --vendor

.PHONY: package
package:
	@printf "$(ATTN_COLOR)==> Building Splunk App package $(NO_COLOR)\n"
	@python3 scripts/build.py --package

.PHONY: install-appinspect
install-appinspect:
	@printf "$(ATTN_COLOR)==> Installing splunk-appinspect via uv $(NO_COLOR)\n"
	@uv tool install --python 3.11 splunk-appinspect

.PHONY: inspect
inspect: package
	@printf "$(ATTN_COLOR)==> Running Splunk AppInspect $(NO_COLOR)\n"
	@python3 scripts/build.py --inspect

.PHONY: clean
clean:
	@printf "$(ATTN_COLOR)==> Cleaning build artifacts and vendor libraries $(NO_COLOR)\n"
	@python3 scripts/build.py --clean

.PHONY: up
up:
	@printf "$(ATTN_COLOR)==> Starting Splunk in Docker $(NO_COLOR)\n"
	@docker-compose up -d

.PHONY: wait_up
wait_up:
	@printf "$(ATTN_COLOR)==> Waiting for Splunk container to be healthy $(NO_COLOR)\n"
	@for i in `seq 0 180`; do \
		if docker exec -it $(CONTAINER_NAME) /sbin/checkstate.sh &> /dev/null; then break; fi; \
		printf "\rWaiting for Splunk for %s seconds..." $$i; \
		sleep 1; \
	done
	@echo ""

.PHONY: deploy
deploy: package
	@printf "$(ATTN_COLOR)==> Deploying app package to Splunk container $(NO_COLOR)\n"
	@tarball=$$(ls -1t app/jinja_formatter-*.tar.gz 2>/dev/null | head -n 1); \
	if [ -z "$$tarball" ]; then echo "Error: No package found in app/"; exit 1; fi; \
	docker cp $$tarball $(CONTAINER_NAME):/tmp/app.tar.gz
	@docker exec -u splunk $(CONTAINER_NAME) /opt/splunk/bin/splunk install app /tmp/app.tar.gz -update 1 -auth admin:changed!
	@docker exec -u 0 $(CONTAINER_NAME) rm -f /tmp/app.tar.gz
	@docker exec -u splunk $(CONTAINER_NAME) curl -s -k -u admin:changed! https://localhost:8089/services/apps/local/_reload > /dev/null || true
	@printf "$(OK_COLOR)==> App successfully installed into Splunk container! $(NO_COLOR)\n"

.PHONY: down
down:
	@printf "$(ATTN_COLOR)==> Stopping Splunk $(NO_COLOR)\n"
	@docker-compose stop

.PHONY: remove
remove:
	@printf "$(ATTN_COLOR)==> Removing Splunk container $(NO_COLOR)\n"
	@docker-compose rm -f -s

.PHONY: start
start: up wait_up deploy

.PHONY: restart
restart: down start

.PHONY: refresh
refresh: remove start


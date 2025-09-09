# ==== Config ====
DOCKER_IMG        ?= ratemate-tests
DOCKER_RUN_OPTS   ?= --rm -t --ipc=host --shm-size=1g
MOUNT             := -v "$(PWD):/app"
ENVFILE           := $(if $(wildcard .env),--env-file .env,)

# (MỚI) Cache Playwright: tắt mặc định, chỉ bật khi USE_CACHE=1
ifeq ($(USE_CACHE),1)
PW_CACHE_MOUNT := -v "$(HOME)/.cache/ms-playwright:/ms-playwright"
endif

PYTEST_COMMON := -vv tests \
  --browser=chromium --browser=firefox --browser=webkit \
  --screenshot=only-on-failure --video=off --tracing=retain-on-failure

TS            := $(shell date +%Y%m%d-%H%M%S)
REPORT_DIR    := report
RUN_XLSX      := $(REPORT_DIR)/run-$(TS).xlsx
SMOKE_XLSX    := $(REPORT_DIR)/smoke-$(TS).xlsx
BASELINE_XLSX := $(REPORT_DIR)/baseline.xlsx

.DEFAULT_GOAL := help
.PHONY: help build verify run smoke baseline clean warm-cache

help:
	@echo "Targets:"
	@echo "  make run              - full suite (KHÔNG cache mặc định)"
	@echo "  USE_CACHE=1 make run  - full suite CÓ cache"
	@echo "  make smoke/baseline/verify/clean/warm-cache"

$(REPORT_DIR):
	mkdir -p $(REPORT_DIR)

build:
	docker build --pull \
	  --build-arg UID=$(shell id -u) --build-arg GID=$(shell id -g) \
	  -t $(DOCKER_IMG) -f Dockerfile .

verify:
	docker run $(DOCKER_RUN_OPTS) --user 0:0 $(PW_CACHE_MOUNT) $(MOUNT) $(ENVFILE) $(DOCKER_IMG) \
	  bash -lc 'python -m playwright --version; ls -la /ms-playwright || true'

run: $(REPORT_DIR)
	docker run $(DOCKER_RUN_OPTS) --user 0:0 $(PW_CACHE_MOUNT) $(MOUNT) $(ENVFILE) $(DOCKER_IMG) \
	  bash -lc 'mkdir -p report test-results && pytest $(PYTEST_COMMON) --excelreport=$(RUN_XLSX)'

smoke: $(REPORT_DIR)
	docker run $(DOCKER_RUN_OPTS) --user 0:0 $(PW_CACHE_MOUNT) $(MOUNT) $(ENVFILE) $(DOCKER_IMG) \
	  bash -lc "mkdir -p report test-results && pytest -vv tests/auth tests/smoke/test_routes.py \
	    --browser=chromium --browser=webkit \
	    --screenshot=only-on-failure --video=off --tracing=retain-on-failure \
	    --excelreport=$(SMOKE_XLSX)"

baseline: $(REPORT_DIR)
	docker run $(DOCKER_RUN_OPTS) --user 0:0 $(PW_CACHE_MOUNT) $(MOUNT) $(ENVFILE) $(DOCKER_IMG) \
	  bash -lc 'mkdir -p report test-results && pytest $(PYTEST_COMMON) --excelreport=$(BASELINE_XLSX)'

clean:
	rm -rf $(REPORT_DIR) test-results .pytest_cache || true

# (Tùy chọn) Làm ấm cache host trước khi USE_CACHE=1
warm-cache:
	mkdir -p $(HOME)/.cache/ms-playwright
	docker run $(DOCKER_RUN_OPTS) --user 0:0 -v "$(HOME)/.cache/ms-playwright:/ms-playwright" $(MOUNT) $(ENVFILE) $(DOCKER_IMG) \
	  bash -lc 'python -m playwright install --with-deps'

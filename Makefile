.PHONY: install install-api install-data lint test ai-eval api demo-data dashboard-data \
	windows-setup public-data synerise-all synerise-smoke generate ods dwd dim dws ads quality all clean

PYTHON ?= python
DATA_ROOT ?= data
START_DATE ?= 2025-01-01
END_DATE ?= 2025-03-31
DT ?= 2025-03-31
SCALE ?= tiny
SYNERISE_INPUT ?= external_data/synerise-recsys-2025/extracted
SYNERISE_TABLES ?= all
SYNERISE_LIMIT ?= 0
SYNERISE_OUTPUT_PARTITIONS ?= 96
SYNERISE_START_DATE ?= 2022-06-23
SYNERISE_END_DATE ?= 2022-12-08

install:
	$(PYTHON) -m pip install -r requirements.txt

install-api:
	$(PYTHON) -m pip install -r requirements-api.txt

install-data:
	$(PYTHON) -m pip install -r requirements-data.txt

lint:
	ruff check app scripts/run_ai_evals.py scripts/generate_demo_data.py tests/test_ai_*.py tests/test_api.py

test:
	pytest

ai-eval:
	$(PYTHON) scripts/run_ai_evals.py --threshold 0.95

demo-data:
	$(PYTHON) scripts/generate_demo_data.py

api:
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

windows-setup:
	powershell -ExecutionPolicy Bypass -File scripts/setup_windows_spark.ps1

public-data:
	$(PYTHON) scripts/download_public_data.py --dataset synerise-recsys-2025 --extract

dashboard-data:
	$(PYTHON) scripts/export_dashboard_data.py --data-root $(DATA_ROOT) --output dashboard/data/dashboard.json --topn 10

synerise-all:
	$(PYTHON) scripts/run_synerise_pipeline.py --input $(SYNERISE_INPUT) --data-root $(DATA_ROOT) --tables $(SYNERISE_TABLES) --start-date $(SYNERISE_START_DATE) --end-date $(SYNERISE_END_DATE) --output-partitions $(SYNERISE_OUTPUT_PARTITIONS)

synerise-smoke:
	$(PYTHON) scripts/run_synerise_pipeline.py --input $(SYNERISE_INPUT) --data-root data_synerise_smoke --tables all --limit-per-table 10000 --output-partitions 4

generate:
	$(PYTHON) scripts/generate_data.py --output $(DATA_ROOT)/raw --scale $(SCALE) --start-date $(START_DATE) --days 90

ods:
	$(PYTHON) jobs/ods_load.py --input $(DATA_ROOT)/raw --output $(DATA_ROOT)/ods --start-date $(START_DATE) --end-date $(END_DATE)

dwd:
	$(PYTHON) jobs/dwd_clean.py --input $(DATA_ROOT)/ods --output $(DATA_ROOT)/dwd --start-date $(START_DATE) --end-date $(END_DATE)

dim:
	$(PYTHON) jobs/dim_build.py --input $(DATA_ROOT) --output $(DATA_ROOT)/dim --dt $(DT) --start-date $(START_DATE) --end-date $(END_DATE)

dws:
	$(PYTHON) jobs/dws_aggregate.py --input $(DATA_ROOT) --output $(DATA_ROOT)/dws --dt $(DT) --start-date $(START_DATE) --end-date $(END_DATE)

ads:
	$(PYTHON) jobs/ads_metrics.py --input $(DATA_ROOT) --output $(DATA_ROOT)/ads --dt $(DT) --start-date $(START_DATE) --end-date $(END_DATE)

quality:
	$(PYTHON) scripts/run_quality_checks.py --input $(DATA_ROOT) --output reports/data_quality_report.md --start-date $(START_DATE) --end-date $(END_DATE)

all:
	$(PYTHON) scripts/run_all.py --scale $(SCALE) --start-date $(START_DATE) --days 90

clean:
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in [pathlib.Path('data/raw'), pathlib.Path('data/ods'), pathlib.Path('data/dwd'), pathlib.Path('data/dim'), pathlib.Path('data/dws'), pathlib.Path('data/ads')]]"

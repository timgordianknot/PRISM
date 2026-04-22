PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: install test run-ui run-api

install:
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

run-ui:
	streamlit run apps/fincrm_dashboard.py

run-api:
	uvicorn api.main:app --reload

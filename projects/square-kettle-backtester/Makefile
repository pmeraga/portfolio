# -----------------------------
# Square Kettle — Data Layer Makefile (Windows-safe)
# -----------------------------

SHELL := bash
.SHELLFLAGS := -o pipefail -c
PY ?= python

# ---- Defaults (override on command line) ----
DATASET ?= GLBX.MDP3
SYMBOLS ?= ES.n.0
STYPE_IN ?= continuous

# Heavy schemas like mbp-10 are excluded from quick testing by default.
# You can still include them by overriding SCHEMAS on the command line.
SCHEMAS_QUICK ?= ohlcv-1m tbbo trades
SCHEMAS_ALL   ?= ohlcv-1m tbbo tcbbo trades mbp-10

# Use quick set by default (fast testing)
SCHEMAS ?= $(SCHEMAS_QUICK)

# Full-range (original) window — you can still use these explicitly if you want
START ?= 2023-12-06T14:30:00Z
END   ?= 2023-12-06T20:30:00Z

# Short test window (fast) — used by smoke-quick target
TEST_START ?= 2023-12-06T14:30:00Z
TEST_END   ?= 2023-12-06T15:00:00Z

INSTRUMENT_ID ?= ES.n.0

RAW ?= raw
CATALOG ?= catalog
INTERIM ?= interim

define hr
	@printf "\n==================== %s ====================\n" "$(1)"
endef

.PHONY: help print-vars fetch fetch-% paths show-artifact catalog inspect csv check \
        smoke smoke-quick clean clean-raw clean-catalog clean-interim setup doctor

help:
	@echo "Targets:"
	@echo "  make fetch               # fetch all SCHEMAS → raw/ with caching"
	@echo "  make fetch-<schema>      # fetch one schema (e.g., fetch-mbp-10)"
	@echo "  make paths               # print expected raw/*.dbn.zst paths for current params"
	@echo "  make show-artifact       # print manifest entry (size, sha) for current params"
	@echo "  make catalog             # build Parquet catalog from computed raw paths"
	@echo "  make inspect             # tabulate catalog contents"
	@echo "  make csv                 # export interim CSVs (quotes/trades/bars_for_viz)"
	@echo "  make check               # verify files exist and are non-empty"
	@echo "  make smoke               # full e2e with current SCHEMAS/START/END"
	@echo "  make smoke-quick         # fast e2e: SCHEMAS_QUICK + TEST_START/TEST_END"
	@echo "  make setup               # pip install -r requirements.txt into $(PY)"
	@echo "  make doctor              # show interpreter + package checks"

print-vars:
	$(call hr,Current Variables)
	@echo "DATASET=$(DATASET)"
	@echo "SYMBOLS=$(SYMBOLS)"
	@echo "STYPE_IN=$(STYPE_IN)"
	@echo "SCHEMAS=$(SCHEMAS)"
	@echo "START=$(START)"
	@echo "END=$(END)"
	@echo "INSTRUMENT_ID=$(INSTRUMENT_ID)"
	@echo "RAW=$(RAW)"
	@echo "CATALOG=$(CATALOG)"
	@echo "INTERIM=$(INTERIM)"

# -------- Fetch raw DBN (cached) --------
fetch: $(SCHEMAS:%=fetch-%)

fetch-%:
	$(call hr,Fetch schema $*)
	$(PY) -m data.fetch_databento \
	  --dataset $(DATASET) \
	  --symbols $(SYMBOLS) \
	  --stype-in $(STYPE_IN) \
	  --schema $* \
	  --start $(START) \
	  --end   $(END)

# Convenience: fetch only quotes+trades (ignore bars/depth) for speed
fetch-quotes-trades:
	$(MAKE) SCHEMAS="tbbo trades" fetch

# -------- Expected raw paths --------
paths:
	$(call hr,Expected raw paths)
	$(PY) src/data/paths_cli.py \
	  --dataset "$(DATASET)" \
	  --symbols "$(SYMBOLS)" \
	  --stype-in "$(STYPE_IN)" \
	  --start "$(START)" \
	  --end "$(END)" \
	  --schemas "$(SCHEMAS)"

# -------- Show manifest entries --------
show-artifact:
	$(call hr,Manifest entry)
	$(PY) src/data/show_manifest_cli.py \
	  --raw "$(RAW)" \
	  --dataset "$(DATASET)" \
	  --symbols "$(SYMBOLS)" \
	  --stype-in "$(STYPE_IN)" \
	  --start "$(START)" \
	  --end "$(END)" \
	  --schemas "$(SCHEMAS)"

# -------- Build Parquet catalog from raw paths --------
catalog:
	$(call hr,Build catalog)
	@$(PY) src/data/paths_cli.py \
	  --dataset "$(DATASET)" \
	  --symbols "$(SYMBOLS)" \
	  --stype-in "$(STYPE_IN)" \
	  --start "$(START)" \
	  --end "$(END)" \
	  --schemas "$(SCHEMAS)" > .mk_raw_paths.txt
	@echo "Using raw paths:"; cat .mk_raw_paths.txt
	@readarray -t RAW_ARR < <(tr -d '\r' < .mk_raw_paths.txt); \
	echo "Count: $${#RAW_ARR[@]}"; \
	for p in "$${RAW_ARR[@]}"; do echo "  -> $$p"; done; \
	$(PY) -m data.etl_to_catalog \
	  --instrument-id $(INSTRUMENT_ID) \
	  --catalog-path $(CATALOG) \
	  --overwrite \
	  --paths $${RAW_ARR[@]}
	@rm -f .mk_raw_paths.txt

# -------- Quick checks: presence + non-empty --------
check:
	$(call hr,Check raw files)
	@for SC in $(SCHEMAS); do \
	  P="$$( $(PY) src/data/paths_cli.py \
	    --dataset "$(DATASET)" \
	    --symbols "$(SYMBOLS)" \
	    --stype-in "$(STYPE_IN)" \
	    --start "$(START)" \
	    --end "$(END)" \
	    --schema "$$SC" )"; \
	  if [ -f "$$P" ] && [ -s "$$P" ]; then \
	    echo "OK  $$P ($$(stat -c%s "$$P" 2>/dev/null || stat -f%z "$$P") bytes)"; \
	  else \
	    echo "MISSING/EMPTY: $$P"; exit 2; \
	  fi; \
	done
	$(call hr,Check catalog)
	@test -s "$(CATALOG)/manifest.json" || (echo "Missing $(CATALOG)/manifest.json"; exit 2)
	@echo "OK  $(CATALOG)/manifest.json"
	$(call hr,Check interim CSVs)
	@test -s "$(INTERIM)/bars_for_viz.csv" && echo "OK  $(INTERIM)/bars_for_viz.csv" || echo "warn: no bars_for_viz.csv"
	@test -s "$(INTERIM)/quotes.csv" && echo "OK  $(INTERIM)/quotes.csv" || echo "warn: no quotes.csv"
	@test -s "$(INTERIM)/trades.csv" && echo "OK  $(INTERIM)/trades.csv" || echo "warn: no trades.csv"

# -------- Inspect catalog contents --------
inspect:
	$(call hr,Inspect catalog)
	$(PY) -m data.inspect_catalog --catalog-path $(CATALOG)

# -------- Export normalized CSVs for viz/QA --------
csv:
	$(call hr,Export CSVs)
	$(PY) -m data.csv_extract \
	  --source catalog \
	  --instrument-id $(INSTRUMENT_ID) \
	  --catalog-path $(CATALOG) \
	  --out-dir $(INTERIM)

# -------- One-button e2e (current variables) --------
smoke: fetch catalog inspect csv check

# -------- One-button e2e (FAST): quotes+trades+bars, short window --------
smoke-quick:
	$(MAKE) SCHEMAS="$(SCHEMAS_QUICK)" START="$(TEST_START)" END="$(TEST_END)" smoke

# -------- Setup & Doctor --------
setup:
	$(call hr,Install Python deps into this interpreter)
	$(PY) -m pip install -r requirements.txt

doctor:
	$(call hr,Environment Doctor)
	@echo "Python path:"; $(PY) -c "import sys; print(sys.executable)"
	@echo "Python version:"; $(PY) -c "import sys; print(sys.version)"
	@echo "Packages:"
	-@$(PY) -m pip show databento | sed 's/^/  /'
	-@$(PY) -m pip show nautilus-trader | sed 's/^/  /'
	-@$(PY) -m pip show python-dotenv | sed 's/^/  /'
	@echo ".env key present? (masked):"
	-@$(PY) -c "import os; print('DATABENTO_API_KEY=', '***' if os.getenv('DATABENTO_API_KEY') else '(missing)')"

# -------- Cleanup --------
clean: clean-raw clean-catalog clean-interim
clean-raw:
	@rm -rf "$(RAW)"
clean-catalog:
	@rm -rf "$(CATALOG)"
clean-interim:
	@rm -rf "$(INTERIM)"

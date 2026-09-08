.PHONY: db server up bench

db:
	. .venv/bin/activate && python -c "from sf_code_intelligence.db import init_db; init_db(); print('Initialized index.db')"

server:
	. .venv/bin/activate && python -m sf_code_intelligence.server

up: db server

bench:
	. .venv/bin/activate && python -m sf_code_intelligence.benchmark ./fixtures --iterations 50 --warmup 5

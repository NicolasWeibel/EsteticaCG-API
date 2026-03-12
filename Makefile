# ===============================
# Makefile  (atajos)
# ===============================
.PHONY: run migrate makemigrations test lint fmt schema deploy-staging
run:
\tpython manage.py runserver
migrate:
\tpython manage.py migrate
makemigrations:
\tpython manage.py makemigrations
test:
\tpytest
lint:
\truff check .
fmt:
\tisort . && black .
schema:
\tpython manage.py spectacular --file schema.yaml
deploy-staging:
\tpowershell -ExecutionPolicy Bypass -File scripts/deploy-staging.ps1

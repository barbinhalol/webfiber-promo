#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
echo "### régua de 3";      LLM_PROVIDER=fake python3 tests/test_viability.py     | tail -1
echo "### guards";          LLM_PROVIDER=fake python3 tests/test_guards.py         | tail -1
echo "### pipeline sombra"; LLM_PROVIDER=fake python3 tests/test_pipeline.py       | tail -1
echo "### filtros webhook"; LLM_PROVIDER=fake python3 tests/test_webhook_filtros.py| tail -1
echo "### conversas";       LLM_PROVIDER=fake python3 tests/test_conversas.py      | tail -1

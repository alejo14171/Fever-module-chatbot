#!/usr/bin/env bash
# Launch LangGraph Studio against the Fever chatbot, in-memory checkpointer.
#
# Usage:
#   GOOGLE_API_KEY=AIza... ./scripts/run_dev.sh
# Or set GOOGLE_API_KEY in your shell first, then run.

set -euo pipefail

export USE_MEMORY_CHECKPOINTER="${USE_MEMORY_CHECKPOINTER:-1}"
export LLM_PROVIDER="${LLM_PROVIDER:-google}"
export LLM_MODEL="${LLM_MODEL:-gemini-2.5-flash}"

if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
  echo "❌ GOOGLE_API_KEY is not set. Export it before running."
  exit 1
fi

cd "$(dirname "$0")/.."
exec uv run langgraph dev --host 0.0.0.0 --port 2024

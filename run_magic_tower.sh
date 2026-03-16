#!/bin/bash
# Load environment variables from .env file
# if [ -f "$(dirname "$0")/.cua/.env" ]; then
#     echo "Loading environment variables from .cua/.env..."
#     export $(cat "$(dirname "$0")/.cua/.env" | grep -v '^#' | xargs)
# else
#     echo "Warning: .cua/.env file not found"
# fi

export CUA_ENV_API_URL="http://${VM_IP}:5000"

# Configuration for Remote Windows Environment
export CUA_ENV_TYPE="windows"
export CUA_TELEMETRY_DISABLED="true"
export CUA_ENV_VNC_URL=""
export XDG_DATA_HOME="./trycua"
task="mota_24_easy"
export MEMORY_TASK_ID="${task}"
export EVALUATION_OUTPUT_DIR="./trycua/cua-bench/${task}"

# Run the Magic Tower Demo task
# Using 'uv run' to ensure we use the correct python environment from the workspace
# uv run cb run task ./tasks/game/mota_24_easy \
#     --agent cua-agent \
#     --model openai/computer-use-preview \
#     --provider-type computer \
#     --wait

MAX_STEPS="${1:-500}"
model_id="anthropic/claude-sonnet-4-20250514"
# model_id="anthropic/claude-opus-4-6"
# model_id="anthropic/claude-haiku-4-5-20251001"
# model_id="openai/computer-use-preview"
# model_id="openai/gpt-5.4"
# summary_model_id="gpt-5-mini" # mini
# summary_model_id="anthropic/claude-haiku-4-5-20251001"
summary_model_id="anthropic/claude-sonnet-4-20250514"
# Optional: use a cheaper model for summarization and memory flush
# summary_model_id="anthropic/claude-haiku-4-5-20251001"
# summary_model_id="${SUMMARY_MODEL:-}"

SUMMARY_MODEL_ARG=""
if [ -n "$summary_model_id" ]; then
    SUMMARY_MODEL_ARG="--summary-model $summary_model_id"
fi

uv run python -m cua_bench.batch.solver ./tasks/game/${task} \
    --eval \
    --agent openclaw-agent \
    --model $model_id \
    --max-steps "$MAX_STEPS" \
    --output-dir $EVALUATION_OUTPUT_DIR \
    $SUMMARY_MODEL_ARG




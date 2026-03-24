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
model_id="${2:-anthropic/claude-sonnet-4-20250514}"
summary_model_id="${3:-anthropic/claude-sonnet-4-20250514}"
thinking_level="${4:-}"
flush_thinking_level="${5:-}"
compaction_thinking_level="${6:-}"

SUMMARY_MODEL_ARG=""
if [ -n "$summary_model_id" ]; then
    SUMMARY_MODEL_ARG="--summary-model $summary_model_id"
fi

THINKING_ARG=""
if [ -n "$thinking_level" ]; then
    THINKING_ARG="--thinking-level $thinking_level"
fi

FLUSH_THINKING_ARG=""
if [ -n "$flush_thinking_level" ]; then
    FLUSH_THINKING_ARG="--flush-thinking-level $flush_thinking_level"
fi

COMPACTION_THINKING_ARG=""
if [ -n "$compaction_thinking_level" ]; then
    COMPACTION_THINKING_ARG="--compaction-thinking-level $compaction_thinking_level"
fi

uv run python -m cua_bench.batch.solver ./tasks/game/${task} \
    --eval \
    --agent openclaw-agent \
    --model $model_id \
    --max-steps "$MAX_STEPS" \
    --output-dir $EVALUATION_OUTPUT_DIR \
    $SUMMARY_MODEL_ARG \
    $THINKING_ARG \
    $FLUSH_THINKING_ARG \
    $COMPACTION_THINKING_ARG



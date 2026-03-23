#!/bin/bash
# Generic retry loop: runs the agent then evaluates, repeating until eval succeeds.
# First run includes setup; subsequent runs skip it.
#
# Usage:
#   bash run_task_loop.sh <task_path> [max_steps] [max_attempts] [model] [summary_model]
#
# Examples:
#   bash run_task_loop.sh ./tasks/game/mota_24_easy 500 5 openai/gpt-5.4 openai/gpt-5.4
#   bash run_task_loop.sh ./tasks/helloworld 50 3
#   bash run_task_loop.sh ./tasks/game/mota_24 200 5 anthropic/claude-opus-4-6

set -euo pipefail

TASK_PATH="${1:?Usage: bash run_task_loop.sh <task_path> [max_steps] [max_attempts] [model] [summary_model]}"
MAX_STEPS="${2:-50}"
MAX_ATTEMPTS="${3:-999}"
model_id="${4:-anthropic/claude-haiku-4-5-20251001}"
summary_model_id="${5:-$model_id}"

# Derive task name from path (e.g. ./tasks/game/mota_24_easy → mota_24_easy)
task=$(basename "$TASK_PATH")

# --- Environment config ---
export CUA_ENV_API_URL="http://${VM_IP}:5000"
export CUA_ENV_TYPE="windows"
export CUA_TELEMETRY_DISABLED="true"
export CUA_ENV_VNC_URL=""
export XDG_DATA_HOME="./trycua"
export MEMORY_TASK_ID="${task}"
export EVALUATION_OUTPUT_DIR="./trycua/cua-bench/${task}"

SUMMARY_MODEL_ARG=""
if [ -n "$summary_model_id" ]; then
    SUMMARY_MODEL_ARG="--summary-model $summary_model_id"
fi

EVAL_DIR="$EVALUATION_OUTPUT_DIR"

# --- Logging: tee all output to logs/<task>/<timestamp>.log ---
LOG_DIR="./logs/${task}"
mkdir -p "$LOG_DIR"
model_short=$(echo "$model_id" | sed 's|.*/||; s|-[0-9]*$||')
LOG_FILE="$LOG_DIR/$(date '+%Y%m%d_%H%M%S')_steps${MAX_STEPS}_attempts${MAX_ATTEMPTS}_${model_short}.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Log file: $LOG_FILE"

# --- Helper: run solver with given mode flags ---
run_solver() {
    uv run python -m cua_bench.batch.solver "$TASK_PATH" \
        --eval \
        --agent openclaw-agent \
        --model $model_id \
        --max-steps "$MAX_STEPS" \
        --output-dir $EVALUATION_OUTPUT_DIR \
        $SUMMARY_MODEL_ARG \
        "$@"
}

echo "=== Run Loop: task=$task, max_steps=$MAX_STEPS, max_attempts=$MAX_ATTEMPTS, model=$model_id, summary=$summary_model_id ==="

attempt=0
while [ "$attempt" -lt "$MAX_ATTEMPTS" ]; do
    attempt=$((attempt + 1))
    echo ""
    echo "========================================"
    echo "  Attempt $attempt / $MAX_ATTEMPTS"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================"

    if [ "$attempt" -eq 1 ]; then
        # First run: setup + agent + eval
        echo "[run] First run — setup + agent + eval..."
        run_solver || true
    else
        # Subsequent runs: skip setup, run agent, then eval separately
        echo "[run] Reusing existing environment — agent only..."
        run_solver --task-only || true

        echo "[eval] Running evaluation..."
        run_solver --evaluate-only || true
    fi

    # Check the latest evaluation JSON (find any *_evaluation_*.json)
    latest_eval=$(ls -t "$EVAL_DIR"/*_evaluation_*.json 2>/dev/null | head -1)
    if [ -z "$latest_eval" ]; then
        echo "[result] No evaluation file found — retrying"
        continue
    fi

    eval_summary=$(python3 -c "import json; d=json.load(open('$latest_eval'))['summary']; print(f\"{d['total_score']:.4f} {d['num_reference_files']}\")")
    total_score=$(echo "$eval_summary" | cut -d' ' -f1)
    num_ref=$(echo "$eval_summary" | cut -d' ' -f2)

    echo "[result] Score: $total_score / $num_ref  (eval: $latest_eval)"

    if python3 -c "exit(0 if $total_score >= 1.0 else 1)"; then
        echo ""
        echo "========================================="
        echo "  SUCCESS on attempt $attempt!"
        echo "  Score: $total_score / $num_ref"
        echo "========================================="
        exit 0
    fi

    echo "[result] Not all milestones passed — retrying..."
done

echo ""
echo "========================================="
echo "  FAILED after $MAX_ATTEMPTS attempts"
echo "========================================="
exit 1

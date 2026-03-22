#!/bin/bash
# Retry loop: runs the agent then evaluates, repeating until eval succeeds.
# First run includes setup (opens game); subsequent runs skip it.
#
# Usage:
#   bash run_magic_tower_loop.sh [max_steps] [max_attempts]
#   bash run_magic_tower_loop.sh 50        # 50 steps, unlimited attempts
#   bash run_magic_tower_loop.sh 50 10     # 50 steps, max 10 attempts

set -euo pipefail

MAX_STEPS="${1:-50}"
MAX_ATTEMPTS="${2:-999}"

# --- Same env config as run_magic_tower.sh ---
export CUA_ENV_API_URL="http://${VM_IP}:5000"
export CUA_ENV_TYPE="windows"
export CUA_TELEMETRY_DISABLED="true"
export CUA_ENV_VNC_URL=""
export XDG_DATA_HOME="./trycua"
task="mota_24_easy"
export MEMORY_TASK_ID="${task}"
export EVALUATION_OUTPUT_DIR="./trycua/cua-bench/${task}"

model_id="anthropic/claude-haiku-4-5-20251001"
summary_model_id="anthropic/claude-haiku-4-5-20251001"

SUMMARY_MODEL_ARG=""
if [ -n "$summary_model_id" ]; then
    SUMMARY_MODEL_ARG="--summary-model $summary_model_id"
fi

EVAL_DIR="$EVALUATION_OUTPUT_DIR"
TASK_TAG="GAME_MOTA_24_EZ"

# --- Logging: tee all output to logs/loop_run/<timestamp>.log ---
LOG_DIR="./logs/loop_run"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date '+%Y%m%d_%H%M%S')_steps${MAX_STEPS}_attempts${MAX_ATTEMPTS}.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Log file: $LOG_FILE"

# --- Helper: run solver with given mode flags ---
run_solver() {
    uv run python -m cua_bench.batch.solver ./tasks/game/${task} \
        --eval \
        --agent openclaw-agent \
        --model $model_id \
        --max-steps "$MAX_STEPS" \
        --output-dir $EVALUATION_OUTPUT_DIR \
        $SUMMARY_MODEL_ARG \
        "$@"
}

echo "=== Run Loop: max_steps=$MAX_STEPS, max_attempts=$MAX_ATTEMPTS ==="

attempt=0
while [ "$attempt" -lt "$MAX_ATTEMPTS" ]; do
    attempt=$((attempt + 1))
    echo ""
    echo "========================================"
    echo "  Attempt $attempt / $MAX_ATTEMPTS"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================"

    if [ "$attempt" -eq 1 ]; then
        # First run: setup (opens game) + agent + eval
        echo "[run] First run — setup + agent + eval..."
        run_solver || true
    else
        # Subsequent runs: skip setup, run agent, then eval separately
        echo "[run] Reusing existing game — agent only..."
        run_solver --task-only || true

        echo "[eval] Running evaluation..."
        run_solver --evaluate-only || true
    fi

    # Check the latest evaluation JSON
    latest_eval=$(ls -t "$EVAL_DIR"/${TASK_TAG}_evaluation_*.json 2>/dev/null | head -1)
    if [ -z "$latest_eval" ]; then
        echo "[result] No evaluation file found — retrying"
        continue
    fi

    total_score=$(python3 -c "import json; d=json.load(open('$latest_eval')); print(d['summary']['total_score'])")
    num_ref=$(python3 -c "import json; d=json.load(open('$latest_eval')); print(d['summary']['num_reference_files'])")

    echo "[result] Score: $total_score / $num_ref  (eval: $latest_eval)"

    if python3 -c "exit(0 if $total_score >= $num_ref else 1)"; then
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

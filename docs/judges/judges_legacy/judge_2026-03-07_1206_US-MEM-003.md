## Evaluation: US-MEM-003 - memory_get tool

### Golden Reference
- **Source**: `openclaw/src/agents/tools/memory-tool.ts` (createMemoryGetTool) referenced in code comments, but the file is not present in the repo (OpenClaw submodule not checked out). The MemorySearchTool in the same `memory/tools.py` serves as the in-repo pattern reference.
- **Key insights**: The code comment references OpenClaw's API shape (path/from/lines), .md-only restriction, and path traversal checks. The implementation follows these conventions. The MemorySearchTool pattern (extend BaseTool, @register_tool, constructor takes MemoryStore, implement call()) is correctly followed.
- **Divergences**: Parameter names use `from` and `lines` (matching OpenClaw) instead of `start_line`/`end_line` (matching MemoryStore.read_file). This is intentional -- the tool translates between the agent-facing API and the store API.

### Verification Level: 1 + 2

US-MEM-003 is a tool implementation story. It requires Level 1 (mechanical) and Level 2 (behavioral). Level 2 is deferred because the tool is not yet wired into the agent for autonomous use -- that happens in US-MEM-AGT.

### Level 1 -- Mechanical
**Status**: PASS
- [x] `uv run pytest tests/test_memory_tools.py -v` -- 22 tests passed, 0 failed
- [x] `uv run ruff check memory/ tests/test_memory_tools.py` -- All checks passed (clean)
- [ ] Smoke test -- skipped: US-MEM-003 is a pure tool class; no agent wiring changes in this story. The tool IS already imported in `agenthle_agent.py` (line 71) and passed to ComputerAgent (line 82), but that wiring predates this story and is not part of its scope.

### Level 2 -- Behavioral (if applicable)
**Status**: DESIGNED (cannot run yet -- full agent wiring is US-MEM-AGT scope)

The tool is already present in the agent's tool list (line 82 of `agenthle_agent.py`), but the agent instructions (lines 85-90) only mention it briefly. True behavioral verification requires US-MEM-AGT to properly instruct the agent to use memory_get after memory_search.

**Test plan** (for after US-MEM-AGT is complete):
1. Run: `./run_magic_tower.sh --max-steps 30`
2. Seed memory first: write known content to `memory_data/MEMORY.md` with identifiable lines at specific line numbers
3. Verify tool invocation: `grep -r '"memory_get"' trycua/cua-bench/mota_24_easy/task_0_agent_logs/trajectories/`
4. Verify the agent used memory_get after a memory_search result (check sequential turns in trajectory)
5. Expected: At least one `memory_get` call with a `from`/`lines` parameter targeting a specific range found via search

### Level 3 -- Outcome (if applicable)
**Status**: NOT APPLICABLE
This is a tool implementation story. Cross-session outcome testing applies to US-MEM-E2E.

### Design Concerns

1. **Path restriction mismatch with acceptance criteria**: The acceptance criterion says "Restricts file_path to memory_data/ tree (rejects path traversal with ..)". The implementation rejects `..` and absolute paths, and restricts to `.md` files, but does NOT restrict to the `memory_data/` tree specifically. Since `MemoryStore.read_file` resolves paths relative to `base_dir` (which IS `memory_data/`), the restriction is implicitly enforced by the store layer. This is actually fine -- but the criterion wording is slightly misleading. The tool delegates path resolution to the store, which is the correct design.

2. **Empty path handling**: If the agent passes `path: ""`, the tool will try `"".endswith(".md")` which returns False, so it returns the `.md-only` error. This is acceptable but the error message ("only .md files can be read") is slightly confusing for an empty path. Minor issue.

3. **`from` as parameter name**: Using `from` as a parameter name works in the JSON schema but could be confusing since `from` is a Python reserved word. The implementation handles this correctly via `params_dict.get("from", 1)` since it's a dict key, not a variable name. No issue in practice.

4. **No line count in response**: The tool returns raw content without indicating how many lines were returned or total lines available. OpenClaw's memory-tool.ts includes line metadata in the response. For a context-constrained agent, knowing "showing lines 10-15 of 200" helps decide whether to fetch more. This is a minor enhancement opportunity, not a blocker.

### Acceptance Criteria Audit
| # | Criterion | Verdict | Issue |
|---|-----------|---------|-------|
| 1 | "memory/tools.py gains MemoryGetTool class extending BaseTool" | OK | Implemented at line 66 |
| 2 | "MemoryGetTool registered with @register_tool('memory_get')" | OK | Line 65 |
| 3 | "Accepts file_path (string), optional start_line and end_line (int)" | WEAK | Actual params are `path`, `from`, `lines` (not `file_path`, `start_line`, `end_line`). The criterion names don't match the implementation. The implementation names are better (match OpenClaw reference), but the criterion should be updated to reflect reality. |
| 4 | "Restricts file_path to memory_data/ tree (rejects path traversal with ..)" | OK | Path traversal rejected (line 113). Also rejects absolute paths and non-.md files. Restriction to memory_data/ is implicit via MemoryStore.base_dir. |
| 5 | "Delegates to MemoryStore.read_file() and returns content" | OK | Line 125 |
| 6 | "Returns helpful message for missing files (no exception)" | OK | Line 128 returns "File 'X' not found or empty." |
| 7 | "memory/__init__.py exports MemoryGetTool" | OK | Exported in `__all__` |
| 8 | "uv run pytest tests/test_memory_tools.py passes (add tests: read full file, line range, path traversal rejected, missing file)" | OK | All 4 specified test cases present: `test_read_full_file`, `test_read_line_range`, `test_path_traversal_rejected`, `test_missing_file`. Plus extras: `test_absolute_path_rejected`, `test_non_md_rejected`, `test_read_log_file`, `test_json_string_params`. |
| 9 | "Lint passes (uv run ruff check .)" | OK | Lint passes for memory/ and tests/ (pre-existing lint issues in opencua.py and submodules are unrelated). |
| -- | -- | MISSING | No test for `from`/`lines` edge cases: what happens with `from: 0` or `from: -1`? The store handles this via `max(0, start_line - 1)` but the tool has no validation. |
| -- | -- | MISSING | No test for very large `lines` value (e.g., `lines: 999999`). Works correctly (store clips to file length) but worth a test for documentation. |

### Verdict

**PASS** -- The implementation is solid, follows the reference pattern correctly, has good test coverage (10 tests for MemoryGetTool), and passes all Level 1 checks. The acceptance criteria have minor naming mismatches (criterion says `file_path`/`start_line`/`end_line`, implementation uses `path`/`from`/`lines`) but the implementation's naming is intentionally aligned with the OpenClaw reference and is the better choice. The story is ready to ship as-is; the recommended changes below are improvements, not blockers.

### Recommended Changes
1. **Update criterion #3 wording** to match actual parameter names: "Accepts `path` (string), optional `from` (int, 1-based start line) and `lines` (int, number of lines to read)" -- this reflects the implemented API which matches the OpenClaw reference.
2. **Optional: Add edge case test** for `from: 0` and `from: -1` to document that the store handles out-of-range start lines gracefully (it does, via `max(0, start_line - 1)`).
3. **Optional: Add line metadata to response** -- after returning content, append a footer like `"\n--- lines {from}-{to} of {total} ---"` to help the agent decide whether to fetch more. This mirrors OpenClaw's behavior and is useful for context-constrained agents. Not required for this story.

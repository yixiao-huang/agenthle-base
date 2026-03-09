"""Quick integration check for task-scoped storage (US-MEM-TSK-S).
Run: uv run python scripts/verify_task_storage.py
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory.store import MemoryStore

BASE = Path("memory_data")

# 1. Create task-scoped store
store = MemoryStore(BASE, task_id="test_verify")

# 2. Init session — should create tasks/test_verify/session-001.md
p1 = store.init_session()
assert p1 == "tasks/test_verify/session-001.md", f"unexpected: {p1}"
assert (BASE / p1).exists()

# 3. Append to session log
store.append_to_session_log("Observation: floor 1 has a yellow door")
content = (BASE / p1).read_text()
assert "yellow door" in content

# 4. Write and read task memory
store.write_task_memory("# Task Memory\nYellow door needs yellow key.\n")
assert "yellow key" in store.read_task_memory()

# 5. Second session increments
p2 = store.init_session()
assert p2 == "tasks/test_verify/session-002.md"

# 6. List session files
files = store.list_session_files()
assert len(files) == 2

# 7. Scoped search finds task files + global
store.write_memory("Global: agent strategies\n")
results = store.search(["yellow"])
assert any("TASK_MEMORY" in r.file_path for r in results)

# 8. Cleanup test dir
import shutil
shutil.rmtree(BASE / "tasks" / "test_verify")
print("✓ All task-scoped storage checks passed")

#!/usr/bin/env python3
"""Level 2 verification: call_planner with a realistic compaction prompt.

Usage:
    uv run python scripts/verify_planner.py

Requires OPENAI_API_KEY to be set.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory.planner import call_planner

SYSTEM_PROMPT = """\
You are a memory compaction assistant. Merge the following session observations
into a concise, actionable summary. Remove contradictions, deduplicate, and
keep only knowledge useful for future sessions of the same task."""

USER_PROMPT = """\
Session observations from a Magic Tower game run:

- Started on floor 1, moved right to pick up a key
- Encountered a yellow door on the right side of floor 1, opened it with a key
- Found a sword behind the yellow door that increases ATK by 10
- Went upstairs to floor 2
- Floor 2 has enemies on the left (slimes, ATK=15, DEF=5, HP=40)
- Tried fighting slimes on floor 2 but took too much damage
- Found a potion on floor 2 that restores 50 HP
- Key observation: should collect all items on a floor before moving up
- The yellow key on floor 1 can also open the door on floor 3
- Contradiction: earlier thought floor 2 had no items, but found potion later
- Strategy: always explore full floor before going up stairs"""


async def main():
    print("=== Testing call_planner with default model (gpt-4.1-mini) ===\n")

    result = await call_planner(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=USER_PROMPT,
    )

    print(f"Response ({len(result)} chars):\n")
    print(result)
    print()

    if not result or len(result) < 20:
        print("FAIL: Response too short or empty")
        sys.exit(1)

    print("=== Testing with explicit model (gpt-4.1-mini) ===\n")

    result2 = await call_planner(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=USER_PROMPT,
        model="gpt-4.1-mini",
    )

    print(f"Response ({len(result2)} chars):\n")
    print(result2)
    print()

    if not result2 or len(result2) < 20:
        print("FAIL: Response too short or empty")
        sys.exit(1)

    print("PASS: Both calls returned non-empty, coherent responses.")


if __name__ == "__main__":
    asyncio.run(main())

# US-OC-034: Expose Trajectory Screenshot Path in Computer Call Output

## Problem

Every computer call (mouse click, keyboard press, etc.) automatically takes a screenshot and returns it to the agent as inline base64. The `TrajectorySaverCallback` also saves this screenshot to a local file (e.g., `trycua/.../turn_005/0003_screenshot_after.png`), but the agent never learns this path.

This matters because:
- After compaction, the base64 image is removed from context — the agent loses access to old screenshots
- With `analyze_image` (US-OC-033), the agent *could* re-examine old screenshots if it knew the local path
- The path survives compaction as text in the summary, while the image does not

## Solution

Inject the local screenshot path as text metadata into each computer call output, so the agent sees both:
1. The base64 image (for immediate visual processing)
2. The local file path (for later re-examination via `analyze_image`)

After compaction, the image is gone but the path text persists in the summary, enabling post-compaction image recall.

### What the agent sees today

```json
{
  "type": "computer_call_output",
  "call_id": "...",
  "output": {
    "type": "input_image",
    "image_url": "data:image/png;base64,..."
  }
}
```

### What the agent should see after this story

The agent receives the same image, plus a text note with the local path. The exact injection mechanism depends on the implementation approach (see below), but conceptually:

```
[Screenshot saved to: /Users/.../trycua/.../turn_005/0003_screenshot_after.png]
```

This text is small (~100 chars) and survives compaction summarization, so the agent can reference it turns later.

## Implementation

### Recommended: Callback approach (no CUA core changes)

Create a `ScreenshotPathCallback` in our OpenClaw module that tracks and injects paths.

**File**: `submodules/cua/libs/cua-bench/cua_bench/agents/openclaw/tools.py` (alongside `ToolLoggingCallback`)

```python
class ScreenshotPathCallback(AsyncCallbackHandler):
    """Injects local screenshot file path into computer call outputs.

    Works with TrajectorySaverCallback: after it saves a screenshot to disk,
    this callback picks up the path and appends it as text metadata to the
    computer_call_output, so the agent knows where to find the file later.
    """

    def __init__(self):
        self._last_screenshot_path: str | None = None

    async def on_screenshot(self, screenshot, name="screenshot"):
        """Record the screenshot name — we'll reconstruct the path in on_computer_call_end."""
        # TrajectorySaverCallback saves to: turn_dir / f"{artifact_idx:04d}_{name}.png"
        # We need the trajectory_saver's current turn_dir and artifact index.
        # Option A: Accept trajectory_saver as a constructor arg and read its state.
        # Option B: Accept trajectory_dir and track turn/artifact counts ourselves.
        self._last_screenshot_name = name

    async def on_computer_call_end(self, item, result):
        """Append screenshot path to the computer call output."""
        if self._last_screenshot_path and result:
            # Inject path as additional metadata
            for r in result:
                if r.get("type") == "computer_call_output":
                    # Add path to output dict
                    r["screenshot_path"] = self._last_screenshot_path
            self._last_screenshot_path = None
```

**Key challenge**: The callback needs to know the exact file path that `TrajectorySaverCallback` used. Two options:

#### Option A: Pass TrajectorySaverCallback reference

```python
class ScreenshotPathCallback(AsyncCallbackHandler):
    def __init__(self, trajectory_saver: TrajectorySaverCallback):
        self.trajectory_saver = trajectory_saver

    async def on_screenshot(self, screenshot, name="screenshot"):
        # Reconstruct path from trajectory_saver's state
        turn_dir = self.trajectory_saver._get_turn_dir()
        artifact_idx = self.trajectory_saver.current_artifact - 1  # just incremented
        self._last_screenshot_path = str(turn_dir / f"{artifact_idx:04d}_{name}.png")
```

Pro: Exact path, no duplication. Con: Relies on TrajectorySaverCallback internals and callback ordering.

#### Option B: Track independently

```python
class ScreenshotPathCallback(AsyncCallbackHandler):
    def __init__(self, trajectory_dir: Path):
        self.trajectory_dir = trajectory_dir
        # Mirror TrajectorySaverCallback's state
        ...
```

Pro: No dependency on TrajectorySaverCallback internals. Con: Duplicates state tracking, could drift.

**Recommendation**: Option A — the `TrajectorySaverCallback` is already created by `ComputerAgent.__init__()` when `trajectory_dir` is set. We can access it from `agent.callbacks` after construction. The ordering concern is manageable: ensure `ScreenshotPathCallback` is added AFTER `TrajectorySaverCallback` in the callbacks list.

### How to inject the path into agent-visible context

The `computer_call_output` dict flows through `responses.py` which converts it to API messages. Adding a new field like `screenshot_path` won't automatically be visible to the model. Options:

1. **Modify the output dict**: Add path as text alongside the image. This requires changes to `responses.py` to handle the extra field — probably not worth it.

2. **Inject a separate message**: After the `computer_call_output`, inject a small assistant or system message with the path. This is fragile.

3. **Modify `on_computer_call_end` to mutate the result**: The callback receives `result` (a list of dicts). Append a `function_call_output`-style text message:

```python
async def on_computer_call_end(self, item, result):
    if self._last_screenshot_path:
        result.append({
            "type": "function_call_output",
            "call_id": item.get("call_id"),
            "output": f"[Screenshot saved to: {self._last_screenshot_path}]",
        })
        self._last_screenshot_path = None
```

Wait — this won't work because `function_call_output` with the same `call_id` would conflict.

4. **(Recommended) Extend the output text**: The cleanest approach is to override `_handle_item` in `OpenClawComputerAgent` to append path info to the output after the parent builds it:

```python
# In OpenClawComputerAgent (agent_loop.py)
async def _handle_item(self, item, computer=None, ignore_call_ids=None):
    result = await super()._handle_item(item, computer, ignore_call_ids)

    # Inject screenshot path if available
    if result and self._trajectory_saver:
        for r in result:
            if r.get("type") == "computer_call_output":
                output = r.get("output", {})
                if output.get("type") == "input_image":
                    # Get the path from trajectory saver
                    path = self._get_last_screenshot_path()
                    if path:
                        r["screenshot_local_path"] = path
    return result
```

Then in `responses.py` conversion (or our OpenClaw override), include this path as part of the text content sent to the model.

### Simplest viable approach

Actually, the simplest approach that doesn't touch CUA internals at all:

**Override `_on_screenshot` in OpenClawComputerAgent** to track the path, then override `_handle_item` to append it.

Since `_on_screenshot` is called right before `call_output` is constructed (agent.py line 571), and `TrajectorySaverCallback.on_screenshot` saves the file during that same callback chain, we can read the path from the trajectory saver after `_on_screenshot` completes.

```python
# In OpenClawComputerAgent
async def _on_screenshot(self, screenshot, name="screenshot"):
    await super()._on_screenshot(screenshot, name)
    # After TrajectorySaverCallback has saved the file, record the path
    for cb in self.callbacks:
        if hasattr(cb, 'trajectory_dir') and hasattr(cb, 'current_artifact'):
            turn_dir = cb._get_turn_dir()
            idx = cb.current_artifact - 1
            self._last_screenshot_path = str(turn_dir / f"{idx:04d}_{name}.png")
            break
```

Then in `_handle_item` override, inject it into the output.

## Callback ordering

**Critical**: `TrajectorySaverCallback` must run its `on_screenshot` BEFORE our path-tracking logic reads the saved path. CUA processes callbacks in list order (`agent.py` line 502-504):

```python
for callback in self.callbacks:
    if hasattr(callback, "on_screenshot"):
        await callback.on_screenshot(screenshot, name)
```

Since `TrajectorySaverCallback` is auto-added by `ComputerAgent.__init__()` when `trajectory_dir` is set, and our callbacks are added later, the ordering should be correct by default. Verify this during implementation.

## Risks

1. **TrajectorySaverCallback internals**: We depend on `_get_turn_dir()` and `current_artifact` which are not public API. If CUA updates these, our code breaks. Mitigate by pinning the submodule version.
2. **No trajectory_dir**: When `trajectory_dir` is not set, `TrajectorySaverCallback` is not added. The path injection should gracefully skip — no crash, just no path in the output.
3. **Compaction summary quality**: The path text (e.g., `[Screenshot saved to: .../turn_005/0003_screenshot_after.png]`) must survive summarization. If the summarizer drops it as noise, the whole feature is useless. May need to add guidance in the summarization prompt to preserve file paths.
4. **Path format**: Local paths are absolute. If the agent runs on a different machine than where screenshots are saved, the paths won't resolve. In our setup this is always the same machine, but document the assumption.

## Relationship to US-OC-033

US-OC-033 (`analyze_image`) provides the tool to read images by path. This story (US-OC-034) provides the paths. Together they enable post-compaction image recall:

```
Turn 5: computer_call → screenshot saved → agent sees image + path text
Turn 20: compaction → image removed from context, path text survives in summary
Turn 25: agent calls analyze_image(image="/path/from/turn_5/screenshot.png", prompt="...")
         → reads local file → sends to VLM → returns text analysis
```

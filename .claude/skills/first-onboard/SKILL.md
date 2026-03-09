---
name: first-onboard
description: "One-time setup for a new server or fresh clone. Initializes git remotes, CUA submodule, and branch tracking. Run this once per machine, then use /onboard for subsequent sessions."
user-invocable: true
---

# First-Time Server Setup

One-time setup for working on AgentHLE from a new machine or fresh clone. Run this once, then use `/onboard` for all future sessions.

---

## Steps

### 1. Verify base repo remotes

Check that the three required remotes exist:

```bash
git remote -v
```

Expected remotes:

| Remote | Fetch URL | Push URL |
|--------|-----------|----------|
| `origin` | `git@github.com:yixiao-huang/agenthle-base.git` | `git@github.com:yixiao-huang/agenthle-base.git` |
| `private` | `git@github.com:yixiao-huang/agenthle-private.git` | `git@github.com:yixiao-huang/agenthle-private.git` |
| `upstream` | `git@github.com:cua-verse/agenthle-base.git` | `git@github.com:cua-verse/agenthle-base.git` |

If any are missing, add them:

```bash
git remote add origin git@github.com:yixiao-huang/agenthle-base.git 2>/dev/null || true
git remote add private git@github.com:yixiao-huang/agenthle-private.git 2>/dev/null || true
git remote add upstream git@github.com:cua-verse/agenthle-base.git 2>/dev/null || true
```

### 2. Checkout tinyclaw branch

```bash
git fetch private
git checkout tinyclaw
git pull private tinyclaw
```

### 3. Initialize CUA submodule

```bash
# Check if already initialized
if [ ! -f submodules/cua/.git ] && [ ! -d submodules/cua/.git ]; then
  echo "Initializing CUA submodule..."
  git submodule update --init submodules/cua
else
  echo "Submodule already initialized."
fi
```

### 4. Set up submodule remotes

The CUA submodule needs: fetch from upstream (`cua-verse/cua`), push to fork (`yixiao-huang/cua`).

```bash
cd submodules/cua

# Add fork remote if missing
if ! git remote | grep -q '^fork$'; then
  echo "Adding fork remote..."
  git remote add fork git@github.com:yixiao-huang/cua.git
fi

# Set push URL on origin to fork (fetch stays upstream)
git remote set-url --push origin git@github.com:yixiao-huang/cua.git

# Verify
git remote -v
cd ../..
```

### 5. Checkout submodule branch

```bash
cd submodules/cua
git fetch fork
git checkout tinyclaw-memory
git pull fork tinyclaw-memory
cd ../..
```

### 6. Verify setup

Run these and confirm the output looks right:

```bash
echo "=== Base repo ==="
git remote -v
git branch --show-current
git log --oneline -3

echo "=== CUA submodule ==="
cd submodules/cua
git remote -v
git branch --show-current
git log --oneline -3
cd ../..

echo "=== Submodule status ==="
git submodule status
```

Report the output to the user. Then tell them to use `/onboard` for all future sessions.

---

## Important Notes

- This skill should only be run **once per machine**. After setup, `/onboard` handles everything.
- If any step fails, stop and report the error — don't skip steps.

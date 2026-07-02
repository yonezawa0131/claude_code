---
name: session-start-hook
description: Create and validate a SessionStart hook that installs project dependencies so tests and linters work in Claude Code on the web sessions. Use when the user wants to set up a repository for Claude Code on the web, or asks for a startup / session-start hook.
---

# SessionStart Hook for Claude Code on the web

Create a SessionStart hook that installs dependencies, prove that linting and testing work with it, then commit and push.

## Reference

### Hook input (stdin)

```json
{
  "session_id": "abc123",
  "source": "startup|resume|clear|compact",
  "transcript_path": "/path/to/transcript.jsonl",
  "permission_mode": "default",
  "hook_event_name": "SessionStart",
  "cwd": "/workspace/repo"
}
```

### Environment variables

- `$CLAUDE_PROJECT_DIR` — repository root
- `$CLAUDE_ENV_FILE` — append `export` lines here to persist variables for the session:
  ```bash
  echo 'export PYTHONPATH="."' >> "$CLAUDE_ENV_FILE"
  ```
- `$CLAUDE_CODE_REMOTE` — `"true"` in remote (web) sessions. Guard the hook so it only runs there:
  ```bash
  if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
    exit 0
  fi
  ```

### Sync vs. async

Hooks run synchronously by default: the session waits for the hook, so dependencies are guaranteed to be ready. A hook can opt into async mode by printing a JSON line before doing any work:

```bash
echo '{"async": true, "asyncTimeout": 300000}'
```

Async mode starts the session while the hook still runs in the background — faster startup, but the agent may race ahead of the install. Default to synchronous; switch to async only if the user asks for it.

## Workflow

### 1. Analyze the project

Identify how dependencies are installed:

- Dependency manifests, e.g. `package.json` → npm, `pyproject.toml` / `requirements.txt` → pip/Poetry, `Cargo.toml` → cargo, `go.mod` → go, `Gemfile` → bundler
- README or similar docs describing environment setup
- Existing lint/test commands (scripts in `package.json`, `Makefile`, CI config)

If you cannot determine how to install dependencies or run lint/tests, ask the user instead of guessing.

### 2. Write the hook

Create `.claude/hooks/session-start.sh` — synchronous, web-only:

```bash
mkdir -p .claude/hooks
cat > .claude/hooks/session-start.sh << 'EOF'
#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Install dependencies here
EOF
chmod +x .claude/hooks/session-start.sh
```

Requirements:

- Idempotent (safe to run repeatedly) and non-interactive (no prompts)
- The container state is cached after the hook completes, so prefer install commands that reuse existing state (e.g. `npm install` over `npm ci`)
- If a SessionStart hook already exists, extend it rather than replacing it

### 3. Register the hook

Add to `.claude/settings.json`, merging with any existing configuration:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh"
          }
        ]
      }
    ]
  }
}
```

### 4. Validate

Run each check and fix the hook until all three pass:

1. Hook: `CLAUDE_CODE_REMOTE=true ./.claude/hooks/session-start.sh` completes successfully and dependencies are installed
2. Linter: run the project's linter on one example file (not the whole project)
3. Tests: run a single test (not the whole suite)

### 5. Commit and push

Commit the hook and settings, and push to the remote branch.

## Final report

End with a summary in this format:

* Summary of the changes made
* Validation results:
  1. ✅/‼️ Session hook execution (details if it failed)
  2. ✅/‼️ Linter execution (details if it failed)
  3. ✅/‼️ Test execution (details if it failed)
* Hook execution mode: Synchronous — explain that this guarantees dependencies are installed before the session starts (no race conditions), at the cost of waiting for the hook on startup, and offer to switch to async if they prefer faster startup
* Note that once the hook is merged into the repo's default branch, all future web sessions will use it

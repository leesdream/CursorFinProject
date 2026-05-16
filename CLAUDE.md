# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python-based financial project. Stack and architecture will grow as development progresses.

## Git & GitHub

Repository: https://github.com/leesdream/CursorFinProject

**Commit convention (Conventional Commits):**
- `feat:` — new feature
- `fix:` — bug fix
- `chore:` — tooling, config, dependencies
- `docs:` — documentation only
- `refactor:` — code restructure, no behavior change
- `test:` — adding or updating tests

Always commit with descriptive messages and push to keep the remote in sync:
```
git add <files>
git commit -m "feat: description of change"
git push
```

## Python Environment

Use a virtual environment in `.venv/` (excluded from git):
```
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FitBot — Python bot that automates booking fitness classes on aimharder.com with a Telegram bot interface. Deployed via Docker.

## Commands

```bash
make venv              # Create virtualenv and install deps
make format            # Format (black) + lint (flake8)
make format/check      # Check formatting/linting without modifying
make tests             # format/check + pytest (requires venv)

# Run tests directly (skips lint):
PYTHONPATH=src venv/bin/pytest src/tests

# Single test file:
PYTHONPATH=src venv/bin/pytest src/tests/test_client.py

# Single test:
PYTHONPATH=src venv/bin/pytest src/tests/test_client.py::TestLogin::test_login_too_many_wrong_attempts
```

PYTHONPATH must be set to `src` when running any Python code.

## Architecture

Three concurrent systems run from `src/main.py`:

1. **APScheduler BackgroundScheduler** — cron jobs for recurring weekly bookings
2. **BookingScheduler** (`booking_scheduler.py`) — one-time bookings via date triggers
3. **Telegram Bot** (`telegram_logger.py`) — user interface in polling mode using ConversationHandler for multi-step booking flows

Key modules:
- `client.py` — HTTP client for aimharder.com (login, list classes, book)
- `repository.py` — JSON file persistence (`schedule.json`) for users and booking goals
- `models.py` — `User` and `BookingGoal` dataclasses
- `error_handling.py` — generic `Result` class (Result pattern instead of exceptions for expected failures)
- `exceptions.py` — domain exceptions (login failures, booking errors)
- `box_data.py` — gym-specific config (box_id, box_name, days_in_advance)

Data flow for one-time bookings: Telegram command → ConversationHandler collects day/time/class → BookingScheduler creates job → Repository persists goal → job fires at (target_date - days_in_advance) → client books → Telegram notification.

## Testing

Tests use `unittest.mock.patch` for HTTP mocking and `freezegun` for time. All external calls are mocked. Test data lives in `src/test_schedule.json`.

## Code Style

- **black** with experimental string processing
- **flake8** for linting
- Python 3.10+ type hints (`str | None` style)

## Rules

### Git & Branching
- Always create feature branches off `master` — never commit directly to `master`
- Make atomic commits that are logically self-contained; when executing a multi-task plan, each task gets its own commit
- Claude Code may commit freely without asking for permission, as long as the current branch is not `master`

### Testing
- Every new feature or module must include tests

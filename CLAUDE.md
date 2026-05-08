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

Clean / hexagonal architecture: the domain layer defines models and port interfaces; application use cases orchestrate the ports; infrastructure adapters implement the ports against real services. `src/main.py` is the composition root — it wires adapters into use cases and starts the Telegram bot.

```
src/
├── main.py                              # composition root (bootstrap)
├── constants.py                         # aimharder URL/endpoint constants
├── schedule.json                        # JSON-backed user + booking-goal store
├── domain/                              # pure: no I/O, no framework imports
│   ├── models.py                        # User, BookingGoal, GymClass dataclasses
│   ├── exceptions.py                    # BookingFailed, AuthenticationFailed, UserNotFound
│   └── ports/                           # abstract interfaces (ABCs)
│       ├── user_repository.py           # IUserRepository
│       ├── booking_repository.py        # IBookingRepository
│       ├── gym_client.py                # IGymClient, IGymClientFactory
│       ├── gym_config.py                # IGymConfig (booking trigger time policy)
│       ├── scheduler.py                 # IJobScheduler
│       └── notifier.py                  # IUserNotifier, IGroupNotifier
├── application/
│   └── use_cases/
│       ├── schedule_booking.py          # ScheduleBookingUseCase
│       ├── execute_booking.py           # ExecuteBookingUseCase (fires at trigger time)
│       └── remove_booking.py            # RemoveBookingUseCase
├── infrastructure/                      # adapters; only this layer touches I/O
│   ├── aimharder/
│   │   ├── client.py                    # AimHarderClient (login, list, book)
│   │   ├── client_factory.py            # AimHarderClientFactory
│   │   ├── gym_config.py                # IAimHarderGym (box_id/box_name/days_in_advance)
│   │   ├── monkey_box_config.py         # env-backed gym config
│   │   ├── raw_booking.py               # API DTO → GymClass mapping
│   │   └── exceptions.py                # platform-specific error keys
│   ├── persistence/
│   │   └── json_repository.py           # JsonRepository implements both repo ports
│   ├── scheduling/
│   │   └── apscheduler.py               # APSchedulerAdapter (BackgroundScheduler + DateTrigger)
│   └── telegram/
│       ├── bot.py                       # TelegramBot (ConversationHandler for /add, /schedule, /remove)
│       ├── user_notifier.py             # TelegramUserNotifier
│       └── group_notifier.py            # TelegramGroupNotifier + token loader
└── tests/
    ├── conftest.py
    ├── fakes.py                         # in-memory test doubles for ports
    ├── use_cases/                       # use-case tests (in-memory ports)
    ├── test_*.py                        # adapter tests (mocked I/O)
    └── test_integration.py              # cross-layer integration
```

Dependency rule: `domain` depends on nothing; `application` imports only `domain`; `infrastructure` and `main.py` depend on both. Adapters implement port interfaces and are injected by `main.bootstrap()`.

Data flow for a one-time booking:
1. Telegram `/add` → `ConversationHandler` collects day/time/class.
2. `ScheduleBookingUseCase` computes the trigger time via `IGymConfig.booking_trigger_time(class_start)`, registers a job with `IJobScheduler`, and persists a `BookingGoal` via `IBookingRepository`.
3. At trigger time, APScheduler invokes `ExecuteBookingUseCase` with `(user_id, booking_goal)`.
4. The use case builds an `IGymClient` for the user via `IGymClientFactory`, lists classes, books the matching one, removes the goal, and pushes a confirmation through `IUserNotifier`.
5. On startup, `bootstrap()` re-schedules every persisted goal to recover from restarts.

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

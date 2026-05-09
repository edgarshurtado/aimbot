# Clean Architecture Refactor — Implementation Plan

> **For Claude:** This plan is split across multiple files. Read this README for the
> dependency graph and execution order, then read individual feature files for task details.
> Dispatch a fresh subagent per task using the Task tool (subagent_type: "general-purpose").

**Goal:** Refactor the FitBot codebase into clean architecture with domain, application, and infrastructure layers to decouple business logic from framework concerns.

**Architecture:** Domain layer owns models, exceptions, and port interfaces. Application layer contains use cases (ScheduleBooking, ExecuteBooking, RemoveBooking) that orchestrate business logic through ports. Infrastructure layer provides concrete adapters (AimHarder HTTP client, JSON persistence, APScheduler, Telegram bot/notifiers). Composition root in `main.py` wires everything together.

**Tech Stack:** Python 3.10+, pytest, pytest-mock, freezegun, APScheduler, python-telegram-bot, requests, BeautifulSoup4

**Design Document:** `docs/plans/2026-02-28-clean-architecture-refactor-design.md`

## Plan Files

| File | Feature | Depends On |
|------|---------|------------|
| `task-0-scaffolding.md` | Domain layer: models, exceptions, ports | None |
| `feature-1-json-repository.md` | JsonRepository adapter (IUserRepository + IBookingRepository) | Task 0 |
| `feature-2-aimharder-client.md` | AimHarderClient + AimHarderClientFactory adapter | Task 0 |
| `feature-3-apscheduler-adapter.md` | APSchedulerAdapter (IJobScheduler) | Task 0 |
| `feature-4-schedule-booking.md` | ScheduleBookingUseCase | Task 0 |
| `feature-5-execute-booking.md` | ExecuteBookingUseCase | Task 0 |
| `feature-6-remove-booking.md` | RemoveBookingUseCase | Task 0 |
| `feature-7-telegram-notifiers.md` | TelegramGroupNotifier + TelegramUserNotifier | Task 0 |
| `feature-8-telegram-bot.md` | TelegramBot thin UI handlers | Features 1, 4, 5, 6, 7 |
| `feature-9-composition-root.md` | main.py wiring + old file cleanup | Features 1-8 |
| `integration.md` | End-to-end integration | All features |

## Dependency Graph

```
                    Task 0 (Scaffolding: domain models, exceptions, ports)
                    /    |     |     \      \       \        \
                   /     |     |      \      \       \        \
               F1-Repo  F2-Client F3-Sched F4-SchedUC F5-ExecUC F6-RemoveUC  F7-Notifiers
               (parallel — no file overlap between F1-F7)
                   \     |     |      /      /       /        /
                    \    |     |     /      /       /        /
                     F8-TelegramBot (depends on F1, F4, F5, F6, F7)
                            |
                     F9-CompositionRoot (depends on F1-F8)
                            |
                     Integration (depends on all)
```

**Parallel execution layers:**
- **Layer 0:** Task 0
- **Layer 1:** F1, F2, F3, F4, F5, F6, F7 (all parallel — zero file overlap)
- **Layer 2:** F8 (depends on Layer 1)
- **Layer 3:** F9 (depends on Layer 2)
- **Layer 4:** Integration (depends on Layer 3)

## Execution Instructions

**Recommended:** Execute using subagents for fresh context per task.

For each task, dispatch a fresh subagent using the Task tool:
- subagent_type: "general-purpose"
- Provide the FULL task text in the prompt (don't make subagent read this file)
- Include relevant context from earlier tasks (what was built, where files are)

**Execution order:**
- Tasks within a triplet are strictly sequential: N.1 -> N.2 -> N.3
- Independent triplets MAY run in parallel ONLY if they have zero file overlap (no shared created/modified files)
- Dependent triplets are sequential: complete triplet N before starting triplet M
- If the dependency graph says two features are parallel, they MUST NOT modify any overlapping files — this was verified during planning

**Never:**
- Skip a test-writing task (N.1) — "I'll write tests with the implementation"
- Skip an adversarial review task (N.3) — "The tests already pass, it's fine"
- Combine tasks within a triplet — each is a separate subagent dispatch
- Proceed to N.2 if N.1 tests don't compile/exist
- Proceed to N.3 if N.2 tests don't pass
- Proceed to next triplet if N.3 verdict is FAIL

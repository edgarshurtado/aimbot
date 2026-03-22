# Design: Separate Gym Config from Platform Client

**Date:** 2026-03-22

## Problem

The current port layer conflates two unrelated concerns:

1. `IGymPlatformConfig.booking_trigger_time` — when a gym opens bookings (e.g. "3 days in advance", or "on Sunday evening for the whole week"). This is a **gym** rule, not a platform rule.
2. `IGymClientFactory` / `IGymClient` — how to talk to the booking **platform** (Aimharder, WODBuster, etc.).

`AimHarderClientFactory` implements both `IGymClientFactory` and `IGymPlatformConfig`, mixing gym-level rules with platform client creation in one concrete class.

The four domain actors are:
1. **Gym** (MonkeyBox, ColisseumBox) — defines when bookings open
2. **GymClass** — the class being booked (model)
3. **Platform** (Aimharder, WODBuster) — HTTP interface for making bookings
4. **User** — has credentials on a platform, authorized to book at a gym

## Design

### Port layer

Split `domain/ports/gym_client.py` — remove `IGymPlatformConfig`. It stays with only:

```python
# domain/ports/gym_client.py
class IGymClient(ABC):
    def get_classes(self, target_day: datetime) -> list[GymClass]: ...
    def book_class(self, gym_class: GymClass) -> None: ...

class IGymClientFactory(ABC):
    def create(self, user: User) -> IGymClient: ...
```

Add a new port file for gym-level rules:

```python
# domain/ports/gym_config.py
class IGymConfig(ABC):
    @abstractmethod
    def booking_trigger_time(self, class_start: datetime) -> datetime: ...
```

`booking_trigger_time` accepts the class start datetime and returns the datetime at which the booking job should fire. The logic can be arbitrary — a simple day offset or a rule like "open Sunday evening for the whole week."

### Infrastructure layer

`AimHarderClientFactory` drops the `IGymPlatformConfig` implementation and only handles platform client creation:

```python
# infrastructure/aimharder/client_factory.py
class AimHarderClientFactory(IGymClientFactory):
    def __init__(self, box_id: int, box_name: str) -> None: ...
    def create(self, user: User) -> AimHarderClient: ...
```

A new concrete class implements the gym booking rule, co-located with `box_data.py`:

```python
# infrastructure/monkey_box_config.py
class MonkeyBoxConfig(IGymConfig):
    def booking_trigger_time(self, class_start: datetime) -> datetime:
        return class_start - timedelta(days=days_in_advance)
```

Future gym configs with arbitrary trigger logic (e.g. Sunday-opens-week) implement `IGymConfig` the same way.

### Composition root (`main.py`)

```python
factory = AimHarderClientFactory(box_id=box_id, box_name=box_name)
gym_config = MonkeyBoxConfig()

execute_uc = ExecuteBookingUseCase(json_repo, json_repo, factory, user_notifier, group_notifier)
schedule_uc = ScheduleBookingUseCase(json_repo, json_repo, apscheduler, gym_config)
```

`ScheduleBookingUseCase` now receives an `IGymConfig` — not a factory, not a platform concept.

## Change surface

| File | Change |
|---|---|
| `domain/ports/gym_client.py` | Remove `IGymPlatformConfig` |
| `domain/ports/gym_config.py` | **New** — `IGymConfig` |
| `infrastructure/aimharder/client_factory.py` | Remove `IGymPlatformConfig` impl |
| `infrastructure/monkey_box_config.py` | **New** — `MonkeyBoxConfig(IGymConfig)` |
| `application/use_cases/schedule_booking.py` | Import `IGymConfig` instead of `IGymPlatformConfig` |
| `main.py` | Inject `MonkeyBoxConfig()` separately from `factory` |
| `src/tests/*` | Update references to `IGymPlatformConfig` |

Everything else — `IGymClient`, `IGymClientFactory`, `AimHarderClient`, `ExecuteBookingUseCase`, `RemoveBookingUseCase` — is unchanged.

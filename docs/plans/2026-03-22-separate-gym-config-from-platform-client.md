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

#### AimHarder gym interface

`IAimHarderGym` extends `IGymConfig` with the platform-specific properties that AimHarder needs (`box_id`, `box_name`, `days_in_advance`). It provides a default `booking_trigger_time` based on `days_in_advance`:

```python
# infrastructure/aimharder/gym_config.py
class IAimHarderGym(IGymConfig):
    @property
    @abstractmethod
    def box_id(self) -> int: ...

    @property
    @abstractmethod
    def box_name(self) -> str: ...

    @property
    @abstractmethod
    def days_in_advance(self) -> int: ...

    def booking_trigger_time(self, class_start: datetime) -> datetime:
        return class_start - timedelta(days=self.days_in_advance)
```

#### Concrete gym config

`MonkeyBoxConfig` implements `IAimHarderGym`, loading all values from environment variables:

```python
# infrastructure/aimharder/monkey_box_config.py
class MonkeyBoxConfig(IAimHarderGym):
    def __init__(self) -> None:
        self._box_id = int(os.environ["BOX_ID"])
        self._box_name = os.environ["BOX_NAME"]
        self._days_in_advance = int(os.environ["DAYS_IN_ADVANCE"])

    @property
    def box_id(self) -> int: return self._box_id
    @property
    def box_name(self) -> str: return self._box_name
    @property
    def days_in_advance(self) -> int: return self._days_in_advance
```

#### Client factory

`AimHarderClientFactory` takes an `IAimHarderGym` instead of raw `box_id`/`box_name` params:

```python
# infrastructure/aimharder/client_factory.py
class AimHarderClientFactory(IGymClientFactory):
    def __init__(self, gym: IAimHarderGym) -> None:
        self._gym = gym

    def create(self, user: User) -> AimHarderClient:
        return AimHarderClient(user.email, user.password, self._gym.box_id, self._gym.box_name)
```

#### Environment variables

`box_data.py` is deleted. `BOX_ID`, `BOX_NAME`, and `DAYS_IN_ADVANCE` move to `.env`:

```env
BOX_ID=9824
BOX_NAME=themonkeybox
DAYS_IN_ADVANCE=3
```

### Composition root (`main.py`)

```python
gym_config = MonkeyBoxConfig()           # reads from .env
factory = AimHarderClientFactory(gym=gym_config)

execute_uc = ExecuteBookingUseCase(json_repo, json_repo, factory, user_notifier, group_notifier)
schedule_uc = ScheduleBookingUseCase(json_repo, json_repo, apscheduler, gym_config)
```

`MonkeyBoxConfig` is the single source of gym configuration. It is injected into `ScheduleBookingUseCase` as an `IGymConfig` (for booking trigger logic) and into `AimHarderClientFactory` as an `IAimHarderGym` (for platform-specific properties).

## Change surface

| File | Change |
|---|---|
| `domain/ports/gym_client.py` | Remove `IGymPlatformConfig` |
| `domain/ports/gym_config.py` | **New** — `IGymConfig` port |
| `infrastructure/aimharder/gym_config.py` | **New** — `IAimHarderGym(IGymConfig)` with default `booking_trigger_time` |
| `infrastructure/aimharder/monkey_box_config.py` | **New** — `MonkeyBoxConfig(IAimHarderGym)`, reads `.env` |
| `infrastructure/aimharder/client_factory.py` | Remove `IGymPlatformConfig` impl, take `IAimHarderGym` in constructor |
| `application/use_cases/schedule_booking.py` | Import `IGymConfig` instead of `IGymPlatformConfig` |
| `main.py` | Create `MonkeyBoxConfig()`, pass to factory and schedule use case |
| `box_data.py` | **Deleted** — values move to `.env` |
| `.env` | Add `BOX_ID`, `BOX_NAME`, `DAYS_IN_ADVANCE` |
| `src/tests/*` | Update references to `IGymPlatformConfig` |

Everything else — `IGymClient`, `AimHarderClient`, `ExecuteBookingUseCase`, `RemoveBookingUseCase` — is unchanged.

# Remove Provider ID from GymClass Domain Model

## Problem

`GymClass.id` is an AimHarder-specific identifier that leaks infrastructure concerns into the domain. The domain never inspects or reasons about this ID — it only shuttles it from `get_classes()` back to `book_class()`. If a second provider (e.g., WODBuster) doesn't use class IDs, the domain model breaks.

## Design

### Domain model

Drop `id` from `GymClass`. Rename `start_time: time` to `scheduled_at: datetime` so the model is self-describing (carries both date and time).

```python
@dataclass
class GymClass:
    name: str
    scheduled_at: datetime
    spots_available: int
    max_spots: int
```

### Port changes

`IGymClient.book_class` accepts a `GymClass` instead of a raw `class_id`:

```python
class IGymClient(ABC):
    @abstractmethod
    def get_classes(self, target_day: datetime) -> list[GymClass]: ...

    @abstractmethod
    def book_class(self, gym_class: GymClass) -> None: ...
```

### Use case changes

`ExecuteBookingUseCase.execute` passes the matched `GymClass` directly:

```python
matched = next(
    (c for c in classes if c.scheduled_at == booking_date and class_name in c.name),
    None,
)
client.book_class(matched)
```

### Adapter changes (AimHarderClient)

The adapter maintains an internal mapping from `(name, scheduled_at)` to the AimHarder-specific ID, built during `get_classes()`:

```python
def get_classes(self, target_day: datetime) -> list[GymClass]:
    ...
    for b in bookings:
        gym_class = b.to_gym_class(target_day.date())
        self._id_map[(gym_class.name, gym_class.scheduled_at)] = b.id
        classes.append(gym_class)
    return classes

def book_class(self, gym_class: GymClass) -> None:
    class_id = self._id_map[(gym_class.name, gym_class.scheduled_at)]
    # POST with class_id as before
```

The key is `(name, scheduled_at)` — not just `scheduled_at` — because two classes can share the same time slot (e.g., "WOD" and "OPEN" both at 10:00).

### RawBooking changes

`to_gym_class()` receives a `date` parameter to build the full `datetime`:

```python
def to_gym_class(self, day: date) -> GymClass:
    return GymClass(
        name=self.class_name,
        scheduled_at=datetime.combine(day, _normalize_timeid(self.timeid)),
        spots_available=self.spots_available,
        max_spots=self.limit,
    )
```

## Test impact

### test_execute_booking.py (8 tests)

- All `GymClass` constructions: drop `id`, `start_time=time(...)` becomes `scheduled_at=datetime(...)`.
- `book_class` assertions change from `client.book_class.assert_called_once_with(datetime(...), "42")` to `client.book_class.assert_called_once_with(matched_gym_class)`.

### test_aimharder.py (13 tests)

- `get_classes` tests: assert `scheduled_at` (full datetime) instead of `id` and `start_time`.
- `book_class` tests: must call `get_classes` first to populate the ID mapping, then call `book_class(gym_class)`. This is valid — you shouldn't book a class you haven't listed.
- `RawBooking.to_gym_class()` tests: pass a `date` parameter.

### test_integration.py (1 test)

- `test_execute_booking_with_real_repo_mocked_http`: update `GymClass` construction.

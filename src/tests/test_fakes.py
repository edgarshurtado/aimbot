"""The in-memory test doubles must honour the same promises the real adapters do.

Use-case tests run against these fakes instead of the real repositories, so a
fake that is looser than its adapter lets a bug pass here and fail in
production. These tests pin down the isolation guarantee the fakes must not
weaken.
"""

from datetime import datetime

from domain.models import BookingGoal, User
from tests.fakes import InMemoryUserRepository

DEFAULT_USER = User(
    id=1,
    email="a@b.com",
    password="pw",
    booking_goals=[
        BookingGoal(class_start=datetime(2027, 6, 15, 10, 0), class_name="WOD")
    ],
)


def test_get_user_returns_deep_copy():
    """Mutating a goal reached through the returned User must not reach the store."""
    repository = InMemoryUserRepository(users=[DEFAULT_USER])

    user = repository.get_user(1)
    user.booking_goals[0].class_name = "MUTATED"

    user2 = repository.get_user(1)
    assert user2.booking_goals[0].class_name == "WOD"

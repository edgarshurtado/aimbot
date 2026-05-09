from abc import ABC, abstractmethod
from domain.models import User


class IUserRepository(ABC):
    @abstractmethod
    def get_user(self, user_id: int) -> User | None: ...

    @abstractmethod
    def get_all_users(self) -> list[User]: ...

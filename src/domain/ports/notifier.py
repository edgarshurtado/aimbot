from abc import ABC, abstractmethod


class IUserNotifier(ABC):
    @abstractmethod
    def notify_user(self, user_id: int, message: str) -> None: ...


class IGroupNotifier(ABC):
    @abstractmethod
    def notify_group(self, message: str) -> None: ...

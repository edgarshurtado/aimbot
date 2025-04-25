from typing import Generic, TypeVar

R = TypeVar('R')
E = TypeVar('E')


class Result(Generic[R, E]):
    def __init__(self, success:bool, data: R | None = None, error: E | None = None):
        self.success = success
        self.data = data
        self.error = error

class Error:
    pass

class UserNotFound(Error):
    pass
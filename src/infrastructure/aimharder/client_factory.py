from datetime import datetime, timedelta

from domain.ports.gym_client import IGymClientFactory, IGymPlatformConfig
from infrastructure.aimharder.client import AimHarderClient


class AimHarderClientFactory(IGymClientFactory, IGymPlatformConfig):
    def __init__(self, box_id: int, box_name: str) -> None:
        self._box_id = box_id
        self._box_name = box_name

    def create(self, email: str, password: str) -> AimHarderClient:
        return AimHarderClient(email, password, self._box_id, self._box_name)

    def booking_trigger_time(self, class_date: datetime) -> datetime:
        return class_date - timedelta(days=3)

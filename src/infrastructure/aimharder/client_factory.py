from domain.models import User
from domain.ports.gym_client import IGymClientFactory
from infrastructure.aimharder.client import AimHarderClient
from infrastructure.aimharder.gym_config import IAimHarderGym


class AimHarderClientFactory(IGymClientFactory):
    def __init__(self, gym: IAimHarderGym) -> None:
        self._gym = gym

    def create(self, user: User) -> AimHarderClient:
        return AimHarderClient(user.email, user.password, self._gym.box_id, self._gym.box_name)

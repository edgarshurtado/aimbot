import os

from infrastructure.aimharder.gym_config import IAimHarderGym


class MonkeyBoxConfig(IAimHarderGym):
    def __init__(self) -> None:
        self._box_id = int(os.environ["MONKEY_BOX_ID"])
        self._box_name = os.environ["MONKEY_BOX_NAME"]
        self._days_in_advance = int(os.environ["MONKEY_BOX_DAYS_IN_ADVANCE"])

    @property
    def box_id(self) -> int:
        return self._box_id

    @property
    def box_name(self) -> str:
        return self._box_name

    @property
    def days_in_advance(self) -> int:
        return self._days_in_advance

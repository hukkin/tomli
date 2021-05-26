import datetime
from typing import Any, Optional


class CustomTzinfo(datetime.tzinfo):
    def __init__(self, offset: datetime.timedelta) -> None:
        self._offset = offset

    def __deepcopy__(self, memo: Any) -> Any:
        return type(self)(self._offset)

    def utcoffset(self, dt: Optional[datetime.datetime]) -> datetime.timedelta:
        return self._offset

    def dst(self, dt: Optional[datetime.datetime]) -> None:
        return None

    def tzname(self, dt: Optional[datetime.datetime]) -> None:
        return None

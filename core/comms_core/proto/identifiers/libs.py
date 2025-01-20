import threading

from pydantic import BaseModel


class Sid(BaseModel):
    """Unique identifier for a shell within the session."""
    value: int
    def __str__(self):
        return str(self.value)

class Uid(BaseModel):
    """Unique identifier for a user within the session."""
    value: int
    def __str__(self):
        return str(self.value)


class IdCounter:
    """Counter for generating unique identifiers."""
    def __init__(self):
        self.__next_sid = 1
        self.__next_uid = 1
        self._lock = threading.Lock()

    async def get_sid(self) -> int:
        with self._lock:
            return self.__next_sid

    async def set_sid(self, sid):
        with self._lock:
            self.__next_sid = sid

    async def get_uid(self) -> int:
        with self._lock:
            return self.__next_uid

    async def set_uid(self, uid):
        with self._lock:
            self.__next_uid = uid


    async def incr_sid(self) -> Sid:
        with self._lock:
            sid = Sid(value=self.__next_sid)
            self.__next_sid += 1
            return sid

    async def incr_uid(self) -> Uid:
        with self._lock:
            uid = Uid(value=self.__next_uid)
            self.__next_uid += 1
            return uid
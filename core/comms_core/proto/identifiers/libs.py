from typing import Self

from pydantic import BaseModel

from core.comms_core.utils.rw_lock import ReadWriteLock


class Sid(BaseModel):
    """Unique identifier for a shell within the session."""
    value: int
    def __str__(self):
        return str(self.value)

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: Self) -> bool:
        if isinstance(other, Sid):
            return self.value == other.value
        return False

class Uid(BaseModel):
    """Unique identifier for a user within the session."""
    value: int
    def __str__(self):
        return str(self.value)

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: Self) -> bool:
        if isinstance(other, Uid):
            return self.value == other.value
        return False


class IdCounter:
    """Counter for generating unique identifiers."""
    def __init__(self):
        self.__next_sid = ReadWriteLock(1)
        self.__next_uid = ReadWriteLock(1)

    async def get_sid(self) -> Sid:
        sid = await self.__next_sid.read()
        return Sid(value=sid)

    async def set_sid(self, sid):
        await self.__next_sid.write(sid)

    async def get_uid(self) -> Uid:
        uid = await self.__next_uid.read()
        return Uid(value=uid)

    async def set_uid(self, uid):
        await self.__next_uid.write(uid)


    async def incr_sid(self) -> Sid:
        """
        Increment the unique identifier for a shell within the session.

        This method reads the current SID value, increments it, and writes the new value back.
        It ensures that the increment operation is performed within a write lock to avoid race conditions.

        Returns:
            Sid: The new unique identifier for the shell.
        """
        val = await self.__next_sid.read()
        await self.__next_sid.acquire_write()
        sid = Sid(value=val)
        val+=1
        await self.__next_sid.release_write()
        await self.__next_sid.write(val)
        return sid


    async def incr_uid(self) -> Uid:
        """
        Increment the unique identifier for a user within the session.

        This method reads the current UID value, increments it, and writes the new value back.
        It ensures that the increment operation is performed within a write lock to avoid race conditions.

        Returns:
            Uid: The new unique identifier for the user.
        """
        val = await self.__next_uid.read()
        await self.__next_uid.acquire_write()
        uid = Uid(value=val)
        val+=1
        await self.__next_uid.release_write()
        await self.__next_uid.write(val)
        return uid
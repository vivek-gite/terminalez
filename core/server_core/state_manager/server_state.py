import asyncio
import logging
import time
from typing import Dict, AsyncGenerator

from core.comms_core.utils.rw_lock import ReadWriteLock
from core.server_core.mesh_handle.mesh import SessionMesh
from core.server_core.state_capture import checkpoint
from core.server_core.state_manager.session import Session

logger = logging.getLogger(__name__)

class ServerState:
    def __init__(self):
        # Fine-grained lock which lets us lock on a per-key basis instead of the entire state
        # key: session_id -> which is made up of 10-random numbers
        self.store_fgMap: Dict[str, ReadWriteLock[Session]] = {}


        self.mesh = SessionMesh()

    def lookup(self, name: str) -> ReadWriteLock[Session] | None:
        """
        Retrieves the Session's ReadWriteLock associated with the given session name.

        Args:
            name (str): The name of the session to look up.

        Returns:
            ReadWriteLock[Session]: The ReadWriteLock associated with the session, or None if not found.
        """
        return self.store_fgMap.get(name)

    async def insert(self, name: str, session: Session):
        """
        Inserts or replaces a session in the store.
        This method adds a new session to the store with the given name. If a session
        with the same name already exists, it shuts down the old session before replacing it.
        It also creates a background task to periodically synchronize the session.

       Args:
           name (str): The name or identifier for the session.
           session (Session): The session object to be inserted.
        """
        # Create a tracked task for session synchronization
        sync_task = None
        
        # Check for existing session and handle it safely
        if name in self.store_fgMap:
            try:
                print("shutting down in insert")
                # Use a timeout to prevent indefinite waiting
                old_session_lock = self.store_fgMap[name]
                old_session = await asyncio.wait_for(old_session_lock.read(), timeout=10.0)
                await old_session.shutdown_session()
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"Failed to properly shutdown existing session {name}: {e}")
                # Continue with replacement anyway
        
        # Create a new ReadWriteLock with the session
        session_lock = ReadWriteLock(session)
        
        # Store the reference first, then start the background task
        self.store_fgMap[name] = session_lock
        
        # Create a tracked background task
        sync_task = asyncio.create_task(self.mesh.periodic_session_sync(name, session))
        
        # Store the task reference on the session for proper cleanup later
        session.background_tasks = session.background_tasks or []
        session.background_tasks.append(sync_task)
        
        logger.info(f"Session {name} inserted into the store.")

    async def remove(self, name: str):
        print("shutting down in remove")
        session: ReadWriteLock = self.store_fgMap.pop(name)
        old_session: Session= await session.read()
        await old_session.shutdown_session()


    async def close_session(self, name: str):
        await self.remove(name)
        await self.mesh.mark_closed(name)


    async def backend_connect(self, name: str) -> ReadWriteLock[Session] | None:
        """
        Connects to the backend session.

        This method checks if the session with the given name exists in the store.
        If it does, it returns the corresponding ReadWriteLock. If not, it retrieves
        the session from the mesh, restores it from the checkpoint, inserts it into
        the store, and broadcasts the transfer.

        Args:
            name (str): The name of the session to connect to.

        Returns:
            ReadWriteLock: The ReadWriteLock associated with the session.

        Raises:
            Exception: If the session with the given name is not found in the mesh.
        """
        if name in self.store_fgMap:
            return self.lookup(name)

        parent, session_checkpoint = await self.mesh.get_session(name)
        if parent is None:
            return None

        session = Session()
        await checkpoint.checkpoint_restore(data=session_checkpoint, session=session)
        await self.insert(name, session)
        await self.mesh.broadcast_transfer(name=name)
        return self.lookup(name)



    def frontend_connect(self, name: str) -> ReadWriteLock[Session]:
        if name in self.store_fgMap:
            print(f"found in store {name}")
            return self.lookup(name)

        raise Exception(f"Session {name} not found in the store")


    async def process_transfer(self) -> None:
        """
        Processes transfer events from the mesh.

        This method subscribes to transfer events from the mesh and removes the corresponding
        sessions from the store when a transfer event is received.

        Raises:
            Exception: If there is an error while processing transfers.
        """
        try:
            transfer_generator: AsyncGenerator[str, None] = self.mesh.subscribe_transfers()

            async for name in transfer_generator:
                self.store_fgMap.pop(name)
        except Exception as e:
            logger.exception(f"Error in process_transfers: {e}")



    async def close_expired_sessions(self):
        """
        Periodically closes expired sessions.

        This method runs an infinite loop that sleeps for 60 seconds between iterations.
        In each iteration, it checks all sessions in the store and closes those that have
        not been accessed for more than 5 mins.

        Raises:
            Exception: If there is an error while closing sessions.
        """
        while True:
            # sleep for 60 secs
            await asyncio.sleep(60)

            for key, value in self.store_fgMap.items():
                session: Session = await value.read()
                if session.last_accessed() - time.time() > 300:
                    await self.close_session(key)



    async def shutdown_all_sessions(self):
        for values in self.store_fgMap.values():
            session: Session = await values.read()
            await session.shutdown_session()


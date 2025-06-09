import asyncio
import logging
import time
from typing import Dict, AsyncGenerator, Set

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
        
        # Track background tasks for proper cleanup
        self._background_tasks: Set[asyncio.Task] = set()
        
        # Lock for managing the store_fgMap to prevent race conditions
        self._store_lock = asyncio.Lock()
        
        # Track session access times for efficient expiry checking
        self._session_access_times: Dict[str, float] = {}

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
        async with self._store_lock:
            # Check for existing session and handle it safely
            if name in self.store_fgMap:
                try:
                    logger.info(f"Replacing existing session {name}")
                    # Use a timeout to prevent indefinite waiting
                    old_session_lock = self.store_fgMap[name]
                    old_session = await asyncio.wait_for(old_session_lock.read(), timeout=10.0)

                    # Cancel and clean up any existing background tasks
                    if hasattr(old_session, 'background_tasks') and old_session.background_tasks:
                        for task in old_session.background_tasks:
                            if not task.done():
                                task.cancel()
                                try:
                                    await asyncio.wait_for(task, timeout=5.0)
                                except (asyncio.CancelledError, asyncio.TimeoutError):
                                    pass
                            self._background_tasks.discard(task)
                    
                    await old_session.shutdown_session()
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning(f"Failed to properly shutdown existing session {name}: {e}")
                    # Continue with replacement anyway
            
            # Create a new ReadWriteLock with the session
            session_lock = ReadWriteLock(session)
            
            # Store the reference first
            self.store_fgMap[name] = session_lock

            try:
                # Create a tracked background task
                sync_task = asyncio.create_task(self.mesh.periodic_session_sync(name, session))
                self._background_tasks.add(sync_task)
                
                # Store the task reference on the session for proper cleanup later
                if not hasattr(session, 'background_tasks'):
                    session.background_tasks = []
                session.background_tasks.append(sync_task)
                
                # Add cleanup callback when task completes
                sync_task.add_done_callback(lambda t: self._background_tasks.discard(t))
                
                logger.info(f"Session {name} inserted into the store with background sync task")
                
            except Exception as e:
                # If task creation fails, remove the session from store
                logger.error(f"Failed to create background task for session {name}: {e}")
                self.store_fgMap.pop(name, None)
                raise
    
    async def remove(self, name: str):
        """
        Safely removes a session from the store with proper cleanup.
        
        Args:
            name (str): The name of the session to remove.
        """
        async with self._store_lock:
            if name not in self.store_fgMap:
                logger.warning(f"Attempted to remove non-existent session: {name}")
                return
            
            logger.info(f"Removing session {name}")
            
            try:
                session_lock: ReadWriteLock = self.store_fgMap.pop(name)
                
                # Get the session with timeout to prevent hanging
                old_session: Session = await asyncio.wait_for(session_lock.read(), timeout=10.0)
                
                # Shutdown the session
                await old_session.shutdown_session()
                logger.info(f"Successfully removed session {name}")
                
            except (asyncio.TimeoutError, Exception) as e:
                logger.error(f"Error removing session {name}: {e}") # Ensure the session is removed from tracking even if cleanup fails
                self.store_fgMap.pop(name, None)

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
        """
        Connects to a frontend session.
        
        Args:
            name (str): The name of the session to connect to.
            
        Returns:
            ReadWriteLock[Session]: The session lock.
            
        Raises:
            Exception: If the session is not found.
        """
        if name in self.store_fgMap:
            logger.debug(f"Found session {name} in store")
            return self.lookup(name)

        raise Exception(f"Session {name} not found in the store")

    async def process_transfer(self) -> None:
        """
        Processes transfer events from the mesh with proper error handling.

        This method subscribes to transfer events from the mesh and safely removes 
        the corresponding sessions from the store when a transfer event is received.

        Raises:
            Exception: If there is an error while processing transfers.
        """
        try:
            transfer_generator: AsyncGenerator[str, None] = self.mesh.subscribe_transfers()

            async for name in transfer_generator:
                async with self._store_lock:
                    if name in self.store_fgMap:
                        logger.info(f"Processing transfer for session {name}")
                        self.store_fgMap.pop(name, None)
                    else:
                        logger.warning(f"Transfer event for non-existent session: {name}")
                        
        except Exception as e:
            logger.exception(f"Error in process_transfers: {e}")
            raise

    async def close_expired_sessions(self):
        """
        Periodically closes expired sessions.
        """
        await self._periodic_cleanup()
    
    async def _periodic_cleanup(self):
        """
        Efficient periodic cleanup of expired sessions and background tasks.
        
        This method runs every 60 seconds and:
        1. Cleans up expired sessions based on access time
        2. Removes completed background tasks
        3. Handles exceptions gracefully
        """
        while True:
            try:
                await asyncio.sleep(60)
                current_time = time.time()
                expired_sessions = []
                
                # Find expired sessions efficiently using access times
                for session_name, session_rw_lock in list(self.store_fgMap.items()):
                    try:
                        session = await asyncio.wait_for(session_rw_lock.read(), timeout=5.0)
                        last_access = session.last_accessed()
                        if current_time - last_access > 300:  # 5 minutes
                            expired_sessions.append(session_name)
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout while checking session {session_name}, skipping")
                    except Exception as e:
                        logger.error(f"Error accessing session {session_name}: {e}")
                
                # Close expired sessions
                for session_name in expired_sessions:
                    try:
                        logger.info(f"Closing expired session: {session_name}")
                        await self.close_session(session_name)
                    except Exception as e:
                        logger.error(f"Failed to close expired session {session_name}: {e}")
                
                # Clean up completed background tasks
                completed_tasks = {task for task in self._background_tasks if task.done()}
                for task in completed_tasks:
                    self._background_tasks.discard(task)
                    if task.exception():
                        logger.warning(f"Background task completed with exception: {task.exception()}")
                
                if expired_sessions or completed_tasks:
                    logger.info(f"Cleanup completed: {len(expired_sessions)} expired sessions, "
                              f"{len(completed_tasks)} completed tasks removed")
                              
            except Exception as e:
                logger.exception(f"Error in periodic cleanup: {e}")
                # Continue the loop even if cleanup fails

    async def shutdown_all_sessions(self):
        """
        Gracefully shutdown all sessions and cleanup resources.
        
        This method:
        1. Cancels all background tasks
        2. Shuts down all sessions with timeout protection
        3. Cleans up all tracking data structures
        """
        logger.info("Starting graceful shutdown of all sessions")
        
        # Cancel all background tasks first
        logger.info(f"Cancelling {len(self._background_tasks)} background tasks")
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete with timeout
        if self._background_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._background_tasks, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some background tasks did not complete within timeout")
        
        # Shutdown all sessions
        session_names = list(self.store_fgMap.keys())
        logger.info(f"Shutting down {len(session_names)} sessions")
        
        shutdown_tasks = []
        for name in session_names:
            try:
                session_lock = self.store_fgMap.get(name)
                if session_lock:
                    session = await asyncio.wait_for(session_lock.read(), timeout=5.0)
                    shutdown_tasks.append(session.shutdown_session())
            except (asyncio.TimeoutError, Exception) as e:
                logger.error(f"Failed to prepare shutdown for session {name}: {e}")
        
        # Execute all shutdowns concurrently with timeout
        if shutdown_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*shutdown_tasks, return_exceptions=True),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some sessions did not shutdown within timeout")
        
        # Clear all tracking data
        self.store_fgMap.clear()
        self._background_tasks.clear()
        
        logger.info("All sessions shutdown completed")

    async def get_session_count(self) -> int:
        """
        Get the current number of active sessions.
        
        Returns:
            int: Number of active sessions.
        """
        return len(self.store_fgMap)
    
    async def get_session_info(self) -> Dict[str, Dict[str, any]]:
        """
        Get information about all active sessions.
        
        Returns:
            Dict containing session information including access times and task counts.
        """
        info = {}
        current_time = time.time()
        
        for name, session_lock in self.store_fgMap.items():
            try:
                session = await asyncio.wait_for(session_lock.read(), timeout=2.0)
                last_access = session.last_accessed()
                task_count = len(getattr(session, 'background_tasks', []))
                
                info[name] = {
                    'last_access_time': last_access,
                    'seconds_since_access': current_time - last_access,
                    'background_task_count': task_count,
                    'is_expired': (current_time - last_access) > 300
                }
            except (asyncio.TimeoutError, Exception) as e:
                info[name] = {
                    'error': str(e),
                    'background_task_count': 0,
                    'is_expired': True
                }
        
        return info
    
    async def force_cleanup_session(self, name: str) -> bool:
        """
        Force cleanup of a specific session, even if it appears to be stuck.
        
        Args:
            name (str): The name of the session to force cleanup.
            
        Returns:
            bool: True if cleanup was successful, False otherwise.
        """
        try:
            logger.warning(f"Force cleaning up session: {name}")
            
            # Remove from store immediately
            session_lock = self.store_fgMap.pop(name, None)
            
            if session_lock:
                try:
                    # Try to get session with very short timeout
                    session = await asyncio.wait_for(session_lock.read(), timeout=1.0)
                    
                    # Cancel background tasks aggressively
                    if hasattr(session, 'background_tasks') and session.background_tasks:
                        for task in session.background_tasks:
                            if not task.done():
                                task.cancel()
                            self._background_tasks.discard(task)
                    
                    # Try to shutdown with timeout
                    await asyncio.wait_for(session.shutdown_session(), timeout=5.0)
                    
                except (asyncio.TimeoutError, Exception) as e:
                    logger.error(f"Session {name} did not respond to graceful shutdown: {e}")
                    # Continue anyway - session is already removed from store
            
            logger.info(f"Force cleanup of session {name} completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to force cleanup session {name}: {e}")
            return False


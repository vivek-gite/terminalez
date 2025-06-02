import asyncio
import logging
from typing import Dict, Set, Optional, List
import weakref

logger = logging.getLogger(__name__)

class TaskRegistry:
    """
    A utility class to track, manage, and clean up asyncio tasks.
    Prevents orphaned tasks by ensuring proper cleanup on errors.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        # Store tasks by context (e.g., session_id, function name)
        self._task_registry: Dict[str, Set[asyncio.Task]] = {}
        # Enable debug mode for detailed task tracking
        self._debug = False
    
    def register_task(self, task: asyncio.Task, context: str) -> asyncio.Task:
        """
        Register a task with a specific context identifier.
        Returns the task for convenience in chaining.
        """
        if context not in self._task_registry:
            self._task_registry[context] = set()
            
        self._task_registry[context].add(task)
        
        # Create a callback to remove the task when it's done
        def _remove_task_when_done(fut):
            try:
                if context in self._task_registry and fut in self._task_registry[context]:
                    self._task_registry[context].remove(fut)
                    if self._debug:
                        logger.debug(f"Task removed from registry: {fut.get_name()} in context {context}")
                    # Clean up empty sets
                    if not self._task_registry[context]:
                        del self._task_registry[context]
            except Exception as e:
                logger.error(f"Error removing task from registry: {e}")
                
        task.add_done_callback(_remove_task_when_done)
        
        if self._debug:
            logger.debug(f"Registered task: {task.get_name()} in context {context}")
            
        return task
    
    def create_task(self, coro, name: Optional[str] = None, context: str = "global") -> asyncio.Task:
        """
        Create and register a task in one operation.
        """
        task = asyncio.create_task(coro, name=name)
        return self.register_task(task, context)
        
    async def cancel_context_tasks(self, context: str, timeout: float = 5.0) -> int:
        """
        Cancel all tasks for a specific context with a timeout.
        Returns the number of tasks that were canceled.
        """
        if context not in self._task_registry:
            return 0
            
        tasks = list(self._task_registry[context])
        count = len(tasks)
        
        if not tasks:
            return 0
            
        logger.info(f"Canceling {count} task(s) for context: {context}")
        
        # Cancel all tasks
        for task in tasks:
            if not task.done() and not task.cancelled():
                task.cancel()
        
        # Wait for all tasks to complete cancellation with timeout
        try:
            await asyncio.wait(tasks, timeout=timeout)
        except Exception as e:
            logger.warning(f"Error waiting for tasks to cancel in context {context}: {e}")
        
        # Check if any tasks are still not done
        still_running = sum(1 for t in tasks if not t.done())
        if still_running:
            logger.warning(f"{still_running} task(s) in context {context} failed to cancel within timeout")
        
        return count
        
    def get_context_task_count(self, context: str) -> int:
        """Get the number of tasks currently registered for a context."""
        if context not in self._task_registry:
            return 0
        return len(self._task_registry[context])
        
    def set_debug(self, debug: bool):
        """Enable or disable debug logging."""
        self._debug = debug
        
    def get_all_contexts(self) -> List[str]:
        """Get a list of all active contexts."""
        return list(self._task_registry.keys())

# Singleton instance
task_registry = TaskRegistry()
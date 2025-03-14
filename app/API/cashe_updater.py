import threading
import time
import logging
from typing import Callable

logger = logging.getLogger("news-updater")

class NewsUpdater:
    """A class that automatically updates news at a set interval."""
    
    def __init__(self, update_interval: int = 600, update_function: Callable = None):
        """
        Initialize the NewsUpdater.
        
        Args:
            update_interval: Time in seconds between updates
            update_function: Function to call for updates
        """
        self.update_interval = update_interval
        self.update_function = update_function
        self.is_running = False
        self.thread = None
        logger.info(f"NewsUpdater initialized with {update_interval}s interval")
    
    def _update_loop(self):
        """Internal loop that runs in a separate thread."""
        logger.info("Update loop started")
        while self.is_running:
            try:
                if self.update_function:
                    logger.info("Running update function")
                    self.update_function()
                else:
                    logger.warning("No update function set")
            except Exception as e:
                logger.error(f"Error during update: {e}")
            
            # Sleep for the interval
            logger.info(f"Sleeping for {self.update_interval}s until next update")
            time.sleep(self.update_interval)
    
    def start(self):
        """Start the automatic update process."""
        if self.is_running:
            logger.warning("Update loop already running")
            return
            
        self.is_running = True
        self.thread = threading.Thread(target=self._update_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info("Started update thread")
    
    def stop(self):
        """Stop the automatic update process."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1)
            logger.info("Stopped update thread")
    
    def set_update_function(self, update_function: Callable):
        """Set the function to call for updates."""
        self.update_function = update_function
        logger.info("Update function set")
    
    def set_interval(self, interval: int):
        """Change the update interval."""
        self.update_interval = interval
        logger.info(f"Update interval changed to {interval}s")

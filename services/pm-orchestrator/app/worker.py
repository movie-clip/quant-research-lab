import threading
import time

from .config import settings
from .orchestrator import Orchestrator


class Worker(threading.Thread):
    def __init__(self, orchestrator: Orchestrator):
        super().__init__(daemon=True)
        self.orchestrator = orchestrator
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            processed = self.orchestrator.process_next_task()
            if not processed:
                time.sleep(settings.worker_poll_interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()

from __future__ import annotations

from collections.abc import Callable
from queue import Empty, Queue
from threading import Event, Thread


class BackgroundWorker:
    def __init__(
        self,
        name: str,
        handler: Callable[[str], None],
        poll_interval_seconds: float = 0.1,
    ) -> None:
        self._name = name
        self._handler = handler
        self._poll_interval_seconds = poll_interval_seconds
        self._queue: Queue[str] = Queue()
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def submit(self, item: str) -> None:
        self._queue.put(item)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def queued_items(self) -> int:
        return self._queue.qsize()

    def _run(self) -> None:
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                item = self._queue.get(timeout=self._poll_interval_seconds)
            except Empty:
                continue
            try:
                self._handler(item)
            finally:
                self._queue.task_done()

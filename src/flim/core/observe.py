"""A small observer utility: objects that send change messages to subscribers."""

import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)


class Observable:
    """Sends change messages to the callables subscribed to it.

    A subscriber that raises is logged and does not stop the others.
    """

    def __init__(self) -> None:
        """Create an observable without subscribers."""
        self._subscribers: list[Callable[[Any], None]] = []
        self._subscribers_lock = threading.Lock()

    def subscribe(self, callback: Callable[[Any], None]) -> Callable[[], None]:
        """Subscribe to the change messages.

        Args:
            callback: Called with each message, in the thread that made the change.
                The same callable subscribed twice is called twice.

        Returns:
            A function that ends the subscription; calling it again has no effect.
        """
        with self._subscribers_lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._subscribers_lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def notify(self, message: Any) -> None:
        """Send a message to every subscriber.

        The subscribers are called in the order they subscribed. An exception raised
        by a subscriber is logged and the remaining subscribers are still called.

        Args:
            message: The change message.
        """
        with self._subscribers_lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(message)
            except Exception:
                logger.exception(f"A subscriber failed on {message!r}")

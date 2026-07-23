"""Optional, technology-neutral queue hooks for future live integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class QueuePublisher(Protocol):
    """Minimal boundary that RabbitMQ, Kafka or another broker can implement."""

    def publish(self, queue_name: str, payload: dict[str, Any]) -> None:
        """Publish one JSON-serializable payload."""


@dataclass(frozen=True)
class QueueOptions:
    """Queue hooks are deliberately disabled unless explicitly enabled."""

    whisper_enabled: bool = False
    analysis_enabled: bool = False
    whisper_queue_name: str = "stereo.whisper"
    analysis_queue_name: str = "stereo.analysis"


@dataclass(frozen=True)
class QueueDispatch:
    queue_name: str
    status: str
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_name": self.queue_name,
            "status": self.status,
            "payload": self.payload,
        }


class InMemoryQueuePublisher:
    """Small adapter useful for integration tests and local demonstrations."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, Any]]] = []

    def publish(self, queue_name: str, payload: dict[str, Any]) -> None:
        self.messages.append((queue_name, payload))

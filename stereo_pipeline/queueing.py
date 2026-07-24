"""Optional, technology-neutral queue hooks for future live integration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol


class QueuePublisher(Protocol):
    """Minimal boundary that RabbitMQ, Kafka or another broker can implement."""

    def publish(self, queue_name: str, payload: dict[str, Any]) -> None:
        """Publish one JSON-serializable payload."""


@dataclass(frozen=True)
class QueueOptions:
    """Queue hooks are disabled unless explicitly enabled through configuration."""

    whisper_enabled: bool = False
    analysis_enabled: bool = False
    whisper_queue_name: str = "stereo.whisper"
    analysis_queue_name: str = "stereo.analysis"

    @classmethod
    def from_env(cls) -> "QueueOptions":
        return cls(
            whisper_enabled=_env_bool("STEREO_WHISPER_QUEUE_ENABLED", False),
            analysis_enabled=_env_bool("STEREO_ANALYSIS_QUEUE_ENABLED", False),
            whisper_queue_name=os.getenv(
                "STEREO_WHISPER_QUEUE_NAME",
                "stereo.whisper",
            ),
            analysis_queue_name=os.getenv(
                "STEREO_ANALYSIS_QUEUE_NAME",
                "stereo.analysis",
            ),
        )


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


@dataclass(frozen=True)
class RabbitMQConfig:
    """RabbitMQ connection values loaded only from environment configuration."""

    host: str = "127.0.0.1"
    port: int = 5672
    username: str = "guest"
    password: str = "guest"
    virtual_host: str = "/"
    heartbeat: int = 60
    blocked_connection_timeout: float = 30.0
    connection_attempts: int = 3
    retry_delay: float = 2.0

    @classmethod
    def from_env(cls) -> "RabbitMQConfig":
        return cls(
            host=os.getenv("RABBITMQ_HOST", "127.0.0.1"),
            port=int(os.getenv("RABBITMQ_PORT", "5672")),
            username=os.getenv("RABBITMQ_USER", "guest"),
            password=os.getenv("RABBITMQ_PASSWORD", "guest"),
            virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
            heartbeat=int(os.getenv("RABBITMQ_HEARTBEAT", "60")),
            blocked_connection_timeout=float(
                os.getenv("RABBITMQ_BLOCKED_TIMEOUT", "30")
            ),
            connection_attempts=int(
                os.getenv("RABBITMQ_CONNECTION_ATTEMPTS", "3")
            ),
            retry_delay=float(os.getenv("RABBITMQ_RETRY_DELAY", "2")),
        )


class RabbitMQQueuePublisher:
    """Publish durable JSON messages with short-lived RabbitMQ connections."""

    def __init__(self, config: RabbitMQConfig | None = None) -> None:
        self.config = config or RabbitMQConfig.from_env()

    def publish(self, queue_name: str, payload: dict[str, Any]) -> None:
        if not queue_name.strip():
            raise ValueError("RabbitMQ queue adı boş olamaz")
        try:
            import pika
        except ImportError as exc:
            raise RuntimeError(
                "RabbitMQ için pika paketi kurulu değil; requirements.txt'i yükleyin"
            ) from exc

        credentials = pika.PlainCredentials(
            self.config.username,
            self.config.password,
        )
        parameters = pika.ConnectionParameters(
            host=self.config.host,
            port=self.config.port,
            virtual_host=self.config.virtual_host,
            credentials=credentials,
            heartbeat=self.config.heartbeat,
            blocked_connection_timeout=self.config.blocked_connection_timeout,
            connection_attempts=self.config.connection_attempts,
            retry_delay=self.config.retry_delay,
        )
        connection = pika.BlockingConnection(parameters)
        try:
            channel = connection.channel()
            channel.queue_declare(queue=queue_name, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    content_encoding="utf-8",
                    delivery_mode=2,
                ),
                mandatory=True,
            )
        finally:
            if connection.is_open:
                connection.close()


def build_queue_publisher_from_env(
    options: QueueOptions,
) -> QueuePublisher | None:
    """Create RabbitMQ only when at least one queue hook is enabled."""
    if not options.whisper_enabled and not options.analysis_enabled:
        return None
    backend = os.getenv("STEREO_QUEUE_BACKEND", "rabbitmq").strip().lower()
    if backend != "rabbitmq":
        raise ValueError(f"Desteklenmeyen queue backend: {backend}")
    return RabbitMQQueuePublisher(RabbitMQConfig.from_env())


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} boolean olmalıdır; alınan değer: {value!r}")

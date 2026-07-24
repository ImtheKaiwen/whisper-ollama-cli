from __future__ import annotations

import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from stereo_pipeline.queueing import (
    QueueOptions,
    RabbitMQConfig,
    RabbitMQQueuePublisher,
    build_queue_publisher_from_env,
)


class _FakeChannel:
    def __init__(self) -> None:
        self.declarations: list[dict] = []
        self.messages: list[dict] = []

    def queue_declare(self, **kwargs) -> None:
        self.declarations.append(kwargs)

    def basic_publish(self, **kwargs) -> None:
        self.messages.append(kwargs)


class _FakeConnection:
    def __init__(self, parameters) -> None:
        self.parameters = parameters
        self.fake_channel = _FakeChannel()
        self.is_open = True

    def channel(self) -> _FakeChannel:
        return self.fake_channel

    def close(self) -> None:
        self.is_open = False


class QueueConfigurationTests(unittest.TestCase):
    def test_env_configuration_controls_queue_and_connection(self) -> None:
        values = {
            "STEREO_WHISPER_QUEUE_ENABLED": "true",
            "STEREO_ANALYSIS_QUEUE_ENABLED": "false",
            "STEREO_WHISPER_QUEUE_NAME": "custom.whisper",
            "RABBITMQ_HOST": "rabbit.internal",
            "RABBITMQ_PORT": "5673",
            "RABBITMQ_USER": "worker",
            "RABBITMQ_PASSWORD": "secret",
            "RABBITMQ_VHOST": "/calls",
        }
        with patch.dict(os.environ, values, clear=True):
            options = QueueOptions.from_env()
            config = RabbitMQConfig.from_env()
            publisher = build_queue_publisher_from_env(options)

        self.assertTrue(options.whisper_enabled)
        self.assertFalse(options.analysis_enabled)
        self.assertEqual(options.whisper_queue_name, "custom.whisper")
        self.assertEqual(config.host, "rabbit.internal")
        self.assertEqual(config.port, 5673)
        self.assertEqual(config.username, "worker")
        self.assertEqual(config.virtual_host, "/calls")
        self.assertIsInstance(publisher, RabbitMQQueuePublisher)

    def test_disabled_hooks_do_not_create_rabbitmq_publisher(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            options = QueueOptions.from_env()
            publisher = build_queue_publisher_from_env(options)

        self.assertFalse(options.whisper_enabled)
        self.assertFalse(options.analysis_enabled)
        self.assertIsNone(publisher)

    def test_rabbitmq_publisher_declares_durable_queue_and_persistent_json(self) -> None:
        state: dict[str, object] = {}

        def blocking_connection(parameters):
            connection = _FakeConnection(parameters)
            state["connection"] = connection
            return connection

        fake_pika = SimpleNamespace(
            PlainCredentials=lambda username, password: (username, password),
            ConnectionParameters=lambda **kwargs: kwargs,
            BlockingConnection=blocking_connection,
            BasicProperties=lambda **kwargs: kwargs,
        )
        publisher = RabbitMQQueuePublisher(
            RabbitMQConfig(username="stereo", password="password")
        )

        with patch.dict(sys.modules, {"pika": fake_pika}):
            publisher.publish("stereo.whisper", {"channel_id": 0, "speaker": "agent"})

        connection = state["connection"]
        channel = connection.fake_channel
        self.assertEqual(
            channel.declarations,
            [{"queue": "stereo.whisper", "durable": True}],
        )
        message = channel.messages[0]
        self.assertEqual(message["exchange"], "")
        self.assertEqual(message["routing_key"], "stereo.whisper")
        self.assertTrue(message["mandatory"])
        self.assertEqual(message["properties"]["delivery_mode"], 2)
        self.assertEqual(
            json.loads(message["body"].decode("utf-8")),
            {"channel_id": 0, "speaker": "agent"},
        )
        self.assertFalse(connection.is_open)


if __name__ == "__main__":
    unittest.main()

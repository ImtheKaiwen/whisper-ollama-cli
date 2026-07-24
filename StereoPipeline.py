"""Compatibility entry point for the simplest stereo-only import."""

from stereo_pipeline.queueing import (
    InMemoryQueuePublisher,
    QueueOptions,
    RabbitMQConfig,
    RabbitMQQueuePublisher,
    build_queue_publisher_from_env,
)
from stereo_pipeline.stereo_entry import StereoPipeline

__all__ = [
    "InMemoryQueuePublisher",
    "QueueOptions",
    "RabbitMQConfig",
    "RabbitMQQueuePublisher",
    "StereoPipeline",
    "build_queue_publisher_from_env",
]

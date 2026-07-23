"""Compatibility entry point for the simplest stereo-only import."""

from stereo_pipeline.queueing import InMemoryQueuePublisher, QueueOptions
from stereo_pipeline.stereo_entry import StereoPipeline

__all__ = ["InMemoryQueuePublisher", "QueueOptions", "StereoPipeline"]

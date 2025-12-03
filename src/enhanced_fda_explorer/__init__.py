"""
Enhanced FDA Explorer - AI-powered FDA medical device data exploration

This package provides an intelligent agent for exploring FDA medical device data,
combining GUDID device resolution with OpenFDA API queries.
"""

__version__ = "2.0.0"
__author__ = "Dr. Sidd Nambiar"

from .agent import FDAAgent
from .tools import DeviceResolver
from .llm_factory import LLMFactory
from .config import Config, get_config

__all__ = [
    "FDAAgent",
    "DeviceResolver",
    "LLMFactory",
    "Config",
    "get_config",
]

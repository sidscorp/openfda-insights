"""
Enhanced FDA Explorer - Next-generation FDA medical device data exploration platform

This package provides a comprehensive platform for exploring FDA medical device data
with production-ready reliability, AI-powered analysis, and multiple interface options.
"""

__version__ = "1.0.0"
__author__ = "Dr. Sidd Nambiar"
__email__ = "sidd.nambiar@example.com"

from .core import FDAExplorer
from .client import EnhancedFDAClient
from .ai import AIAnalysisEngine
from .config import Config

__all__ = [
    "FDAExplorer",
    "EnhancedFDAClient", 
    "AIAnalysisEngine",
    "Config",
]
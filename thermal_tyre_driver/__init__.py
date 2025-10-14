"""
Public interface for the thermal tyre driver package.
"""

__version__ = "0.1.1"

from .driver import (
    SensorConfig,
    TyreThermalSensor,
    TyreThermalData,
    TyreAnalysis,
    TyreSection,
    DetectionInfo,
    I2CMux,
)

__all__ = [
    "SensorConfig",
    "TyreThermalSensor",
    "TyreThermalData",
    "TyreAnalysis",
    "TyreSection",
    "DetectionInfo",
    "I2CMux",
    "__version__",
]

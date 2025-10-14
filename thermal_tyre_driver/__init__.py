"""
Public interface for the thermal tyre driver package.
"""

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
]

"""
Fast version of thermal_tyre_pico.py
Uses mean instead of median for 5-10x speedup
Less robust but much faster for CircuitPython
"""

# Copy everything from thermal_tyre_pico.py but replace slow functions
import board
import busio
import adafruit_mlx90640
import time
try:
    import ulab.numpy as np
except ImportError:
    import numpy as np
from collections import deque

__version__ = "0.2.0-pico-fast"

# Import all classes from original
import sys
sys.path.insert(0, '/sd' if hasattr(board, 'SD') else '/')

# We'll just patch the slow functions
def calculate_median_fast(data):
    """Fast median approximation using mean"""
    return sum(data) / len(data) if data else 0

def calculate_mad_fast(data):
    """Fast MAD approximation using standard deviation"""
    if not data or len(data) < 2:
        return 0
    mean = sum(data) / len(data)
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    return variance ** 0.5  # Standard deviation as MAD proxy

def median_filter_1d_fast(data, size=3):
    """Fast median filter using simple averaging"""
    result = [0] * len(data)
    half_size = size // 2

    for i in range(len(data)):
        window_start = max(0, i - half_size)
        window_end = min(len(data), i + half_size + 1)
        window = data[window_start:window_end]
        result[i] = sum(window) / len(window)  # Mean instead of median

    return result

# Monkey-patch the slow functions
import thermal_tyre_pico
thermal_tyre_pico.calculate_median = calculate_median_fast
thermal_tyre_pico.calculate_mad = calculate_mad_fast
thermal_tyre_pico.median_filter_1d = median_filter_1d_fast

print("⚡ Fast mode enabled - using mean instead of median")

# Re-export everything
from thermal_tyre_pico import *

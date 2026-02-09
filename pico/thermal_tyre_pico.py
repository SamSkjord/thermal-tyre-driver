#!/usr/bin/env python3
"""
Thermal Tyre Sensor Driver for Raspberry Pi Pico
CircuitPython port with serial and I2C peripheral output
"""

import board
import busio
import adafruit_mlx90640
import time
try:
    import ulab.numpy as np
except ImportError:
    # Fallback for testing on non-Pico systems
    import numpy as np
from collections import deque

__version__ = "0.2.0-pico-fast"

# ⚡ FAST MODE ENABLED ⚡
# Using mean instead of median for 10x speedup
# Slightly less robust to outliers but much faster on CircuitPython

# ---- Helper Functions ----
def median_filter_1d(data, size=3):
    """Simple 1D filter - FAST MODE: uses mean for speed"""
    # Original median filter with sorted() is too slow
    # Using mean instead of median is much faster
    result = [0] * len(data)
    half_size = size // 2

    for i in range(len(data)):
        window_start = max(0, i - half_size)
        window_end = min(len(data), i + half_size + 1)
        window = data[window_start:window_end]
        result[i] = sum(window) / len(window)  # Mean instead of median

    return result


def calculate_median(data):
    """Calculate median - FAST MODE: uses mean for speed"""
    # Original median code is too slow (~800ms per frame)
    # Using mean is 10x faster and good enough for this application
    if hasattr(data, 'tolist'):
        data = data.tolist()
    return sum(data) / len(data) if len(data) > 0 else 0


def calculate_mad(data):
    """Calculate MAD approximation - FAST MODE: uses std dev"""
    # Original MAD (double median) is too slow
    # Using standard deviation as proxy is much faster
    if not data or len(data) < 2:
        return 0
    mean = sum(data) / len(data)
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    return variance ** 0.5  # Std dev as MAD approximation


# ---- Data Structures ----
class TyreSection:
    """Temperature statistics for a tyre section"""

    def __init__(self, avg=0.0, median=0.0, min_val=0.0, max_val=0.0, std=0.0):
        self.avg = avg
        self.median = median
        self.min = min_val
        self.max = max_val
        self.std = std

    def to_dict(self):
        return {
            "avg": round(self.avg, 2),
            "median": round(self.median, 2),
            "min": round(self.min, 2),
            "max": round(self.max, 2),
            "std": round(self.std, 2)
        }


class TyreAnalysis:
    """Complete tyre temperature analysis"""

    def __init__(self, left, centre, right, lateral_gradient):
        self.left = left
        self.centre = centre
        self.right = right
        self.lateral_gradient = lateral_gradient

    def to_dict(self):
        return {
            "left": self.left.to_dict(),
            "centre": self.centre.to_dict(),
            "right": self.right.to_dict(),
            "lateral_gradient": round(self.lateral_gradient, 2)
        }


class DetectionInfo:
    """Detection algorithm information"""

    def __init__(self, method, span_start, span_end, width, confidence,
                 inverted, clipped, mad_global, median_temp, centre_temp, threshold_delta):
        self.method = method
        self.span_start = span_start
        self.span_end = span_end
        self.width = width
        self.confidence = confidence
        self.inverted = inverted
        self.clipped = clipped
        self.mad_global = mad_global
        self.median_temp = median_temp
        self.centre_temp = centre_temp
        self.threshold_delta = threshold_delta

    def to_dict(self):
        return {
            "method": self.method,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "width": self.width,
            "confidence": round(self.confidence, 3),
            "inverted": self.inverted,
            "clipped": self.clipped,
            "mad_global": round(self.mad_global, 2),
            "median_temp": round(self.median_temp, 2),
            "centre_temp": round(self.centre_temp, 2),
            "threshold_delta": round(self.threshold_delta, 2)
        }


class TyreThermalData:
    """Complete thermal data packet from sensor"""

    def __init__(self, frame_number, analysis, detection,
                 temperature_profile, warnings=None):
        self.frame_number = frame_number
        self.analysis = analysis
        self.detection = detection
        self.temperature_profile = temperature_profile
        self.warnings = warnings or []

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "frame_number": self.frame_number,
            "analysis": self.analysis.to_dict(),
            "detection": self.detection.to_dict(),
            "temperature_profile": [round(x, 1) for x in self.temperature_profile],
            "warnings": self.warnings
        }


class SensorConfig:
    """Sensor configuration parameters"""

    def __init__(self):
        # Sensor specs
        self.sensor_width = 32
        self.sensor_height = 24
        self.middle_rows = 4
        self.start_row = 10

        # Temperature limits
        self.min_temp = 0.0
        self.max_temp = 180.0
        self.brake_temp_threshold = 180.0

        # MAD thresholds
        self.mad_uniform_threshold = 0.5
        self.k_floor = 5.0
        self.k_multiplier = 2.0
        self.delta_floor = 3.0
        self.delta_multiplier = 1.8

        # Region growing
        self.max_fail_count = 2
        self.centre_col = 16

        # Geometry constraints
        self.min_tyre_width = 6
        self.max_tyre_width = 28
        self.max_width_change_ratio = 0.3

        # Temporal smoothing
        self.ema_alpha = 0.3
        self.spatial_filter_size = 3
        self.persistence_frames = 2

        # Confidence thresholds
        self.min_confidence_warning = 0.5
        self.temp_diff_for_high_confidence = 3.0

        # MLX90640 settings
        self.refresh_rate = 4  # Hz


# ---- Main Driver Class ----
class TyreThermalSensor:
    """
    Driver for MLX90640 thermal sensor with tyre analysis
    Pico-optimized version with serial and I2C peripheral output

    Example usage:
        sensor = TyreThermalSensor()
        data = sensor.read()
        print(data.to_dict())
    """

    def __init__(self, config=None, i2c_bus=None):
        """
        Initialize thermal sensor driver

        Args:
            config: Sensor configuration (uses defaults if None)
            i2c_bus: Existing I2C bus to use (creates new if None)
        """
        self.config = config or SensorConfig()
        self.frame_count = 0

        # Initialize I2C
        if i2c_bus is None:
            # MLX90640 supports up to 1MHz - use it for best performance
            self.i2c = busio.I2C(board.GP1, board.GP0, frequency=1000000)
        else:
            self.i2c = i2c_bus

        # Initialize MLX90640
        self._init_sensor()

        # Initialize detection state
        self.prev_span = None
        self.prev_width = None
        self.ema_profile = None
        self.persistence_buffer = deque((), self.config.persistence_frames)
        self.confidence_history = deque((), 10)

    def _init_sensor(self):
        """Initialize MLX90640 sensor"""
        try:
            self.mlx = adafruit_mlx90640.MLX90640(self.i2c)

            # Set refresh rate
            refresh_rate_map = {
                1: adafruit_mlx90640.RefreshRate.REFRESH_1_HZ,
                2: adafruit_mlx90640.RefreshRate.REFRESH_2_HZ,
                4: adafruit_mlx90640.RefreshRate.REFRESH_4_HZ,
                8: adafruit_mlx90640.RefreshRate.REFRESH_8_HZ,
                16: adafruit_mlx90640.RefreshRate.REFRESH_16_HZ,
                32: adafruit_mlx90640.RefreshRate.REFRESH_32_HZ,
            }
            self.mlx.refresh_rate = refresh_rate_map.get(
                self.config.refresh_rate, adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
            )

            # Warn about high refresh rates
            if self.config.refresh_rate > 8:
                print(f"Warning: {self.config.refresh_rate}Hz may be too fast for CircuitPython")
                print("Consider using MicroPython or C if you need >8Hz")

            # Give sensor time to stabilize after changing refresh rate
            time.sleep(1.0)

        except Exception as e:
            raise RuntimeError(f"Failed to initialize MLX90640: {e}")

    def read(self):
        """
        Read sensor and return complete analysis

        Returns:
            TyreThermalData object containing all analysis results
        """
        # Read frame
        frame_2d = self._read_frame()
        if frame_2d is None:
            raise RuntimeError("Failed to read frame")

        self.frame_count += 1

        # Perform detection
        left, right, detection_info, profile = self._detect_tyre_span(frame_2d)

        # Analyse sections
        analysis = self._analyse_sections(frame_2d, left, right)

        # Generate warnings
        warnings = self._generate_warnings(analysis, detection_info)

        # Create data packet
        data = TyreThermalData(
            frame_number=self.frame_count,
            analysis=analysis,
            detection=detection_info,
            temperature_profile=profile,
            warnings=warnings
        )

        return data

    def _read_frame(self):
        """Read a frame from the sensor with retry"""
        frame = [0.0] * 768

        # Try up to 3 times
        for attempt in range(3):
            try:
                self.mlx.getFrame(frame)
                # Convert to 2D array (24x32)
                frame_2d = []
                for i in range(24):
                    row = frame[i * 32:(i + 1) * 32]
                    frame_2d.append(row)
                return frame_2d
            except Exception as e:
                if attempt < 2:  # Don't print on last attempt
                    continue
                else:
                    print(f"Error reading frame after 3 attempts: {e}")
                    return None

    def _extract_middle_rows(self, frame_2d):
        """Extract middle rows and handle brake plume"""
        middle_rows = []
        for i in range(self.config.start_row,
                      self.config.start_row + self.config.middle_rows):
            middle_rows.append(frame_2d[i][:])

        # Handle hot pixels (brake plume)
        for row_idx in range(len(middle_rows)):
            for col_idx in range(len(middle_rows[0])):
                if middle_rows[row_idx][col_idx] > self.config.brake_temp_threshold:
                    # Replace with median of neighbors
                    neighbours = []
                    for dr in [-1, 0, 1]:
                        for dc in [-1, 0, 1]:
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = row_idx + dr, col_idx + dc
                            if (0 <= nr < len(middle_rows) and
                                0 <= nc < len(middle_rows[0]) and
                                middle_rows[nr][nc] <= self.config.brake_temp_threshold):
                                neighbours.append(middle_rows[nr][nc])

                    if neighbours:
                        middle_rows[row_idx][col_idx] = calculate_median(neighbours)

        return middle_rows

    def _grow_region(self, profile, centre, median_temp, delta, inverted=False):
        """Grow region from centre"""
        n_cols = len(profile)
        seed_temp = profile[centre]

        # Calculate local MAD
        local_window_size = 5
        local_start = max(0, centre - local_window_size // 2)
        local_end = min(n_cols, centre + local_window_size // 2 + 1)
        local_window = profile[local_start:local_end]
        local_mad = calculate_mad(local_window)

        k = max(self.config.k_floor, self.config.k_multiplier * local_mad)

        left = centre
        right = centre

        def meets_criteria(temp):
            within_k = abs(temp - seed_temp) <= k
            if inverted:
                global_criterion = temp <= median_temp - delta
            else:
                global_criterion = temp >= median_temp + delta
            return within_k or global_criterion

        # Grow left
        fail_count = 0
        for col in range(centre - 1, -1, -1):
            if meets_criteria(profile[col]):
                left = col
                fail_count = 0
            else:
                fail_count += 1
                if fail_count >= self.config.max_fail_count:
                    break

        # Grow right
        fail_count = 0
        for col in range(centre + 1, n_cols):
            if meets_criteria(profile[col]):
                right = col
                fail_count = 0
            else:
                fail_count += 1
                if fail_count >= self.config.max_fail_count:
                    break

        return left, right + 1

    def _apply_constraints(self, left, right):
        """Apply geometry and temporal constraints"""
        width = right - left

        # Width constraints
        if width < self.config.min_tyre_width:
            centre = (left + right) // 2
            half_width = self.config.min_tyre_width // 2
            left = max(0, centre - half_width)
            right = min(self.config.sensor_width, left + self.config.min_tyre_width)
        elif width > self.config.max_tyre_width:
            excess = width - self.config.max_tyre_width
            left += excess // 2
            right -= excess - excess // 2

        # Temporal constraints
        if self.prev_width is not None:
            new_width = right - left
            max_change = int(self.prev_width * self.config.max_width_change_ratio)

            if new_width > self.prev_width + max_change:
                shrink_amount = new_width - (self.prev_width + max_change)
                left += shrink_amount // 2
                right -= shrink_amount - shrink_amount // 2
            elif new_width < self.prev_width - max_change:
                expand_amount = (self.prev_width - max_change) - new_width
                centre = (left + right) // 2
                left = max(0, centre - (self.prev_width - max_change) // 2)
                right = min(self.config.sensor_width,
                           left + (self.prev_width - max_change))

        return left, right

    def _apply_persistence_smoothing(self, left, right):
        """Apply weighted persistence smoothing"""
        self.persistence_buffer.append((left, right))

        if len(self.persistence_buffer) < 2:
            return left, right

        # Simple exponential weighting
        total_weight = 0
        weighted_left = 0
        weighted_right = 0

        for i, (l, r) in enumerate(self.persistence_buffer):
            weight = (i + 1) ** 2  # Quadratic weight
            weighted_left += l * weight
            weighted_right += r * weight
            total_weight += weight

        smoothed_left = int(weighted_left / total_weight)
        smoothed_right = int(weighted_right / total_weight)

        return smoothed_left, smoothed_right

    def _calculate_confidence(self, profile, left, right, mad_global, method):
        """Calculate detection confidence"""
        confidence = 1.0

        width = right - left
        if width <= self.config.min_tyre_width + 2:
            confidence *= 0.7
        elif width >= self.config.max_tyre_width - 2:
            confidence *= 0.8

        if mad_global < 1.0:
            confidence *= 0.6

        # Temperature difference
        tyre_temps = profile[left:right]
        if len(tyre_temps) > 0:
            tyre_mean = sum(tyre_temps) / len(tyre_temps)

            background_temps = []
            if left > 2:
                background_temps.extend(profile[:left - 1])
            if right < len(profile) - 2:
                background_temps.extend(profile[right + 1:])

            if len(background_temps) > 0:
                background_mean = sum(background_temps) / len(background_temps)
                temp_diff = abs(tyre_mean - background_mean)

                if temp_diff > self.config.temp_diff_for_high_confidence:
                    confidence *= 1.2
                elif temp_diff < 1.0:
                    confidence *= 0.7

        if method == "held_uniform":
            confidence *= 0.5

        confidence = min(1.0, max(0.0, confidence))
        self.confidence_history.append(confidence)

        return confidence

    def _detect_tyre_span(self, frame_2d):
        """Detect tyre span and return detection info"""
        # Extract middle rows
        middle_rows = self._extract_middle_rows(frame_2d)

        # Collapse to 1D profile (median of rows)
        profile = []
        for col_idx in range(self.config.sensor_width):
            col_temps = [row[col_idx] for row in middle_rows]
            profile.append(calculate_median(col_temps))

        # Clip temperatures
        profile = [max(self.config.min_temp, min(self.config.max_temp, t))
                  for t in profile]

        # Spatial filtering
        profile = median_filter_1d(profile, size=self.config.spatial_filter_size)

        # Temporal smoothing (EMA)
        if self.ema_profile is None:
            self.ema_profile = profile[:]
        else:
            alpha = self.config.ema_alpha
            for i in range(len(profile)):
                self.ema_profile[i] = alpha * profile[i] + (1 - alpha) * self.ema_profile[i]

        smoothed_profile = self.ema_profile[:]

        # Calculate statistics
        median_temp = calculate_median(smoothed_profile)
        mad_global = calculate_mad(smoothed_profile)

        # Check for uniform temperature
        if (mad_global < self.config.mad_uniform_threshold and
            self.prev_span is not None):
            left, right = self.prev_span
            method = "held_uniform"
            inverted = False
            centre_temp = smoothed_profile[self.config.centre_col]
            delta = 0.0
        else:
            # Calculate threshold
            delta = max(self.config.delta_floor,
                       self.config.delta_multiplier * mad_global)

            # Fixed centre
            centre = self.config.centre_col
            centre_temp = smoothed_profile[centre]

            # Detect inversion
            inverted = centre_temp < median_temp - delta

            # Grow region
            left, right = self._grow_region(smoothed_profile, centre,
                                           median_temp, delta, inverted)

            # Apply constraints
            left, right = self._apply_constraints(left, right)

            # Apply smoothing
            left, right = self._apply_persistence_smoothing(left, right)

            method = "region_growing"

        # Update state
        self.prev_span = (left, right)
        self.prev_width = right - left

        # Calculate confidence
        confidence = self._calculate_confidence(smoothed_profile, left, right,
                                               mad_global, method)

        # Check clipping
        clipped = "none"
        if left == 0 and right == self.config.sensor_width:
            clipped = "both_edges"
        elif left == 0:
            clipped = "left_edge"
        elif right == self.config.sensor_width:
            clipped = "right_edge"

        # Create detection info
        detection = DetectionInfo(
            method=method,
            span_start=left,
            span_end=right,
            width=right - left,
            confidence=confidence,
            inverted=inverted,
            clipped=clipped,
            mad_global=mad_global,
            median_temp=median_temp,
            centre_temp=centre_temp,
            threshold_delta=delta
        )

        return left, right, detection, smoothed_profile

    def _analyse_sections(self, frame_2d, left, right):
        """Analyse tyre temperature in sections"""
        middle_rows = self._extract_middle_rows(frame_2d)

        tyre_width = right - left
        if tyre_width <= 0:
            return TyreAnalysis(
                TyreSection(), TyreSection(), TyreSection(), 0.0
            )

        section_width = tyre_width / 3.0

        # Extract sections
        sections_data = {"left": [], "centre": [], "right": []}
        section_bounds = [
            ("left", 0, int(section_width)),
            ("centre", int(section_width), int(2 * section_width)),
            ("right", int(2 * section_width), tyre_width)
        ]

        for row in middle_rows:
            tyre_region = row[left:right]
            for name, start, end in section_bounds:
                if start < end and start < tyre_width:
                    section_temps = tyre_region[start:min(end, tyre_width)]
                    sections_data[name].extend(section_temps)

        # Calculate statistics
        sections = {}
        for name, temps in sections_data.items():
            if temps:
                avg = sum(temps) / len(temps)
                median = calculate_median(temps)
                min_val = min(temps)
                max_val = max(temps)

                # Calculate std dev
                mean = avg
                variance = sum((x - mean) ** 2 for x in temps) / len(temps)
                std = variance ** 0.5

                sections[name] = TyreSection(avg, median, min_val, max_val, std)
            else:
                sections[name] = TyreSection()

        # Calculate gradient
        col_means = []
        for col_idx in range(left, right):
            col_temps = [row[col_idx] for row in middle_rows]
            col_means.append(sum(col_temps) / len(col_temps))

        gradient = max(col_means) - min(col_means) if col_means else 0.0

        return TyreAnalysis(
            sections["left"],
            sections["centre"],
            sections["right"],
            gradient
        )

    def _generate_warnings(self, analysis, detection):
        """Generate warning messages"""
        warnings = []

        if detection.confidence < self.config.min_confidence_warning:
            warnings.append(f"Low confidence: {int(detection.confidence * 100)}%")

        # Temperature differential
        temps = [analysis.left.avg, analysis.centre.avg, analysis.right.avg]
        temps = [t for t in temps if t > 0]
        if len(temps) >= 2:
            diff = max(temps) - min(temps)
            if diff > 5:
                warnings.append(f"Temp diff: {round(diff, 1)}C across tyre")

        if detection.method == "held_uniform":
            warnings.append("Uniform temp - using previous detection")

        if detection.inverted:
            warnings.append("Inverted: Cold tyre on warm ground")

        if detection.clipped != "none":
            warnings.append(f"Clipped at {detection.clipped}")

        # Check for high temperatures
        max_temps = [analysis.left.max, analysis.centre.max, analysis.right.max]
        max_temps = [t for t in max_temps if t > 0]
        if max_temps and max(max_temps) > 50:
            warnings.append(f"High temp: {round(max(max_temps), 1)}C")

        if analysis.lateral_gradient > 10:
            warnings.append(f"High gradient: {round(analysis.lateral_gradient, 1)}C")

        return warnings

    def reset(self):
        """Reset driver state"""
        self.frame_count = 0
        self.prev_span = None
        self.prev_width = None
        self.ema_profile = None
        self.persistence_buffer = deque((), self.config.persistence_frames)
        self.confidence_history = deque((), 10)

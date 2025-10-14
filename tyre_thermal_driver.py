#!/usr/bin/env python3
"""
Thermal Tyre Sensor Driver
Provides a clean API for thermal tyre analysis with I2C multiplexer support
"""

import time
import board
import busio
import adafruit_mlx90640
import numpy as np
from scipy import ndimage
from collections import deque
from typing import Tuple, Dict, List, Optional, NamedTuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json


# ---- Data Structures ----
@dataclass
class TyreSection:
    """Temperature statistics for a tyre section"""
    avg: float = 0.0
    median: float = 0.0
    min: float = 0.0
    max: float = 0.0
    std: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TyreAnalysis:
    """Complete tyre temperature analysis"""
    left: TyreSection
    centre: TyreSection
    right: TyreSection
    lateral_gradient: float
    
    def to_dict(self) -> Dict:
        return {
            'left': self.left.to_dict(),
            'centre': self.centre.to_dict(),
            'right': self.right.to_dict(),
            'lateral_gradient': self.lateral_gradient
        }


@dataclass
class DetectionInfo:
    """Detection algorithm information"""
    method: str
    span_start: int
    span_end: int
    width: int
    confidence: float
    inverted: bool
    clipped: str
    mad_global: float
    median_temp: float
    centre_temp: float
    threshold_delta: float
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TyreThermalData:
    """Complete thermal data packet from sensor"""
    timestamp: datetime
    sensor_id: str
    frame_number: int
    
    # Core temperature data
    analysis: TyreAnalysis
    detection: DetectionInfo
    
    # Raw data
    temperature_profile: np.ndarray
    raw_frame: Optional[np.ndarray] = None
    
    # Warnings
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'sensor_id': self.sensor_id,
            'frame_number': self.frame_number,
            'analysis': self.analysis.to_dict(),
            'detection': self.detection.to_dict(),
            'temperature_profile': self.temperature_profile.tolist(),
            'raw_frame': self.raw_frame.tolist() if self.raw_frame is not None else None,
            'warnings': self.warnings
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class SensorConfig:
    """Sensor configuration parameters"""
    # Sensor specs
    sensor_width: int = 32
    sensor_height: int = 24
    middle_rows: int = 4
    start_row: int = 10
    
    # Temperature limits
    min_temp: float = 0.0
    max_temp: float = 180.0
    brake_temp_threshold: float = 180.0
    
    # MAD thresholds
    mad_uniform_threshold: float = 0.5
    k_floor: float = 5.0
    k_multiplier: float = 2.0
    delta_floor: float = 3.0
    delta_multiplier: float = 1.8
    
    # Region growing
    max_fail_count: int = 2
    centre_col: int = 16
    
    # Geometry constraints
    min_tyre_width: int = 6
    max_tyre_width: int = 28
    max_width_change_ratio: float = 0.3
    
    # Temporal smoothing
    ema_alpha: float = 0.3
    spatial_filter_size: int = 3
    persistence_frames: int = 2
    
    # Confidence thresholds
    min_confidence_warning: float = 0.5
    temp_diff_for_high_confidence: float = 3.0
    
    # MLX90640 settings
    refresh_rate: int = 4  # Hz
    
    # Include raw frame in output
    include_raw_frame: bool = False


# ---- I2C Multiplexer Support ----
class I2CMux:
    """TCA9548A I2C Multiplexer control"""
    
    def __init__(self, i2c_bus: busio.I2C, address: int = 0x70):
        """
        Initialize I2C multiplexer
        
        Args:
            i2c_bus: I2C bus instance
            address: Multiplexer I2C address (default 0x70)
        """
        self.i2c = i2c_bus
        self.address = address
        self.current_channel = None
    
    def select_channel(self, channel: int):
        """
        Select multiplexer channel (0-7)
        
        Args:
            channel: Channel number to select
        """
        if not 0 <= channel <= 7:
            raise ValueError(f"Channel must be 0-7, got {channel}")
        
        if self.current_channel != channel:
            # Write channel select byte
            while not self.i2c.try_lock():
                pass
            try:
                self.i2c.writeto(self.address, bytes([1 << channel]))
                self.current_channel = channel
            finally:
                self.i2c.unlock()
    
    def disable_all(self):
        """Disable all multiplexer channels"""
        while not self.i2c.try_lock():
            pass
        try:
            self.i2c.writeto(self.address, bytes([0]))
            self.current_channel = None
        finally:
            self.i2c.unlock()


# ---- Main Driver Class ----
class TyreThermalSensor:
    """
    Driver for MLX90640 thermal sensor with tyre analysis
    
    Example usage:
        # Single sensor
        sensor = TyreThermalSensor(sensor_id="FRONT_LEFT")
        data = sensor.read()
        print(data.to_json())
        
        # With I2C mux
        sensor = TyreThermalSensor(
            sensor_id="FRONT_LEFT",
            mux_address=0x70,
            mux_channel=0
        )
        data = sensor.read()
    """
    
    def __init__(self, 
                 sensor_id: str,
                 config: Optional[SensorConfig] = None,
                 mux_address: Optional[int] = None,
                 mux_channel: Optional[int] = None,
                 i2c_bus: Optional[busio.I2C] = None):
        """
        Initialize thermal sensor driver
        
        Args:
            sensor_id: Identifier for this sensor (e.g., "FRONT_LEFT")
            config: Sensor configuration (uses defaults if None)
            mux_address: I2C mux address if using multiplexer
            mux_channel: Mux channel for this sensor
            i2c_bus: Existing I2C bus to use (creates new if None)
        """
        self.sensor_id = sensor_id
        self.config = config or SensorConfig()
        self.frame_count = 0
        
        # Initialize I2C
        if i2c_bus is None:
            self.i2c = busio.I2C(board.SCL, board.SDA)
        else:
            self.i2c = i2c_bus
        
        # Setup multiplexer if needed
        self.mux = None
        self.mux_channel = mux_channel
        if mux_address is not None:
            self.mux = I2CMux(self.i2c, mux_address)
            if mux_channel is not None:
                self.mux.select_channel(mux_channel)
        
        # Initialize MLX90640
        self._init_sensor()
        
        # Initialize detection state
        self.prev_span = None
        self.prev_width = None
        self.ema_profile = None
        self.persistence_buffer = deque(maxlen=self.config.persistence_frames)
        self.confidence_history = deque(maxlen=10)
        self._mad_cache = {}
    
    def _init_sensor(self):
        """Initialize MLX90640 sensor"""
        try:
            # Select mux channel if needed
            if self.mux and self.mux_channel is not None:
                self.mux.select_channel(self.mux_channel)
            
            self.mlx = adafruit_mlx90640.MLX90640(self.i2c)
            
            # Set refresh rate
            refresh_rate_map = {
                1: adafruit_mlx90640.RefreshRate.REFRESH_1_HZ,
                2: adafruit_mlx90640.RefreshRate.REFRESH_2_HZ,
                4: adafruit_mlx90640.RefreshRate.REFRESH_4_HZ,
                8: adafruit_mlx90640.RefreshRate.REFRESH_8_HZ,
                16: adafruit_mlx90640.RefreshRate.REFRESH_16_HZ,
                32: adafruit_mlx90640.RefreshRate.REFRESH_32_HZ
            }
            self.mlx.refresh_rate = refresh_rate_map.get(
                self.config.refresh_rate,
                adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
            )
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize MLX90640 for {self.sensor_id}: {e}")
    
    def read(self) -> TyreThermalData:
        """
        Read sensor and return complete analysis
        
        Returns:
            TyreThermalData object containing all analysis results
        """
        # Select mux channel if needed
        if self.mux and self.mux_channel is not None:
            self.mux.select_channel(self.mux_channel)
        
        # Read frame
        frame_2d = self._read_frame()
        if frame_2d is None:
            raise RuntimeError(f"Failed to read frame from {self.sensor_id}")
        
        self.frame_count += 1
        
        # Perform detection
        left, right, detection_info, profile = self._detect_tyre_span(frame_2d)
        
        # Analyse sections
        analysis = self._analyse_sections(frame_2d, left, right)
        
        # Generate warnings
        warnings = self._generate_warnings(analysis, detection_info)
        
        # Create data packet
        data = TyreThermalData(
            timestamp=datetime.now(),
            sensor_id=self.sensor_id,
            frame_number=self.frame_count,
            analysis=analysis,
            detection=detection_info,
            temperature_profile=profile,
            raw_frame=frame_2d if self.config.include_raw_frame else None,
            warnings=warnings
        )
        
        return data
    
    def _read_frame(self) -> Optional[np.ndarray]:
        """Read a frame from the sensor"""
        frame = [0.0] * 768
        try:
            self.mlx.getFrame(frame)
            return np.array(frame).reshape(24, 32)
        except Exception as e:
            print(f"Error reading frame from {self.sensor_id}: {e}")
            return None
    
    def _extract_middle_rows(self, frame_2d: np.ndarray) -> np.ndarray:
        """Extract middle rows and handle brake plume"""
        middle_rows = frame_2d[
            self.config.start_row:self.config.start_row + self.config.middle_rows, :
        ].copy()
        
        # Handle hot pixels
        hot_mask = middle_rows > self.config.brake_temp_threshold
        
        if np.any(hot_mask):
            for row_idx, col_idx in np.argwhere(hot_mask):
                neighbours = []
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = row_idx + dr, col_idx + dc
                        if (0 <= nr < middle_rows.shape[0] and 
                            0 <= nc < middle_rows.shape[1] and
                            not hot_mask[nr, nc]):
                            neighbours.append(middle_rows[nr, nc])
                
                if neighbours:
                    middle_rows[row_idx, col_idx] = np.median(neighbours)
        
        return middle_rows
    
    def _calculate_mad(self, data: np.ndarray) -> float:
        """Calculate Median Absolute Deviation with caching"""
        cache_key = hash(data.tobytes())
        
        if cache_key in self._mad_cache:
            return self._mad_cache[cache_key]
        
        median = np.median(data)
        mad = np.median(np.abs(data - median))
        
        if len(self._mad_cache) > 100:
            self._mad_cache.clear()
        
        self._mad_cache[cache_key] = mad
        return mad
    
    def _grow_region(self, profile: np.ndarray, centre: int, 
                    median_temp: float, delta: float, inverted: bool = False) -> Tuple[int, int]:
        """Grow region from centre"""
        n_cols = len(profile)
        seed_temp = profile[centre]
        
        # Calculate local MAD
        local_window_size = 5
        local_start = max(0, centre - local_window_size // 2)
        local_end = min(n_cols, centre + local_window_size // 2 + 1)
        local_window = profile[local_start:local_end]
        local_mad = self._calculate_mad(local_window)
        
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
    
    def _apply_constraints(self, left: int, right: int) -> Tuple[int, int]:
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
                right = min(self.config.sensor_width, left + (self.prev_width - max_change))
        
        return left, right
    
    def _apply_persistence_smoothing(self, left: int, right: int) -> Tuple[int, int]:
        """Apply weighted persistence smoothing"""
        self.persistence_buffer.append((left, right))
        
        if len(self.persistence_buffer) < 2:
            return left, right
        
        weights = np.exp(np.linspace(0, 1, len(self.persistence_buffer)))
        weights /= weights.sum()
        
        smoothed_left = np.average([s[0] for s in self.persistence_buffer], weights=weights)
        smoothed_right = np.average([s[1] for s in self.persistence_buffer], weights=weights)
        
        return int(smoothed_left), int(smoothed_right)
    
    def _calculate_confidence(self, profile: np.ndarray, left: int, right: int,
                             mad_global: float, method: str) -> float:
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
            tyre_mean = np.mean(tyre_temps)
            
            background_temps = []
            if left > 2:
                background_temps.extend(profile[:left-1])
            if right < len(profile) - 2:
                background_temps.extend(profile[right+1:])
            
            if len(background_temps) > 0:
                background_mean = np.mean(background_temps)
                temp_diff = abs(tyre_mean - background_mean)
                
                if temp_diff > self.config.temp_diff_for_high_confidence:
                    confidence *= 1.2
                elif temp_diff < 1.0:
                    confidence *= 0.7
        
        if method == 'held_uniform':
            confidence *= 0.5
        
        confidence = min(1.0, max(0.0, confidence))
        self.confidence_history.append(confidence)
        
        return confidence
    
    def _detect_tyre_span(self, frame_2d: np.ndarray) -> Tuple[int, int, DetectionInfo, np.ndarray]:
        """Detect tyre span and return detection info"""
        # Extract middle rows
        middle_rows = self._extract_middle_rows(frame_2d)
        
        # Collapse to 1D profile
        profile = np.median(middle_rows, axis=0)
        profile = np.clip(profile, self.config.min_temp, self.config.max_temp)
        profile = ndimage.median_filter(profile, size=self.config.spatial_filter_size)
        
        # Temporal smoothing
        if self.ema_profile is None:
            self.ema_profile = profile
        else:
            alpha = self.config.ema_alpha
            self.ema_profile = alpha * profile + (1 - alpha) * self.ema_profile
        
        smoothed_profile = self.ema_profile
        
        # Calculate statistics
        median_temp = np.median(smoothed_profile)
        mad_global = self._calculate_mad(smoothed_profile)
        
        # Check for uniform temperature
        if mad_global < self.config.mad_uniform_threshold and self.prev_span is not None:
            left, right = self.prev_span
            method = 'held_uniform'
            inverted = False
            centre_temp = smoothed_profile[self.config.centre_col]
            delta = 0.0
        else:
            # Calculate threshold
            delta = max(self.config.delta_floor, self.config.delta_multiplier * mad_global)
            
            # Fixed centre
            centre = self.config.centre_col
            centre_temp = smoothed_profile[centre]
            
            # Detect inversion
            inverted = centre_temp < median_temp - delta
            
            # Grow region
            left, right = self._grow_region(smoothed_profile, centre, median_temp, delta, inverted)
            
            # Apply constraints
            left, right = self._apply_constraints(left, right)
            
            # Apply smoothing
            left, right = self._apply_persistence_smoothing(left, right)
            
            method = 'region_growing'
        
        # Update state
        self.prev_span = (left, right)
        self.prev_width = right - left
        
        # Calculate confidence
        confidence = self._calculate_confidence(smoothed_profile, left, right, mad_global, method)
        
        # Check clipping
        clipped = 'none'
        if left == 0 and right == self.config.sensor_width:
            clipped = 'both_edges'
        elif left == 0:
            clipped = 'left_edge'
        elif right == self.config.sensor_width:
            clipped = 'right_edge'
        
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
    
    def _analyse_sections(self, frame_2d: np.ndarray, left: int, right: int) -> TyreAnalysis:
        """Analyse tyre temperature in sections"""
        middle_rows = self._extract_middle_rows(frame_2d)
        
        tyre_width = right - left
        if tyre_width <= 0 or middle_rows.size == 0:
            return TyreAnalysis(
                left=TyreSection(),
                centre=TyreSection(),
                right=TyreSection(),
                lateral_gradient=0.0
            )
        
        section_width = tyre_width / 3
        tyre_region = middle_rows[:, left:right]
        
        sections = {}
        section_bounds = [
            ('left', 0, int(section_width)),
            ('centre', int(section_width), int(2 * section_width)),
            ('right', int(2 * section_width), tyre_width)
        ]
        
        for name, start, end in section_bounds:
            if start < end and start < tyre_width:
                section_data = tyre_region[:, start:min(end, tyre_width)]
                sections[name] = TyreSection(
                    avg=float(np.mean(section_data)),
                    median=float(np.median(section_data)),
                    min=float(np.min(section_data)),
                    max=float(np.max(section_data)),
                    std=float(np.std(section_data))
                )
            else:
                sections[name] = TyreSection()
        
        # Calculate gradient
        col_means = np.mean(tyre_region, axis=0)
        gradient = float(np.max(col_means) - np.min(col_means)) if len(col_means) > 0 else 0.0
        
        return TyreAnalysis(
            left=sections.get('left', TyreSection()),
            centre=sections.get('centre', TyreSection()),
            right=sections.get('right', TyreSection()),
            lateral_gradient=gradient
        )
    
    def _generate_warnings(self, analysis: TyreAnalysis, detection: DetectionInfo) -> List[str]:
        """Generate warning messages"""
        warnings = []
        
        if detection.confidence < self.config.min_confidence_warning:
            warnings.append(f"Low detection confidence: {detection.confidence:.0%}")
        
        # Temperature differential
        temps = [analysis.left.avg, analysis.centre.avg, analysis.right.avg]
        temps = [t for t in temps if t > 0]
        if len(temps) >= 2:
            diff = max(temps) - min(temps)
            if diff > 5:
                warnings.append(f"Temperature differential: {diff:.1f}°C across tyre")
        
        if detection.method == 'held_uniform':
            warnings.append("Uniform temperature - using previous detection")
        
        if detection.inverted:
            warnings.append("Inverted mode: Cold tyre on warm ground")
        
        if detection.clipped != 'none':
            warnings.append(f"Tyre clipped at {detection.clipped}")
        
        # Check for high temperatures
        max_temps = [analysis.left.max, analysis.centre.max, analysis.right.max]
        max_temps = [t for t in max_temps if t > 0]
        if max_temps and max(max_temps) > 50:
            warnings.append(f"High temperature: {max(max_temps):.1f}°C")
        
        if analysis.lateral_gradient > 10:
            warnings.append(f"High lateral gradient: {analysis.lateral_gradient:.1f}°C")
        
        return warnings
    
    def get_stats(self) -> Dict:
        """Get driver statistics"""
        return {
            'sensor_id': self.sensor_id,
            'frame_count': self.frame_count,
            'average_confidence': float(np.mean(list(self.confidence_history))) if self.confidence_history else 0.0,
            'current_span': self.prev_span,
            'current_width': self.prev_width
        }
    
    def reset(self):
        """Reset driver state"""
        self.frame_count = 0
        self.prev_span = None
        self.prev_width = None
        self.ema_profile = None
        self.persistence_buffer.clear()
        self.confidence_history.clear()
        self._mad_cache.clear()


# ---- Example Usage ----
if __name__ == "__main__":
    """Example usage of the driver"""
    
    # Example 1: Single sensor
    print("Example 1: Single sensor")
    sensor = TyreThermalSensor(sensor_id="FRONT_LEFT")
    
    for i in range(5):
        try:
            data = sensor.read()
            print(f"\nFrame {data.frame_number}:")
            print(f"  Timestamp: {data.timestamp}")
            print(f"  Detection: {data.detection.span_start}-{data.detection.span_end}")
            print(f"  Confidence: {data.detection.confidence:.0%}")
            print(f"  Left: {data.analysis.left.avg:.1f}°C")
            print(f"  Centre: {data.analysis.centre.avg:.1f}°C")
            print(f"  Right: {data.analysis.right.avg:.1f}°C")
            if data.warnings:
                print(f"  Warnings: {', '.join(data.warnings)}")
            time.sleep(0.5)
        except Exception as e:
            print(f"Error: {e}")
            break
    
    print("\n" + "="*70)
    
    # Example 2: Multiple sensors with I2C mux
    print("Example 2: Multiple sensors with I2C mux")
    
    # Shared I2C bus
    i2c_bus = busio.I2C(board.SCL, board.SDA)
    
    # Create sensors for all four tyres
    sensors = {
        "FRONT_LEFT": TyreThermalSensor(
            sensor_id="FRONT_LEFT",
            mux_address=0x70,
            mux_channel=0,
            i2c_bus=i2c_bus
        ),
        "FRONT_RIGHT": TyreThermalSensor(
            sensor_id="FRONT_RIGHT",
            mux_address=0x70,
            mux_channel=1,
            i2c_bus=i2c_bus
        ),
        "REAR_LEFT": TyreThermalSensor(
            sensor_id="REAR_LEFT",
            mux_address=0x70,
            mux_channel=2,
            i2c_bus=i2c_bus
        ),
        "REAR_RIGHT": TyreThermalSensor(
            sensor_id="REAR_RIGHT",
            mux_address=0x70,
            mux_channel=3,
            i2c_bus=i2c_bus
        )
    }
    
    # Read from all sensors
    for position, sensor in sensors.items():
        try:
            data = sensor.read()
            print(f"\n{position}:")
            print(f"  Temps: L={data.analysis.left.avg:.1f}°C "
                  f"C={data.analysis.centre.avg:.1f}°C "
                  f"R={data.analysis.right.avg:.1f}°C")
            print(f"  Confidence: {data.detection.confidence:.0%}")
        except Exception as e:
            print(f"  Error: {e}")
    
    print("\n" + "="*70)
    
    # Example 3: JSON output
    print("Example 3: JSON output")
    sensor = TyreThermalSensor(sensor_id="TEST", config=SensorConfig(include_raw_frame=False))
    data = sensor.read()
    print(data.to_json()[:500] + "...")  # Print first 500 chars
# Thermal Tyre Sensor Driver

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-red)](https://www.raspberrypi.org/)
[![AI Slop](https://img.shields.io/badge/Claude%20-Opus%204.1-beige)](https://www.morningstar.com/news/marketwatch/20251003175/the-ai-bubble-is-17-times-the-size-of-the-dot-com-frenzy-and-four-times-subprime-this-analyst-argues)

A robust Python driver for thermal tyre temperature monitoring using MLX90640 thermal cameras. Features MAD-based detection algorithms, I2C multiplexer support, and real-time analysis of tyre temperature distribution.

## 🌟 Features

- **Robust Detection**: MAD-based centre-out region growing algorithm
- **Multi-Sensor Support**: Built-in I2C multiplexer (TCA9548A) support for up to 8 sensors
- **Real-time Analysis**: Three-section tyre temperature analysis (left/centre/right)
- **Confidence Scoring**: Detection confidence metrics for reliability assessment
- **Edge Case Handling**: Automatic handling of brake heat, cold tyres, and sensor clipping
- **Structured Output**: JSON-serializable data structures for easy integration
- **Configurable Parameters**: Extensive configuration options for different use cases
- **Production Ready**: Comprehensive error handling and temporal smoothing

## 📋 Requirements

### Hardware
- Raspberry Pi (or compatible SBC with I2C)
- MLX90640 thermal camera sensor(s)
- (Optional) TCA9548A I2C multiplexer for multiple sensors
- I2C pull-up resistors (typically 4.7kΩ)

### Software
```bash
# Python 3.7+
python3 --version

# Required packages
pip install numpy
pip install scipy
pip install adafruit-circuitpython-mlx90640
pip install adafruit-blinka
```

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/samskjord/thermal-tyre-driver.git
cd thermal-tyre-sensor

# Install dependencies
pip install -r requirements.txt

# Enable I2C on Raspberry Pi
sudo raspi-config
# Navigate to: Interfacing Options -> I2C -> Enable
```

### Basic Usage

```python
from tyre_thermal_driver import TyreThermalSensor

# Create sensor instance
sensor = TyreThermalSensor(sensor_id="FRONT_LEFT")

# Read temperature data
data = sensor.read()

# Access temperature analysis
print(f"Left: {data.analysis.left.avg:.1f}°C")
print(f"Centre: {data.analysis.centre.avg:.1f}°C")
print(f"Right: {data.analysis.right.avg:.1f}°C")
print(f"Confidence: {data.detection.confidence:.0%}")
```

## 📖 API Documentation

### TyreThermalSensor Class

#### Constructor

```python
TyreThermalSensor(
    sensor_id: str,
    config: Optional[SensorConfig] = None,
    mux_address: Optional[int] = None,
    mux_channel: Optional[int] = None,
    i2c_bus: Optional[busio.I2C] = None
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `sensor_id` | str | Unique identifier for the sensor (e.g., "FRONT_LEFT") |
| `config` | SensorConfig | Configuration object (uses defaults if None) |
| `mux_address` | int | I2C address of multiplexer (e.g., 0x70) |
| `mux_channel` | int | Multiplexer channel (0-7) |
| `i2c_bus` | busio.I2C | Shared I2C bus instance |

#### Methods

##### `read() -> TyreThermalData`
Reads sensor and returns complete analysis.

```python
data = sensor.read()
```

##### `get_stats() -> Dict`
Returns driver statistics.

```python
stats = sensor.get_stats()
print(f"Frames processed: {stats['frame_count']}")
print(f"Average confidence: {stats['average_confidence']:.1%}")
```

##### `reset()`
Resets driver state.

```python
sensor.reset()
```

### Data Structures

#### TyreThermalData

The main data structure returned by `read()`:

```python
@dataclass
class TyreThermalData:
    timestamp: datetime          # Reading timestamp
    sensor_id: str               # Sensor identifier
    frame_number: int            # Sequential frame count
    analysis: TyreAnalysis       # Temperature analysis
    detection: DetectionInfo     # Detection algorithm info
    temperature_profile: np.ndarray  # 1D temperature array
    raw_frame: Optional[np.ndarray]  # Full 24x32 frame
    warnings: List[str]          # Warning messages
```

#### TyreAnalysis

Temperature analysis for tyre sections:

```python
@dataclass
class TyreAnalysis:
    left: TyreSection            # Left third of tyre
    centre: TyreSection          # Centre third
    right: TyreSection           # Right third
    lateral_gradient: float      # Temperature gradient across tyre
```

#### TyreSection

Statistics for each section:

```python
@dataclass
class TyreSection:
    avg: float      # Average temperature
    median: float   # Median temperature
    min: float      # Minimum temperature
    max: float      # Maximum temperature
    std: float      # Standard deviation
```

## ⚙️ Configuration

### SensorConfig Parameters

```python
from tyre_thermal_driver import SensorConfig

config = SensorConfig(
    # Sensor specifications
    sensor_width=32,              # Pixels
    sensor_height=24,             # Pixels
    middle_rows=4,                # Rows to analyze
    
    # Temperature limits
    min_temp=0.0,                 # °C
    max_temp=180.0,               # °C
    brake_temp_threshold=180.0,   # °C
    
    # MAD thresholds
    mad_uniform_threshold=0.5,
    k_floor=5.0,
    k_multiplier=2.0,
    delta_floor=3.0,
    delta_multiplier=1.8,
    
    # Detection parameters
    min_tyre_width=6,             # Pixels
    max_tyre_width=28,            # Pixels
    max_width_change_ratio=0.3,   # ±30% per frame
    
    # Smoothing
    ema_alpha=0.3,                # EMA weight
    persistence_frames=2,          # Frames for stability
    
    # Output options
    include_raw_frame=False       # Include full frame data
)

sensor = TyreThermalSensor("CUSTOM", config=config)
```

## 🔧 Advanced Usage

### Multiple Sensors with I2C Multiplexer

```python
import busio
import board
from tyre_thermal_driver import TyreThermalSensor

# Share I2C bus for efficiency
i2c_bus = busio.I2C(board.SCL, board.SDA)

# Create sensors for all four tyres
sensors = {
    "FL": TyreThermalSensor("FL", mux_address=0x70, mux_channel=0, i2c_bus=i2c_bus),
    "FR": TyreThermalSensor("FR", mux_address=0x70, mux_channel=1, i2c_bus=i2c_bus),
    "RL": TyreThermalSensor("RL", mux_address=0x70, mux_channel=2, i2c_bus=i2c_bus),
    "RR": TyreThermalSensor("RR", mux_address=0x70, mux_channel=3, i2c_bus=i2c_bus)
}

# Read all tyres
for position, sensor in sensors.items():
    data = sensor.read()
    print(f"{position}: L={data.analysis.left.avg:.1f}°C "
          f"C={data.analysis.centre.avg:.1f}°C "
          f"R={data.analysis.right.avg:.1f}°C "
          f"[{data.detection.confidence:.0%}]")
```

### Data Logging Example

```python
import json
import time
from datetime import datetime

def log_tyre_data(sensor, log_file="tyre_temps.jsonl"):
    """Log tyre temperature data to JSON Lines file"""
    
    while True:
        try:
            data = sensor.read()
            
            # Create log entry
            log_entry = {
                "timestamp": data.timestamp.isoformat(),
                "sensor": data.sensor_id,
                "temps": {
                    "left": data.analysis.left.avg,
                    "centre": data.analysis.centre.avg,
                    "right": data.analysis.right.avg
                },
                "confidence": data.detection.confidence,
                "warnings": data.warnings
            }
            
            # Append to file
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            time.sleep(1.0)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1.0)
```

### Real-time Monitoring

```python
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

def create_live_plot(sensor):
    """Create live temperature plot"""
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    # Temperature history
    history_len = 100
    temps = {'left': [], 'centre': [], 'right': []}
    confidence = []
    
    def update(frame):
        data = sensor.read()
        
        # Update history
        for section in ['left', 'centre', 'right']:
            temp = getattr(data.analysis, section).avg
            temps[section].append(temp)
            if len(temps[section]) > history_len:
                temps[section].pop(0)
        
        confidence.append(data.detection.confidence)
        if len(confidence) > history_len:
            confidence.pop(0)
        
        # Plot temperatures
        ax1.clear()
        x = range(len(temps['left']))
        ax1.plot(x, temps['left'], 'b-', label='Left')
        ax1.plot(x, temps['centre'], 'g-', label='Centre')
        ax1.plot(x, temps['right'], 'r-', label='Right')
        ax1.set_ylabel('Temperature (°C)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot confidence
        ax2.clear()
        ax2.plot(range(len(confidence)), confidence, 'k-')
        ax2.set_ylabel('Confidence')
        ax2.set_xlabel('Time (frames)')
        ax2.set_ylim([0, 1])
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
    
    ani = FuncAnimation(fig, update, interval=250)
    plt.show()
```

## 🔍 Detection Algorithm

The driver uses a MAD-based (Median Absolute Deviation) centre-out region growing algorithm:

1. **Profile Extraction**: Collapses middle sensor rows to 1D temperature profile
2. **Temporal Smoothing**: Applies EMA filter to reduce noise
3. **MAD Calculation**: Computes global and local temperature variation
4. **Region Growing**: Grows from centre pixel using dual thresholds:
   - Local threshold (k): Temperature similarity to seed point
   - Global threshold (Δ): Temperature above/below median
5. **Constraint Application**: Enforces geometry and temporal constraints
6. **Confidence Scoring**: Evaluates detection quality

### Algorithm Parameters

- `k = max(5.0, 2.0 × local_MAD)` - Local temperature threshold
- `Δ = max(3.0, 1.8 × global_MAD)` - Global temperature threshold
- Two consecutive failures stop region growth
- Width constrained to 6-28 pixels
- ±30% width change limit per frame

## 📊 Output Examples

### JSON Output

```json
{
  "timestamp": "2024-01-15T14:32:15.123456",
  "sensor_id": "FRONT_LEFT",
  "frame_number": 42,
  "analysis": {
    "left": {
      "avg": 45.2,
      "median": 45.1,
      "min": 44.8,
      "max": 45.7,
      "std": 0.3
    },
    "centre": {
      "avg": 48.5,
      "median": 48.6,
      "min": 47.9,
      "max": 49.2,
      "std": 0.4
    },
    "right": {
      "avg": 44.8,
      "median": 44.7,
      "min": 44.3,
      "max": 45.3,
      "std": 0.3
    },
    "lateral_gradient": 4.3
  },
  "detection": {
    "method": "region_growing",
    "span_start": 8,
    "span_end": 24,
    "width": 16,
    "confidence": 0.85,
    "inverted": false,
    "clipped": "none"
  },
  "warnings": [
    "Temperature differential: 3.7°C across tyre"
  ]
}
```

## 🐛 Troubleshooting

### Common Issues

#### I2C Device Not Found
```bash
# Check I2C devices
sudo i2cdetect -y 1

# Expected output for MLX90640: address 0x33
# Expected output for TCA9548A: address 0x70
```

#### Permission Denied
```bash
# Add user to i2c group
sudo usermod -a -G i2c $USER

# Logout and login again
```

#### Slow Frame Rate
- Check I2C speed: `sudo cat /boot/config.txt | grep i2c`
- Add `dtparam=i2c_baudrate=400000` for 400kHz

#### Low Confidence Readings
- Ensure sensor is properly aimed at tyre
- Check for obstructions or reflections
- Adjust mounting distance (10-30cm typical)
- Calibrate configuration parameters

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

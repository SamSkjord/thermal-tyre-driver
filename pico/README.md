# Thermal Tyre Driver - Raspberry Pi Pico Port

CircuitPython port of the thermal tyre driver optimized for Raspberry Pi Pico with dual communication channels.

## Features

- **Pico-optimized**: Runs on CircuitPython with minimal dependencies
- **Dual output**: Serial (USB CDC) + I2C peripheral mode simultaneously
- **Memory efficient**: Simplified algorithms for microcontroller constraints
- **No multiplexer needed**: Single sensor per Pico
- **Register-based I2C**: Easy integration with other microcontrollers

## Hardware Requirements

### Components
- Raspberry Pi Pico (or Pico W)
- MLX90640 thermal camera sensor
- I2C pull-up resistors (4.7kΩ typical)

### Wiring

#### MLX90640 Sensor (I2C0)
```
MLX90640        Pico
--------        ----
VDD      →      3V3 (Pin 36)
GND      →      GND (Pin 38)
SDA      →      GP0 (Pin 1)
SCL      →      GP1 (Pin 2)
```

#### I2C Peripheral Output (I2C1)
Connect to your controller/main system:
```
Pico            Controller
----            ----------
GP4 (Pin 6)  →  SDA (with pull-up)
GP5 (Pin 7)  →  SCL (with pull-up)
GND          →  GND
```

#### Serial Output
- USB connection provides serial communication automatically
- Access via `/dev/ttyACM0` (Linux) or COM port (Windows)

## Software Setup

### Quick Install

See **[INSTALLATION.md](INSTALLATION.md)** for complete step-by-step guide, or use **[INSTALL_CHECKLIST.md](INSTALL_CHECKLIST.md)** to verify your setup.

### Summary

1. **Install CircuitPython** on Pico (one-time)
2. **Copy libraries** to `CIRCUITPY/lib/`
3. **Copy driver files** to `CIRCUITPY/` root:
   - `boot.py` - USB serial setup
   - `code.py` - Main application (auto-runs!)
   - `thermal_tyre_pico.py` - Sensor driver
   - `communication.py` - Serial output
4. **Connect sensor** to GP0/GP1
5. **Power on** - code runs automatically!

### Files You Need

Required on CIRCUITPY drive:
```
CIRCUITPY/
├── boot.py                    # USB serial config
├── code.py                    # Auto-runs on boot
├── thermal_tyre_pico.py       # Driver
├── communication.py           # Serial/I2C
└── lib/
    ├── adafruit_mlx90640.mpy
    └── adafruit_bus_device/
```

**Important**: File must be named `code.py` (not `main.py`) to auto-run on boot!

### Auto-Run vs Manual Examples

- **`code.py`** - Production version, auto-runs on boot (use this for deployment)
- **`main.py`** - Example with I2C peripheral (for testing both outputs)
- **`example_serial_only.py`** - Minimal example (for learning)
- **`test_i2c.py`** - Diagnostic tool (for troubleshooting)

For production use, copy `code.py` to your Pico. It will start automatically every time you power on.

## Usage Examples

### 1. Serial Output Only (Simplest)

```python
from thermal_tyre_pico import TyreThermalSensor
from communication import SerialCommunicator
import time

sensor = TyreThermalSensor()
serial = SerialCommunicator()

while True:
    data = sensor.read()
    serial.send_data(data)  # Send JSON
    time.sleep(0.25)
```

### 2. I2C Peripheral Output

```python
import board
from thermal_tyre_pico import TyreThermalSensor
from communication import I2CPeripheralExtended

sensor = TyreThermalSensor()
i2c_peripheral = I2CPeripheralExtended(
    scl_pin=board.GP5,
    sda_pin=board.GP4,
    address=0x42
)

while True:
    data = sensor.read()
    i2c_peripheral.update_data(data)
    i2c_peripheral.service()  # Handle I2C requests
    time.sleep(0.01)
```

### 3. Dual Output (Serial + I2C)

See `main.py` for complete example with both outputs.

## Communication Protocols

### Serial (USB CDC)

Two formats available:

**Full JSON** (default):
```json
{
  "frame_number": 42,
  "analysis": {
    "left": {"avg": 45.2, "median": 45.1, ...},
    "centre": {"avg": 48.5, ...},
    "right": {"avg": 44.8, ...}
  },
  "detection": {...},
  "warnings": [...]
}
```

**Compact CSV**:
```
42,45.2,48.5,44.8,0.85,0
```
*Format: frame_number,L_avg,C_avg,R_avg,confidence,warnings_count*

### I2C Peripheral Mode

The Pico acts as an I2C slave device with register-based access:

#### Register Map

| Register | Size | Description |
|----------|------|-------------|
| 0x00 | 2 bytes | Left temperature (int16, tenths of °C) |
| 0x02 | 2 bytes | Centre temperature (int16, tenths of °C) |
| 0x04 | 2 bytes | Right temperature (int16, tenths of °C) |
| 0x06 | 1 byte | Confidence (uint8, 0-100%) |
| 0x07 | 1 byte | Warnings count |
| 0x08 | 1 byte | Span start pixel |
| 0x09 | 1 byte | Span end pixel |
| 0x0A | 1 byte | Tyre width (pixels) |
| 0x0B | 2 bytes | Lateral gradient (int16, tenths of °C) |
| 0x0D | 2 bytes | Frame counter (uint16) |

#### Reading from Controller (Serial)

Python example:
```python
import serial
import json

ser = serial.Serial('/dev/ttyACM1', 115200)

while True:
    line = ser.readline()
    data = json.loads(line)

    print(f"Frame {data['frame_number']}: "
          f"L={data['analysis']['left']['avg']:.1f}C")
```

### Reading from Controller (I2C)

Python example (using smbus2):
```python
import smbus2

bus = smbus2.SMBus(1)
PICO_ADDR = 0x42

# Read temperatures
left_raw = bus.read_word_data(PICO_ADDR, 0x00)
left_temp = left_raw / 10.0  # Convert to °C

centre_raw = bus.read_word_data(PICO_ADDR, 0x02)
centre_temp = centre_raw / 10.0

right_raw = bus.read_word_data(PICO_ADDR, 0x04)
right_temp = right_raw / 10.0

confidence = bus.read_byte_data(PICO_ADDR, 0x06) / 100.0

print(f"L:{left_temp}C C:{centre_temp}C R:{right_temp}C [{confidence:.0%}]")
```

See `example_i2c_controller.py` for full example.

## Real-Time Visualization (Mac/Host)

A visualization tool is included to monitor thermal data in real-time on your Mac/PC.

### Setup

```bash
# Install dependencies
pip install -r requirements_visualizer.txt
```

### Usage

```bash
# Auto-detect Pico serial port
python visualizer.py

# Specify port manually
python visualizer.py -p /dev/tty.usbmodem14201

# List available ports
python visualizer.py --list
```

### Features

The visualizer displays:
- **Current temperatures**: Live bar chart (Left/Centre/Right)
- **Temperature history**: Scrolling line graph showing trends
- **Detection confidence**: Visual confidence meter
- **Temperature profile**: 32-pixel sensor view with tyre span highlighted
- **Lateral gradient**: Temperature difference across tyre
- **Warnings**: Real-time alert messages
- **Statistics**: Frame count, drop rate, etc.

### Screenshot

```
┌─────────────────────────────────────────────────────────────┐
│  Current Temps  │        Temperature History                │
│   L  ┃  C  ┃  R │                                           │
│  45° ┃ 52° ┃ 43°│    [Line graph showing L/C/R over time]   │
├─────────────────┴───────────────────────────────────────────┤
│ Confidence ███░░│    Temperature Profile (32 pixels)        │
│    85%         │    [Profile with tyre span highlighted]    │
├────────────────┬────────────────────────────────────────────┤
│ Lateral Gradient │           Status & Warnings              │
│ [History graph]  │  Frame: 142                              │
│                  │  ⚠️ High gradient: 12.3°C                 │
└──────────────────┴──────────────────────────────────────────┘
```

### Tips

- Leave visualizer running during testing to monitor in real-time
- Color-coded temperatures: Blue (cool), Orange (warm), Red (hot)
- Confidence indicator: Green (>80%), Orange (50-80%), Red (<50%)
- Close window or Ctrl+C to exit

## Performance Notes

### CircuitPython Performance - Final Results

**Achieved: 1.5 fps (stable)**

After extensive optimization and testing:

| Component | Time | Optimization |
|-----------|------|--------------|
| Frame read (MLX90640) | 670ms | I2C @ 1MHz (was 750ms @ 400kHz) |
| Algorithm processing | 20ms | Mean-based (was 800ms with median) |
| Serial output | 2ms | Compact CSV |
| **Total** | **692ms** | **1.5 fps** |

**Bottleneck identified:** Adafruit MLX90640 library's `getFrame()` blocks for 670ms regardless of sensor refresh rate (tested 4Hz, 8Hz, 16Hz - all identical). This is a library limitation, not hardware.

**For tyre monitoring:** 1.5fps is perfectly adequate! Tyre temperatures change over seconds/minutes, not milliseconds.

See **[PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md)** for detailed analysis.

### If You Need More Performance

**For 16Hz+, you need faster execution:**

1. **MicroPython** (2-3x faster):
   - Can handle 16Hz with `@micropython.native` decorators
   - Same code, just faster execution

2. **C/C++ Port** (10x+ faster):
   - Can easily handle 32Hz
   - Rewrite median/MAD calculations in C
   - Use native MLX90640 library

Most demanding operations (optimize these first):
- `calculate_median()` - O(n log n) sorting
- `calculate_mad()` - Double median calculation
- `_grow_region()` - Iterative pixel walking
- `_extract_middle_rows()` - Neighbor interpolation

## Configuration

Adjust `SensorConfig` parameters in code:

```python
from thermal_tyre_pico import SensorConfig

config = SensorConfig()
config.refresh_rate = 4  # Hz - Recommended: 4 (safe), 8 (max for CircuitPython)
config.ema_alpha = 0.3   # Temporal smoothing
config.min_tyre_width = 6  # Pixels
config.max_tyre_width = 28  # Pixels

sensor = TyreThermalSensor(config=config)
```

**Refresh rate recommendations:**
- **4Hz**: Best for CircuitPython, stable, low CPU usage
- **8Hz**: Maximum for CircuitPython, use if you need faster updates
- **16Hz+**: Requires MicroPython or C port

**For racing/motorsport**: 4-8Hz is usually sufficient for tyre temperature monitoring. Tyre temps change slowly (seconds/minutes), so 4Hz provides good real-time feedback.

## Differences from Raspberry Pi Version

| Feature | Pi Version | Pico Version |
|---------|-----------|--------------|
| Dependencies | numpy, scipy | ulab (numpy-like) |
| Multiplexer | Supported | Not included |
| datetime | Full datetime | time.monotonic() |
| JSON | json module | ujson (faster) |
| Communication | N/A | Serial + I2C peripheral |
| Raw frames | Optional | Not included (memory) |
| Memory usage | ~2-10MB | ~40-60KB |

## Troubleshooting

### I2C ETIMEDOUT Errors

If you see `[Errno 116] ETIMEDOUT`:

1. **Run diagnostic test first:**
   ```bash
   # Copy test_i2c.py to your Pico and run it
   # It will check connectivity and scan for devices
   ```

2. **Check wiring:**
   ```
   MLX90640 VDD → Pico 3V3 (Pin 36)
   MLX90640 GND → Pico GND (Pin 38)
   MLX90640 SDA → Pico GP0 (Pin 1)
   MLX90640 SCL → Pico GP1 (Pin 2)
   ```

3. **Add pull-up resistors:**
   - 4.7kΩ from SDA to 3V3
   - 4.7kΩ from SCL to 3V3
   - Many MLX90640 breakouts have these built-in

4. **Check I2C address:**
   ```python
   import board
   import busio

   i2c = busio.I2C(board.GP1, board.GP0)
   while not i2c.try_lock():
       pass
   devices = i2c.scan()
   print([hex(d) for d in devices])  # Should see 0x33
   i2c.unlock()
   ```

5. **Try lower I2C speed:**
   ```python
   i2c = busio.I2C(board.GP1, board.GP0, frequency=100000)
   ```

### I2C Sensor Not Found
If 0x33 not found in scan:
- Verify 3.3V power (NOT 5V!)
- Check all connections
- Try different I2C pins
- Test sensor on Arduino/Pi first

### Memory Errors
- Reduce `persistence_frames` in config
- Don't enable raw frame output
- Use compact serial format

### Low Confidence
- Check sensor alignment with tyre
- Verify mounting distance (10-30cm)
- Adjust MAD thresholds in config

### I2C Peripheral Not Working
- Ensure pull-up resistors on SCL/SDA
- Check CircuitPython version (7.0+)
- Verify controller I2C clock speed (<400kHz)

## Pin Customization

Default pins can be changed:

```python
import board
import busio

# Use different I2C pins for sensor
i2c_sensor = busio.I2C(scl=board.GP3, sda=board.GP2)
sensor = TyreThermalSensor(i2c_bus=i2c_sensor)

# Use different pins for I2C peripheral
i2c_peripheral = I2CPeripheralExtended(
    scl_pin=board.GP7,
    sda_pin=board.GP6,
    address=0x42
)
```

## License

MIT License - same as main thermal-tyre-driver package

## Performance Optimization Tips

If you need higher performance:

1. **Reduce refresh rate**: 2Hz instead of 4Hz
2. **Simplify median calculations**: Use sorted samples with stride
3. **Reduce history**: Smaller `persistence_frames`
4. **Pre-allocate buffers**: Reuse arrays instead of creating new ones
5. **Profile**: Use `time.monotonic()` to measure hot spots

## Multi-Sensor Setup

For multiple tyres, use one Pico per sensor with I2C multiplexer:

```
                        ┌─ Mux Ch0 ─ Pico (FL sensor)
                        ├─ Mux Ch1 ─ Pico (FR sensor)
Main Controller ─ I2C ──┤─ Mux Ch2 ─ Pico (RL sensor)
                        └─ Mux Ch3 ─ Pico (RR sensor)
```

All Picos use the same I2C peripheral address (e.g., 0x42). Host selects which sensor by switching the multiplexer channel.

## Contributing

If you port to C or add optimizations, please share!

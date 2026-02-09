# Migration Guide: Raspberry Pi → Pico

Guide for adapting existing code to the Pico port.

## Import Changes

### Before (Raspberry Pi)
```python
from thermal_tyre_driver import (
    SensorConfig,
    TyreThermalSensor,
    TyreThermalData
)
```

### After (Pico)
```python
from thermal_tyre_pico import (
    SensorConfig,
    TyreThermalSensor,
    TyreThermalData
)
from communication import SerialCommunicator, I2CPeripheralExtended
```

## Initialization Changes

### Before (Raspberry Pi - Single Sensor)
```python
config = SensorConfig(include_raw_frame=False, refresh_rate=4)
sensor = TyreThermalSensor(sensor_id="FRONT_LEFT", config=config)
```

### After (Pico - Single Sensor)
```python
config = SensorConfig()
config.refresh_rate = 4
sensor = TyreThermalSensor(config=config)
```

### Before (Raspberry Pi - With Multiplexer)
```python
import busio
import board

i2c_bus = busio.I2C(board.SCL, board.SDA)
config = SensorConfig(include_raw_frame=False)

sensors = {
    "FL": TyreThermalSensor("FL", config=config,
                           mux_address=0x70, mux_channel=0,
                           i2c_bus=i2c_bus),
    "FR": TyreThermalSensor("FR", config=config,
                           mux_address=0x70, mux_channel=1,
                           i2c_bus=i2c_bus),
}
```

### After (Pico - Multiple Sensors)
Use separate Pico boards, one per sensor, all with same I2C address:

**Each Pico runs identical code:**
```python
sensor = TyreThermalSensor()
i2c_peripheral = I2CPeripheralExtended(..., address=0x42)
# All Picos use same address
# Host controller switches I2C mux channel to select which Pico
```

## Configuration Changes

### Before (Raspberry Pi)
```python
config = SensorConfig(
    include_raw_frame=False,
    refresh_rate=4,
    min_tyre_width=6,
    max_tyre_width=28,
    ema_alpha=0.3
)
```

### After (Pico)
```python
config = SensorConfig()
config.refresh_rate = 4
config.min_tyre_width = 6
config.max_tyre_width = 28
config.ema_alpha = 0.3
# Note: include_raw_frame removed (memory constraints)
```

## Data Access Changes

### Before (Raspberry Pi)
```python
data = sensor.read()

# Access data
print(f"Timestamp: {data.timestamp.isoformat()}")
print(f"Left: {data.analysis.left.avg:.1f}°C")

# Convert to JSON
json_str = data.to_json()

# Access raw frame
if data.raw_frame is not None:
    print(f"Frame shape: {data.raw_frame.shape}")
```

### After (Pico)
```python
data = sensor.read()

# Access data
print(f"Frame: {data.frame_number}")
print(f"Left: {data.analysis.left.avg:.1f}°C")

# Convert to dict (then serialize manually)
data_dict = data.to_dict()
import json
json_str = json.dumps(data_dict)

# Raw frame not available (memory)
```

## Output/Communication Changes

### Before (Raspberry Pi)
Typically, you'd process data locally or log to file:

```python
data = sensor.read()

# Log to file
with open('tyre_data.jsonl', 'a') as f:
    f.write(data.to_json() + '\n')

# Or process immediately
analyze_temperatures(data)
```

### After (Pico)
Output via serial or I2C peripheral:

```python
# Serial output
serial = SerialCommunicator()
data = sensor.read()
serial.send_data(data)  # Sends JSON

# OR

# I2C peripheral output
i2c_peripheral = I2CPeripheralExtended(...)
data = sensor.read()
i2c_peripheral.update_data(data)
i2c_peripheral.service()
```

## Reading Data from Pico

### Serial (Python on host)
```python
import serial
import json

ser = serial.Serial('/dev/ttyACM1', 115200)

while True:
    line = ser.readline()
    data = json.loads(line)
    print(f"Left: {data['analysis']['left']['avg']}°C")
```

### I2C (Python on Raspberry Pi)
```python
from smbus2 import SMBus

bus = SMBus(1)
PICO_ADDR = 0x42

# Read left temperature (register 0x00, 2 bytes)
left_raw = bus.read_word_data(PICO_ADDR, 0x00)
left_temp = left_raw / 10.0

print(f"Left: {left_temp}°C")
```

## Algorithm Differences

Most detection algorithms are identical, but with these changes:

### Numerical Operations

**Before (NumPy):**
```python
import numpy as np

median = np.median(data)
mad = np.median(np.abs(data - median))
profile = np.median(middle_rows, axis=0)
```

**After (Manual/ulab):**
```python
# Median implemented manually or via ulab
median = calculate_median(data)
deviations = [abs(x - median) for x in data]
mad = calculate_median(deviations)

# Median across columns
profile = []
for col in range(32):
    col_data = [row[col] for row in middle_rows]
    profile.append(calculate_median(col_data))
```

### Filtering

**Before (scipy):**
```python
from scipy import ndimage
profile = ndimage.median_filter(profile, size=3)
```

**After (Manual):**
```python
profile = median_filter_1d(profile, size=3)
```

## Performance Expectations

| Operation | Raspberry Pi | Pico (CircuitPython) | Pico (C) |
|-----------|--------------|----------------------|----------|
| Frame read | 1-2ms | 5-10ms | 1-2ms |
| Detection | 5-10ms | 50-100ms | 5-15ms |
| Total cycle @ 4Hz | 250ms (plenty) | 250ms (tight) | 250ms (plenty) |

## Memory Usage

| Item | Raspberry Pi | Pico |
|------|--------------|------|
| Available RAM | 512MB-8GB | 264KB |
| Driver usage | 2-10MB | 40-60KB |
| Per frame | ~10KB | ~3KB |
| History/cache | Unlimited | Limited |

## Feature Parity Table

| Feature | Pi Version | Pico Version |
|---------|-----------|--------------|
| Core detection | ✅ | ✅ |
| MAD algorithm | ✅ | ✅ |
| Region growing | ✅ | ✅ |
| Temperature analysis | ✅ | ✅ |
| Confidence scoring | ✅ | ✅ |
| Warnings | ✅ | ✅ |
| I2C multiplexer | ✅ | ❌ |
| Raw frame output | ✅ | ❌ |
| Timestamps | ✅ | ❌ |
| Sensor ID | ✅ | ❌ |
| Statistics/caching | ✅ | ⚠️ (limited) |
| Serial output | ➖ | ✅ |
| I2C peripheral | ➖ | ✅ |

✅ = Full support
⚠️ = Partial/modified
❌ = Not supported
➖ = Not applicable

## Common Gotchas

### 1. Lists vs NumPy Arrays
```python
# This won't work on Pico:
profile = np.array(frame).reshape(24, 32)

# Do this instead:
profile = []
for i in range(24):
    profile.append(frame[i*32:(i+1)*32])
```

### 2. No Timestamps or Sensor IDs
```python
# Pico version doesn't include timestamps (no RTC) or sensor_id
# Data packet is minimal - just measurements and frame counter

data = sensor.read()
print(data.frame_number)  # Just frame counter
```

### 3. JSON serialization
```python
# NumPy arrays aren't JSON serializable on Pico
# Convert to lists first:
data_dict = {
    "temps": [float(x) for x in temperature_array]
}
```

### 4. Memory allocation
```python
# Don't create large temporary arrays
# Reuse buffers where possible

# Bad:
for i in range(1000):
    temp_array = [0] * 768  # Creates new array each iteration

# Good:
temp_array = [0] * 768
for i in range(1000):
    # Reuse temp_array
    fill_array(temp_array)
```

## Testing Migration

1. **Test on Pi first** - Verify algorithm works
2. **Port to Pico** - Copy code, adapt imports
3. **Test sensor read** - Verify I2C communication
4. **Test detection** - Compare results with Pi version
5. **Test communication** - Verify serial/I2C output
6. **Profile performance** - Measure timing
7. **Optimize if needed** - Address bottlenecks

## Need Help?

- Check `README.md` for setup instructions
- See `example_*.py` files for working examples
- Review `thermal_tyre_pico.py` for implementation details
- Compare with original `driver.py` for algorithm reference

# Pico Installation Guide

Complete guide to install the thermal tyre sensor on your Raspberry Pi Pico.

## CircuitPython Boot Sequence

When a Pico boots with CircuitPython:
1. **`boot.py`** runs first (USB setup, configuration)
2. **`code.py`** runs second (your main application) ← **This auto-runs!**

## Installation Steps

### 1. Install CircuitPython (One-Time)

If you haven't already:

1. Download CircuitPython for Pico: https://circuitpython.org/board/raspberry_pi_pico/
2. Hold **BOOTSEL** button while plugging in Pico via USB
3. Pico appears as **RPI-RP2** drive
4. Copy the `.uf2` file to the drive
5. Pico reboots and appears as **CIRCUITPY** drive

### 2. Install Required Libraries

Download CircuitPython libraries bundle: https://circuitpython.org/libraries

From the bundle, copy these to `CIRCUITPY/lib/`:
```
CIRCUITPY/
├── lib/
│   ├── adafruit_mlx90640.mpy
│   └── adafruit_bus_device/
│       ├── __init__.mpy
│       ├── i2c_device.mpy
│       └── spi_device.mpy
```

**Quick check**: After copying, you should see:
```
CIRCUITPY/lib/adafruit_mlx90640.mpy
CIRCUITPY/lib/adafruit_bus_device/__init__.mpy
```

### 3. Copy Driver Files

Copy these files to the **root** of the CIRCUITPY drive:

```
CIRCUITPY/
├── boot.py                    # USB serial setup
├── code.py                    # Main application (AUTO-RUNS!)
├── thermal_tyre_pico.py       # Sensor driver
└── communication.py           # Serial/I2C communication
```

**Copy these files:**
- `boot.py` → `CIRCUITPY/boot.py`
- `code.py` → `CIRCUITPY/code.py`
- `thermal_tyre_pico.py` → `CIRCUITPY/thermal_tyre_pico.py`
- `communication.py` → `CIRCUITPY/communication.py`

### 4. Verify Installation

After copying files, your CIRCUITPY drive should look like:

```
CIRCUITPY/
├── boot.py
├── code.py
├── thermal_tyre_pico.py
├── communication.py
└── lib/
    ├── adafruit_mlx90640.mpy
    └── adafruit_bus_device/
```

### 5. Connect Sensor

Wire the MLX90640 to your Pico:

```
MLX90640        Pico
--------        ----
VDD      →      3V3 (Pin 36)
GND      →      GND (Pin 38)
SDA      →      GP0 (Pin 1)
SCL      →      GP1 (Pin 2)
```

**Important**: Add 4.7kΩ pull-up resistors on SDA and SCL (or use a breakout board with built-in pull-ups).

### 6. Power Cycle

1. Unplug the Pico from USB
2. Plug it back in
3. **code.py runs automatically!**

You should see output in the serial console.

## Viewing Serial Output

### macOS/Linux
```bash
# Find the port
ls /dev/tty.usb*

# Connect (console port)
screen /dev/tty.usbmodem14201 115200

# Exit screen: Ctrl+A, then K, then Y
```

### Alternative: Use Mu Editor
1. Download Mu: https://codewith.mu/
2. Open Mu, select "CircuitPython" mode
3. Click "Serial" button to see console output

## Auto-Run Configuration

### code.py (Main Application)
- **Runs automatically on boot**
- Starts sensor and begins outputting data
- Edit `code.py` to change settings:
  ```python
  REFRESH_RATE = 4  # Change to 8 for faster updates
  COMPACT_SERIAL = False  # Change to True for CSV format
  ```

### boot.py (Boot Configuration)
- **Runs before code.py**
- Sets up USB serial channels
- Usually don't need to modify

## Customization

### Change Refresh Rate

Edit `code.py`:
```python
REFRESH_RATE = 8  # 4, 8 (max for CircuitPython)
```

### Change Output Format

Edit `code.py`:
```python
COMPACT_SERIAL = True  # CSV format instead of JSON
```

### Add I2C Peripheral

If you want I2C peripheral output (for reading from another device), edit `code.py` to include the I2C communication setup from `main.py`.

## Testing

### Quick Test
1. Power on Pico with sensor connected
2. Point sensor at your hand
3. Watch serial output - should see temperature rise

### With Visualizer
```bash
# On your Mac
cd thermal-tyre-driver/pico
python3 visualizer.py
```

Should automatically connect and show live data!

## Troubleshooting

### "No module named 'adafruit_mlx90640'"
- Library not installed
- Copy `adafruit_mlx90640.mpy` to `CIRCUITPY/lib/`

### "I2C timeout" errors
- Check wiring
- Verify pull-up resistors present
- Run diagnostic: Copy `test_i2c.py` to CIRCUITPY and rename to `code.py`

### code.py not running
- Check file is named exactly `code.py` (not `code.py.txt`)
- Look for errors in serial console
- Try safe mode: Hold BOOTSEL during boot, errors will show on CIRCUITPY drive

### Serial port not found
- macOS: `/dev/tty.usbmodem*`
- Linux: `/dev/ttyACM*`
- Windows: `COM*`

### Code runs but no serial output
- Check `boot.py` exists and has `usb_cdc.enable()`
- Try the data port instead of console port (different tty number)

## File Management Tips

### Editing Files Directly on Pico
1. Open files on CIRCUITPY drive with any text editor
2. Save changes
3. Pico auto-reloads code.py when you save!

### Entering REPL (Interactive Mode)
1. Connect to serial console
2. Press **Ctrl+C** to stop code.py
3. You're now in REPL (Python prompt)
4. Press **Ctrl+D** to restart code.py

### Stopping Auto-Run Temporarily
Method 1: Rename `code.py` to something else (`code.py.bak`)
Method 2: Safe mode - hold BOOTSEL during boot

## Updating Code

To update the driver:
1. Edit files on CIRCUITPY drive
2. Save
3. Pico automatically reloads (no need to unplug!)

Or:

1. Connect to serial console
2. Press **Ctrl+C** to stop
3. Edit files
4. Press **Ctrl+D** to restart

## Production Deployment

For final deployment:
1. Verify sensor readings are accurate
2. Set appropriate refresh rate (4Hz recommended)
3. Disconnect from computer
4. Power Pico from USB power supply or battery
5. Code runs automatically on power-up!

## Next Steps

Once installed and running:
1. ✓ Verify sensor readings with visualizer
2. ✓ Test at different refresh rates
3. ✓ Check confidence values are high (>80%)
4. ✓ Mount sensor in final position
5. ✓ Test with actual tyre

Your Pico is now a standalone thermal tyre sensor! 🎉

# Installation Checklist

Quick checklist to verify your Pico is set up correctly.

## ✅ Pre-Installation

- [ ] Raspberry Pi Pico (or Pico W)
- [ ] MLX90640 thermal camera sensor
- [ ] USB cable (data, not just power)
- [ ] 4.7kΩ resistors × 2 (for I2C pull-ups) OR breakout board with built-in pull-ups

## ✅ CircuitPython Installation

- [ ] Downloaded CircuitPython .uf2 file from https://circuitpython.org/board/raspberry_pi_pico/
- [ ] Held BOOTSEL button while plugging in Pico
- [ ] Saw RPI-RP2 drive appear
- [ ] Copied .uf2 file to RPI-RP2
- [ ] Pico rebooted
- [ ] CIRCUITPY drive now appears

## ✅ Libraries Installation

- [ ] Downloaded CircuitPython libraries bundle
- [ ] Created `lib/` folder on CIRCUITPY
- [ ] Copied `adafruit_mlx90640.mpy` to `CIRCUITPY/lib/`
- [ ] Copied `adafruit_bus_device/` folder to `CIRCUITPY/lib/`

Verify:
```
CIRCUITPY/lib/adafruit_mlx90640.mpy exists ✓
CIRCUITPY/lib/adafruit_bus_device/__init__.mpy exists ✓
```

## ✅ Driver Installation

Copy these 4 files to CIRCUITPY root:

- [ ] `boot.py` → `CIRCUITPY/boot.py`
- [ ] `code.py` → `CIRCUITPY/code.py`
- [ ] `thermal_tyre_pico.py` → `CIRCUITPY/thermal_tyre_pico.py`
- [ ] `communication.py` → `CIRCUITPY/communication.py`

## ✅ Hardware Connection

MLX90640 to Pico wiring:

- [ ] VDD → Pico 3V3 (Pin 36)
- [ ] GND → Pico GND (Pin 38)
- [ ] SDA → Pico GP0 (Pin 1)
- [ ] SCL → Pico GP1 (Pin 2)
- [ ] 4.7kΩ pull-up: SDA to 3V3
- [ ] 4.7kΩ pull-up: SCL to 3V3

**Double-check:**
- [ ] Using 3.3V (NOT 5V!)
- [ ] Connections are solid (no loose wires)
- [ ] Sensor breakout has power LED on (if present)

## ✅ First Boot Test

- [ ] Unplugged Pico from USB
- [ ] Plugged Pico back in
- [ ] Green LED on Pico blinks (CircuitPython running)

## ✅ Serial Console Test

macOS/Linux:
```bash
ls /dev/tty.usb*  # Should show a port
screen /dev/tty.usbmodem14201 115200
```

You should see:
```
==================================================
Thermal Tyre Sensor - Auto-start
==================================================

Initializing sensor at 4Hz...
✓ Sensor ready
✓ Serial ready
```

- [ ] Saw startup messages
- [ ] No error messages
- [ ] Sensor initialized successfully

## ✅ Data Output Test

After a few seconds, you should see output like:
```json
{
  "frame_number": 1,
  "analysis": {
    "left": {"avg": 23.5, ...},
    ...
  }
}
```

- [ ] JSON data appearing
- [ ] Frame numbers incrementing
- [ ] Temperature values reasonable (15-40°C at room temp)

## ✅ Sensor Functionality Test

Point sensor at your hand (warm) or ice cube (cold):

- [ ] Temperature values change
- [ ] Centre temperature different from left/right when hand is off-center
- [ ] Confidence >50%

## ✅ Visualizer Test (Mac)

```bash
cd thermal-tyre-driver/pico
pip3 install -r requirements_visualizer.txt
python3 visualizer.py
```

- [ ] Visualizer window opens
- [ ] Live data updating
- [ ] Temperature bars moving when pointing sensor at hand
- [ ] No "No data" errors

## ✅ Auto-Run Test

- [ ] Unplugged Pico
- [ ] Waited 5 seconds
- [ ] Plugged Pico back in
- [ ] Code started automatically (no button presses needed)
- [ ] Serial output begins within 5 seconds

## 🎉 Installation Complete!

If all boxes are checked, your thermal tyre sensor is:
- ✅ Properly installed
- ✅ Running automatically on boot
- ✅ Outputting data over serial
- ✅ Ready for deployment

## 🔧 If Something Failed

### No CIRCUITPY drive
→ CircuitPython not installed correctly. Redo step 1.

### Library import errors
→ Libraries not in `lib/` folder. Check paths exactly match.

### "I2C timeout" errors
→ Wiring issue or missing pull-ups. Check connections and resistors.

### No serial output
→ Check `boot.py` exists. Try different serial port (tty.usbmodem14203 vs 14201).

### Sensor values all 0°C or 999°C
→ Sensor not communicating. Check I2C wiring and pull-ups.

### Code doesn't auto-run
→ File must be named exactly `code.py` (not `code.py.txt`)

## 📝 Configuration

Edit `CIRCUITPY/code.py` to customize:

```python
REFRESH_RATE = 4     # Change to 8 for faster (4 recommended)
COMPACT_SERIAL = False  # Change to True for CSV format
```

Save file → Pico auto-reloads!

## 🚀 You're Done!

Your Pico is now a standalone thermal sensor. Unplug it, power it from any USB source, and it will automatically start sensing and transmitting temperature data.

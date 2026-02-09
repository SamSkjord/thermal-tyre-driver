# Thermal Visualizer

Real-time visualization tool for the MLX90640 thermal camera data from the Pico.

## Installation

Install the required Python packages:

```bash
pip install -r requirements_visualizer.txt
```

This installs:
- pyserial (for serial communication)
- matplotlib (for visualization)
- numpy (for data processing)

## Usage

### Basic Usage (Auto-detect Pico)

```bash
python3 visualizer.py
```

The visualizer will automatically detect your Pico's USB serial port.

### Specify Port Manually

```bash
python3 visualizer.py --port /dev/tty.usbmodem14201
```

On Linux:
```bash
python3 visualizer.py --port /dev/ttyACM0
```

On Windows:
```bash
python visualizer.py --port COM3
```

### List Available Ports

```bash
python3 visualizer.py --list
```

### Adjust Baud Rate

The default baud rate is 115200. To change it:

```bash
python3 visualizer.py --baudrate 921600
```

**Note:** Make sure the Pico firmware uses the same baud rate!

### Adjust History Length

Control how many frames are kept in the history graphs (default: 100):

```bash
python3 visualizer.py --history 200
```

## Display

The visualizer shows:

1. **Current Temperatures** - Bar chart of left/centre/right zone temperatures
2. **Temperature History** - Line graph showing temperature trends over time
3. **Detection Confidence** - Horizontal bar showing tyre detection confidence
4. **Temperature Profile** - 32-pixel horizontal temperature profile across the sensor
5. **Lateral Gradient** - Temperature gradient across the tyre surface
6. **Status Panel** - Frame count, FPS, warnings, and detection status

## Data Format

The visualizer supports two output formats from the C code:

### CSV Format (COMPACT_OUTPUT = 1)
```
Frame,FPS,L_avg,L_med,C_avg,C_med,R_avg,R_med,Width,Conf,Det
```

**Note:** In CSV mode, the temperature profile display will show "Profile data not available in CSV mode"

### JSON Format (COMPACT_OUTPUT = 0)
```json
{
  "frame_number": 123,
  "fps": 7.5,
  "analysis": {
    "left": {"avg": 25.1, "median": 25.0, ...},
    "centre": {"avg": 30.2, "median": 30.1, ...},
    "right": {"avg": 28.5, "median": 28.3, ...},
    "lateral_gradient": 5.2
  },
  "detection": {
    "detected": 1,
    "span_start": 8,
    "span_end": 23,
    "tyre_width": 15,
    "confidence": 0.95
  },
  "temperature_profile": [20.1, 20.5, ...],
  "warnings": []
}
```

**Recommended:** Use JSON format for full visualization features including temperature profile.

## Switching Output Format

Edit `main.c` and change:

```c
#define COMPACT_OUTPUT 1  // 1 for CSV, 0 for JSON
```

Then rebuild and flash:

```bash
./build_and_flash.sh
```

## Troubleshooting

### No data appearing

1. Check that the Pico is connected and running
2. Verify the correct port with `--list`
3. Check baud rate matches (115200 by default)
4. Look for errors in the terminal

### Slow/choppy visualization

1. Reduce history length: `--history 50`
2. The C version should achieve 5-10 fps
3. Check if debug messages are slowing down the Pico (disable in main.c)

### "No Pico device found"

Use `--list` to see available ports, then specify manually with `--port`

## Performance Notes

The visualizer automatically handles frame rate mismatches:

- **Pico Data Rate**: ~11.5 fps (87ms per frame)
- **Visualization Rate**: ~4 fps (250ms per frame)
- **Frame Skipping**: The visualizer automatically drops frames to always show the latest data

This is normal and expected - matplotlib is slower than the C firmware. The visualizer will show the "Dropped" count in the status panel. This doesn't affect the Pico's performance, only the visualization.

**Dropped frames** = Frames received but not displayed (because visualization is slower than data rate)

## Tips

- Close the visualizer window to exit cleanly
- Press Ctrl+C in terminal to force quit
- For best performance, use JSON mode and disable verbose debug output in main.c
- The "Dropped" counter shows frames skipped for display, not data loss
- The Pico continues running at full speed regardless of visualization rate

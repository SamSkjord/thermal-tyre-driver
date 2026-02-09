"""
code.py - Auto-runs on Pico boot
Main thermal tyre sensor application
"""

import board
import time
from thermal_tyre_pico import TyreThermalSensor, SensorConfig
from communication import SerialCommunicator

# Configuration
COMPACT_SERIAL = True  # True for CSV format, False for full JSON (CSV is MUCH faster!)
REFRESH_RATE = 8  # Hz - sensor set to 8Hz, actual achievable: ~1.5fps due to library

# Performance note: CircuitPython + Adafruit MLX90640 library achieves ~1.5fps
# regardless of sensor refresh rate setting (tested 4Hz, 8Hz, 16Hz all ~670ms/frame)
# This is a library limitation, not hardware. For faster rates, use MicroPython or C.

def main():
    print("\n" + "="*50)
    print("Thermal Tyre Sensor - Auto-start")
    print("="*50)

    # Create sensor configuration
    config = SensorConfig()
    config.refresh_rate = REFRESH_RATE

    # Initialize sensor
    print(f"\nInitializing sensor at {REFRESH_RATE}Hz...")
    try:
        sensor = TyreThermalSensor(config=config)
        print("✓ Sensor ready")
    except Exception as e:
        print(f"✗ Sensor init failed: {e}")
        print("\nCheck:")
        print("  - MLX90640 connected to GP0(SDA)/GP1(SCL)")
        print("  - 3.3V power to sensor")
        print("  - 4.7kΩ pull-ups on SDA/SCL")
        return

    # Initialize serial communication
    try:
        serial = SerialCommunicator()
        print("✓ Serial ready")
    except Exception as e:
        print(f"✗ Serial init failed: {e}")
        return

    # Main loop
    print(f"\n{'='*50}")
    print(f"Running at {REFRESH_RATE}Hz...")
    print(f"Output: {'Compact CSV' if COMPACT_SERIAL else 'Full JSON'}")
    print(f"{'='*50}\n")

    frame_interval = 1.0 / REFRESH_RATE
    frame_count = 0
    error_count = 0
    max_errors = 10

    while True:
        try:
            # Read sensor
            print(f"Reading frame {frame_count + 1}...", end=" ")
            data = sensor.read()
            print("✓")

            frame_count += 1
            error_count = 0  # Reset error count on success

            # Send via serial
            if COMPACT_SERIAL:
                serial.send_compact(data)
            else:
                serial.send_data(data)

            # Print summary every 10 frames (console status)
            if frame_count % 10 == 0:
                a = data.analysis
                print(f"[{frame_count}] L={a.left.avg:.1f}°C "
                      f"C={a.centre.avg:.1f}°C "
                      f"R={a.right.avg:.1f}°C "
                      f"conf={data.detection.confidence:.0%}")

            # Wait for next frame
            time.sleep(frame_interval)

        except KeyboardInterrupt:
            print("\n\nStopping (Ctrl+C pressed)...")
            break

        except Exception as e:
            error_count += 1
            print(f"Error (#{error_count}): {e}")

            if error_count >= max_errors:
                print(f"\n✗ Too many errors ({max_errors}), stopping.")
                print("Check sensor connection and restart Pico")
                break

            time.sleep(1.0)  # Wait before retry

    print("\n" + "="*50)
    print("Sensor stopped")
    print("="*50)


if __name__ == "__main__":
    main()

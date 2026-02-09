"""
code_debug.py - Debug version with timing information
Rename to code.py to use, or run manually to see where time is spent
"""

import board
import time
from thermal_tyre_pico import TyreThermalSensor, SensorConfig
from communication import SerialCommunicator

# Configuration
COMPACT_SERIAL = False
REFRESH_RATE = 8

def main():
    print("\n" + "="*50)
    print("Thermal Tyre Sensor - DEBUG MODE")
    print("="*50)

    # Initialize
    config = SensorConfig()
    config.refresh_rate = REFRESH_RATE

    print(f"\nInitializing sensor at {REFRESH_RATE}Hz...")
    sensor = TyreThermalSensor(config=config)
    print("✓ Sensor ready")

    serial = SerialCommunicator()
    print("✓ Serial ready\n")

    print("="*50)
    print("TIMING ANALYSIS - First 10 frames")
    print("="*50)

    for i in range(10):
        loop_start = time.monotonic()

        # Time sensor read
        read_start = time.monotonic()
        data = sensor.read()
        read_time = (time.monotonic() - read_start) * 1000  # ms

        # Time serialization
        serialize_start = time.monotonic()
        if COMPACT_SERIAL:
            serial.send_compact(data)
        else:
            serial.send_data(data)
        serialize_time = (time.monotonic() - serialize_start) * 1000  # ms

        loop_time = (time.monotonic() - loop_start) * 1000  # ms

        print(f"\nFrame {i+1}:")
        print(f"  Read:      {read_time:6.1f}ms")
        print(f"  Serialize: {serialize_time:6.1f}ms")
        print(f"  Total:     {loop_time:6.1f}ms")
        print(f"  Target:    {1000/REFRESH_RATE:6.1f}ms ({REFRESH_RATE}Hz)")

        if loop_time > 1000/REFRESH_RATE:
            print(f"  ⚠️ SLOW! Over budget by {loop_time - 1000/REFRESH_RATE:.1f}ms")

        # Don't sleep - measure actual achievable rate
        time.sleep(0.01)  # Just a tiny delay

    print("\n" + "="*50)
    print("ANALYSIS COMPLETE")
    print("="*50)


if __name__ == "__main__":
    main()

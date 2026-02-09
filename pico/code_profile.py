"""
code_profile.py - Performance profiling
Shows exactly where time is being spent
"""

import board
import time
from thermal_tyre_pico import TyreThermalSensor, SensorConfig
from communication import SerialCommunicator

print("\n" + "="*50)
print("PERFORMANCE PROFILING")
print("="*50)

# Initialize
config = SensorConfig()
config.refresh_rate = 4

print("\nInitializing...")
t0 = time.monotonic()
sensor = TyreThermalSensor(config=config)
print(f"Sensor init: {(time.monotonic() - t0)*1000:.0f}ms")

t0 = time.monotonic()
serial = SerialCommunicator()
print(f"Serial init: {(time.monotonic() - t0)*1000:.0f}ms")

print("\n" + "="*50)
print("Reading 5 frames with detailed timing...")
print("="*50)

for frame_num in range(5):
    print(f"\n--- Frame {frame_num + 1} ---")

    frame_start = time.monotonic()

    # Time the read operation
    t0 = time.monotonic()
    data = sensor.read()
    read_ms = (time.monotonic() - t0) * 1000

    # Time serialization
    t0 = time.monotonic()
    serial.send_compact(data)
    send_ms = (time.monotonic() - t0) * 1000

    total_ms = (time.monotonic() - frame_start) * 1000

    print(f"  sensor.read():  {read_ms:6.0f}ms")
    print(f"  serial.send():  {send_ms:6.0f}ms")
    print(f"  Total:          {total_ms:6.0f}ms")
    print(f"  Achievable fps: {1000/total_ms:.1f}")

    # Small delay
    time.sleep(0.1)

print("\n" + "="*50)
print("DIAGNOSIS")
print("="*50)

if read_ms > 500:
    print("\n⚠️  sensor.read() is VERY slow (>500ms)")
    print("This suggests CircuitPython is too slow for the algorithm.")
    print("\nSolutions:")
    print("1. Simplify algorithm (use mean instead of median)")
    print("2. Port to MicroPython (2-3x faster)")
    print("3. Port to C (10x faster)")
elif read_ms > 200:
    print("\n⚠️  sensor.read() is slow (>200ms)")
    print("At this speed, you can achieve ~5fps max.")
    print("Consider MicroPython for better performance.")
else:
    print("\n✓ sensor.read() speed is acceptable")
    print("Should achieve 4Hz easily.")

if send_ms > 50:
    print("\n⚠️  Serial send is slow")
    print("Use COMPACT_SERIAL = True for faster output")

print("\n" + "="*50)

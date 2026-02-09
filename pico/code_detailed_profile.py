"""
Detailed profiling - instruments the driver internally
Shows exactly which operation is slow
"""

import board
import time
import busio
import adafruit_mlx90640
from thermal_tyre_pico import SensorConfig

print("\n" + "="*50)
print("DETAILED PROFILING - Breaking down sensor.read()")
print("="*50)

# Manually recreate key parts with timing
config = SensorConfig()
config.refresh_rate = 4

# Initialize I2C and sensor
i2c = busio.I2C(board.GP1, board.GP0, frequency=400000)
mlx = adafruit_mlx90640.MLX90640(i2c)
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
time.sleep(1)

print("\nMeasuring individual operations...\n")

# Import the individual functions we need to test
from thermal_tyre_pico import calculate_median, calculate_mad, median_filter_1d

for test_num in range(3):
    print(f"--- Test {test_num + 1} ---")

    # 1. Frame read from sensor
    t0 = time.monotonic()
    frame = [0.0] * 768
    mlx.getFrame(frame)
    frame_read_ms = (time.monotonic() - t0) * 1000

    # 2. Convert to 2D
    t0 = time.monotonic()
    frame_2d = []
    for i in range(24):
        row = frame[i * 32:(i + 1) * 32]
        frame_2d.append(row)
    convert_ms = (time.monotonic() - t0) * 1000

    # 3. Extract middle rows
    t0 = time.monotonic()
    middle_rows = frame_2d[10:14]
    extract_ms = (time.monotonic() - t0) * 1000

    # 4. Calculate median across rows (collapse to 1D)
    t0 = time.monotonic()
    profile = []
    for col_idx in range(32):
        col_temps = [row[col_idx] for row in middle_rows]
        profile.append(calculate_median(col_temps))
    collapse_ms = (time.monotonic() - t0) * 1000

    # 5. Median filter (spatial)
    t0 = time.monotonic()
    profile = median_filter_1d(profile, size=3)
    filter_ms = (time.monotonic() - t0) * 1000

    # 6. Calculate MAD
    t0 = time.monotonic()
    mad = calculate_mad(profile)
    mad_ms = (time.monotonic() - t0) * 1000

    # 7. Region growing simulation (simplified)
    t0 = time.monotonic()
    median_temp = calculate_median(profile)
    # Simulate the iteration
    for i in range(32):
        _ = abs(profile[i] - median_temp)
    region_ms = (time.monotonic() - t0) * 1000

    # 8. Section analysis simulation
    t0 = time.monotonic()
    left_section = profile[0:10]
    centre_section = profile[10:22]
    right_section = profile[22:32]
    left_avg = sum(left_section) / len(left_section)
    centre_avg = sum(centre_section) / len(centre_section)
    right_avg = sum(right_section) / len(right_section)
    analysis_ms = (time.monotonic() - t0) * 1000

    total_ms = frame_read_ms + convert_ms + extract_ms + collapse_ms + filter_ms + mad_ms + region_ms + analysis_ms

    print(f"  1. Frame read:      {frame_read_ms:6.1f}ms")
    print(f"  2. Convert 2D:      {convert_ms:6.1f}ms")
    print(f"  3. Extract rows:    {extract_ms:6.1f}ms")
    print(f"  4. Collapse 1D:     {collapse_ms:6.1f}ms  ← calculate_median × 32")
    print(f"  5. Median filter:   {filter_ms:6.1f}ms  ← median_filter_1d")
    print(f"  6. MAD calc:        {mad_ms:6.1f}ms  ← calculate_mad")
    print(f"  7. Region grow:     {region_ms:6.1f}ms")
    print(f"  8. Analysis:        {analysis_ms:6.1f}ms")
    print(f"  ---")
    print(f"  Total measured:     {total_ms:6.1f}ms")
    print()

    time.sleep(0.2)

print("="*50)
print("ANALYSIS")
print("="*50)
print("\nLook for operations taking >100ms")
print("Those are the bottlenecks to optimize.")
print("\nExpected breakdown:")
print("  Frame read:  ~10-50ms (hardware)")
print("  Processing:  ~30-80ms (should be fast with mean)")
print("  Total:       ~50-130ms target")

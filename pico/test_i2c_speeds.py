"""
Test different I2C speeds to find optimal
MLX90640 supports up to 1MHz
"""

import board
import time
import busio
import adafruit_mlx90640

print("\n=== Testing I2C Speeds ===\n")

# Test different speeds
speeds = [
    (100000, "100kHz (slow)"),
    (400000, "400kHz (current)"),
    (800000, "800kHz"),
    (1000000, "1MHz (max)"),
]

frame = [0.0] * 768

for speed, label in speeds:
    print(f"\n--- Testing {label} ---")

    try:
        # Create I2C at this speed
        i2c = busio.I2C(board.GP1, board.GP0, frequency=speed)
        mlx = adafruit_mlx90640.MLX90640(i2c)
        mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ
        time.sleep(1.5)  # Let sensor stabilize

        # Test 3 frame reads
        times = []
        for i in range(3):
            t0 = time.monotonic()
            mlx.getFrame(frame)
            read_ms = (time.monotonic() - t0) * 1000
            times.append(read_ms)
            print(f"  Frame {i+1}: {read_ms:.0f}ms")
            time.sleep(0.01)

        avg = sum(times) / len(times)
        print(f"  Average: {avg:.0f}ms → {1000/avg:.1f} fps achievable")

        # Clean up
        i2c.deinit()
        time.sleep(0.5)

    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "="*50)
print("EXPECTED RESULTS")
print("="*50)
print("If I2C speed is the bottleneck:")
print("  100kHz: ~800-900ms")
print("  400kHz: ~700-800ms (current)")
print("  800kHz: ~400-500ms")
print("  1MHz:   ~300-400ms or better!")
print("\nIf frame time stays ~750ms at all speeds:")
print("  → Sensor capture time is the limit, not I2C")

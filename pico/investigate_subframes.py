"""
Investigate if we can read subframes directly instead of waiting for getFrame()
The MLX90640 has chess-pattern subframes that might be faster to access
"""

import board
import time
import busio
import adafruit_mlx90640

print("\n=== Investigating MLX90640 Subframe Behavior ===\n")

i2c = busio.I2C(board.GP1, board.GP0, frequency=1000000)
mlx = adafruit_mlx90640.MLX90640(i2c)

# Try 16Hz mode (fastest subframe rate)
print("Setting to 16Hz mode...")
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_16_HZ
time.sleep(2)

print("\nTesting 16Hz mode frame times:\n")

frame = [0.0] * 768
times = []

for i in range(10):
    t0 = time.monotonic()
    mlx.getFrame(frame)
    read_ms = (time.monotonic() - t0) * 1000
    times.append(read_ms)
    print(f"Frame {i+1:2d}: {read_ms:5.0f}ms")
    time.sleep(0.01)

avg = sum(times) / len(times)
print(f"\nAverage: {avg:.0f}ms → {1000/avg:.1f} fps")
print(f"\nExpected at 16Hz: ~125ms (two 62.5ms subframes)")
print(f"Actual: {avg:.0f}ms")

if avg > 200:
    print("\n⚠️ getFrame() is blocking longer than sensor capture time!")
    print("This is a library limitation, not sensor limitation.")
    print("\nPossible causes:")
    print("1. Library waits for multiple frame refreshes")
    print("2. Library has internal delays/polling")
    print("3. Need to use a different MLX90640 library")

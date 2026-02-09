"""
Simple test: Does 1MHz I2C work better than 400kHz?
Power cycle Pico before running to ensure clean state
"""

import board
import time
import busio
import adafruit_mlx90640

# Change this to test different speeds
TEST_SPEED = 1000000  # Try: 400000, 800000, 1000000

print(f"\n=== Testing I2C at {TEST_SPEED/1000:.0f}kHz ===\n")

# Create I2C at test speed
i2c = busio.I2C(board.GP1, board.GP0, frequency=TEST_SPEED)
print(f"I2C initialized at {TEST_SPEED/1000:.0f}kHz")

mlx = adafruit_mlx90640.MLX90640(i2c)
print("MLX90640 initialized")

mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ
print("Set to 8Hz refresh rate")

print("\nWaiting for sensor to stabilize...")
time.sleep(2)

print("\nReading 10 frames...\n")

frame = [0.0] * 768
times = []

for i in range(10):
    t0 = time.monotonic()
    mlx.getFrame(frame)
    read_ms = (time.monotonic() - t0) * 1000
    times.append(read_ms)

    avg_temp = sum(frame) / len(frame)
    print(f"Frame {i+1:2d}: {read_ms:5.0f}ms  (avg temp: {avg_temp:.1f}°C)")

    time.sleep(0.01)

print(f"\n{'='*50}")
print(f"Average frame time: {sum(times)/len(times):.0f}ms")
print(f"Achievable fps: {1000/(sum(times)/len(times)):.1f}")
print(f"{'='*50}")

print("\nNow try again with TEST_SPEED = 400000 and compare!")

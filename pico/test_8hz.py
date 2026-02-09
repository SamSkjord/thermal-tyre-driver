"""
Test if 8Hz sensor mode improves frame read time
"""

import board
import time
import busio
import adafruit_mlx90640

print("\n=== Testing 8Hz Mode ===\n")

i2c = busio.I2C(board.GP1, board.GP0, frequency=400000)
mlx = adafruit_mlx90640.MLX90640(i2c)

print("Setting refresh rate to 8Hz...")
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ
time.sleep(1)

print("Reading 5 frames...\n")

frame = [0.0] * 768

for i in range(5):
    t0 = time.monotonic()
    mlx.getFrame(frame)
    read_ms = (time.monotonic() - t0) * 1000

    print(f"Frame {i+1}: {read_ms:.0f}ms")
    time.sleep(0.01)  # Tiny delay

print(f"\nExpected at 8Hz: ~125ms per frame")
print("If still ~700ms, sensor itself is the limit")

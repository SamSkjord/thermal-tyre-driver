"""
Test the actual driver code step by step
"""

import board
import busio
import adafruit_mlx90640
import time

print("=== Driver Test ===\n")

# Step 1: Basic init
print("1. Creating I2C bus...")
i2c = busio.I2C(board.GP1, board.GP0, frequency=400000)
print("   ✓ Done")

# Step 2: Init sensor
print("\n2. Initializing MLX90640...")
mlx = adafruit_mlx90640.MLX90640(i2c)
print("   ✓ Done")

# Step 3: Set refresh rate (this might be the issue)
print("\n3. Setting refresh rate to 4Hz...")
try:
    mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
    print("   ✓ Done")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Step 4: Wait a moment for sensor to stabilize
print("\n4. Waiting for sensor to stabilize...")
time.sleep(1)
print("   ✓ Done")

# Step 5: Try reading multiple frames
print("\n5. Reading 5 frames...")
frame = [0.0] * 768
for i in range(5):
    try:
        print(f"   Frame {i+1}...", end=" ")
        mlx.getFrame(frame)
        avg = sum(frame) / len(frame)
        print(f"✓ (avg: {avg:.1f}°C)")
        time.sleep(0.25)  # 4Hz = 250ms
    except Exception as e:
        print(f"✗ Error: {e}")
        break

print("\n=== Test Complete ===")

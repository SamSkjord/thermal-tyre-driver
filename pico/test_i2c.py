"""
I2C diagnostic test for MLX90640
Run this first to verify sensor connectivity
"""

import board
import busio
import time

print("=== I2C Diagnostic Test ===\n")

# Test I2C bus
print("1. Testing I2C bus initialization...")
try:
    i2c = busio.I2C(board.GP1, board.GP0)
    print("   ✓ I2C bus created")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    exit()

# Scan for devices
print("\n2. Scanning for I2C devices...")
while not i2c.try_lock():
    pass

try:
    devices = i2c.scan()
    print(f"   Found {len(devices)} device(s):")
    for addr in devices:
        print(f"   - 0x{addr:02X}")

    if 0x33 in devices:
        print("   ✓ MLX90640 found at 0x33")
    else:
        print("   ✗ MLX90640 NOT found (expected at 0x33)")
        print("\n   Troubleshooting:")
        print("   - Check wiring: SDA→GP0, SCL→GP1")
        print("   - Verify 3.3V power to sensor")
        print("   - Check for 4.7kΩ pull-up resistors on SDA/SCL")
        print("   - Try different I2C pins")

finally:
    i2c.unlock()

# Test MLX90640 library
if 0x33 in devices:
    print("\n3. Testing MLX90640 initialization...")
    try:
        import adafruit_mlx90640
        mlx = adafruit_mlx90640.MLX90640(i2c)
        print("   ✓ MLX90640 library initialized")

        # Try reading a frame
        print("\n4. Testing frame read...")
        frame = [0.0] * 768
        mlx.getFrame(frame)
        print("   ✓ Frame read successful")

        # Show some stats
        min_temp = min(frame)
        max_temp = max(frame)
        avg_temp = sum(frame) / len(frame)
        print(f"\n   Frame stats:")
        print(f"   - Min: {min_temp:.1f}°C")
        print(f"   - Max: {max_temp:.1f}°C")
        print(f"   - Avg: {avg_temp:.1f}°C")

        print("\n✓ All tests passed! Sensor is working.")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("\n   This could be:")
        print("   - Library not installed (copy adafruit_mlx90640.mpy to lib/)")
        print("   - Sensor initialization issue")
        print("   - Communication problem")

print("\n=== Test Complete ===")

"""
Test the optimized MLX90640Fast library vs original Adafruit library
Measures frame read performance
"""

import board
import time
import busio

print("\n" + "="*60)
print("MLX90640 Library Performance Comparison")
print("="*60)

# Test 1: Original Adafruit library
print("\n[1/2] Testing ORIGINAL Adafruit library...")
print("-" * 60)

try:
    import adafruit_mlx90640
    i2c = busio.I2C(board.GP1, board.GP0, frequency=1000000)
    mlx_old = adafruit_mlx90640.MLX90640(i2c)
    mlx_old.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_16_HZ

    time.sleep(2)  # Let sensor stabilize

    frame_old = [0.0] * 768
    times_old = []

    print("Reading 10 frames...")
    for i in range(10):
        t0 = time.monotonic()
        mlx_old.getFrame(frame_old)
        elapsed_ms = (time.monotonic() - t0) * 1000
        times_old.append(elapsed_ms)
        print(f"  Frame {i+1:2d}: {elapsed_ms:6.1f}ms")

    avg_old = sum(times_old) / len(times_old)
    fps_old = 1000 / avg_old

    print(f"\nOriginal library results:")
    print(f"  Average: {avg_old:.1f}ms per frame")
    print(f"  FPS: {fps_old:.2f}")
    print(f"  Sample temps: L={frame_old[16]:.1f}°C, C={frame_old[384]:.1f}°C, R={frame_old[752]:.1f}°C")

    # Clean up
    i2c.deinit()
    time.sleep(1)

except Exception as e:
    print(f"❌ Original library test failed: {e}")
    avg_old = None

# Test 2: Optimized Fast library
print("\n[2/2] Testing OPTIMIZED Fast library...")
print("-" * 60)

try:
    from mlx90640_fast import MLX90640Fast, RefreshRate
    i2c = busio.I2C(board.GP1, board.GP0, frequency=1000000)
    mlx_new = MLX90640Fast(i2c)
    mlx_new.refresh_rate = RefreshRate.REFRESH_16_HZ

    time.sleep(2)  # Let sensor stabilize

    frame_new = [0.0] * 768
    times_new = []

    print("Reading 10 frames...")
    for i in range(10):
        t0 = time.monotonic()
        mlx_new.getFrame(frame_new)
        elapsed_ms = (time.monotonic() - t0) * 1000
        times_new.append(elapsed_ms)
        print(f"  Frame {i+1:2d}: {elapsed_ms:6.1f}ms")

    avg_new = sum(times_new) / len(times_new)
    fps_new = 1000 / avg_new

    print(f"\nOptimized library results:")
    print(f"  Average: {avg_new:.1f}ms per frame")
    print(f"  FPS: {fps_new:.2f}")
    print(f"  Sample temps: L={frame_new[16]:.1f}°C, C={frame_new[384]:.1f}°C, R={frame_new[752]:.1f}°C")

    # Clean up
    i2c.deinit()

except Exception as e:
    print(f"❌ Optimized library test failed: {e}")
    import traceback
    traceback.print_exc()
    avg_new = None

# Summary
print("\n" + "="*60)
print("PERFORMANCE SUMMARY")
print("="*60)

if avg_old and avg_new:
    speedup = avg_old / avg_new
    improvement_pct = ((avg_old - avg_new) / avg_old) * 100

    print(f"\nOriginal:  {avg_old:6.1f}ms/frame → {1000/avg_old:5.2f} fps")
    print(f"Optimized: {avg_new:6.1f}ms/frame → {1000/avg_new:5.2f} fps")
    print(f"\nSpeedup: {speedup:.2f}x faster")
    print(f"Improvement: {improvement_pct:.1f}% reduction in frame time")

    if avg_new < 200:
        print("\n✅ SUCCESS! Achieved target of <200ms per frame")
    elif avg_new < 400:
        print(f"\n⚡ Good improvement! {improvement_pct:.0f}% faster")
    else:
        print(f"\n⚠️  Still room for improvement")

elif avg_old:
    print(f"\nOriginal: {avg_old:.1f}ms/frame")
    print("Optimized test failed - check errors above")
elif avg_new:
    print(f"\nOptimized: {avg_new:.1f}ms/frame")
    print("Original test failed - check errors above")
else:
    print("\nBoth tests failed - check sensor connection")

print("\n" + "="*60)

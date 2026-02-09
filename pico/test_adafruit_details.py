"""
Test to understand what Adafruit library is actually doing
Add instrumentation to see retry loop behavior
"""

import board
import time
import busio

print("\n" + "="*60)
print("Analyzing Adafruit MLX90640 Behavior")
print("="*60)

# Patch the original library to add debug output
import adafruit_mlx90640

# Save original method
original_getframedata = adafruit_mlx90640.MLX90640._GetFrameData

def instrumented_getframedata(self, frameData):
    """Instrumented version that counts iterations"""
    dataReady = 0
    cnt = 0
    statusRegister = [0]
    controlRegister = [0]
    iterations = 0

    # Poll for data ready
    t_poll_start = time.monotonic()
    while dataReady == 0:
        self._I2CReadWords(0x8000, statusRegister)
        dataReady = statusRegister[0] & 0x0008
        iterations += 1
    t_poll_end = time.monotonic()
    poll_time_ms = (t_poll_end - t_poll_start) * 1000

    # The retry loop
    retry_count = 0
    t_retry_start = time.monotonic()
    while (dataReady != 0) and (cnt < 5):
        self._I2CWriteWord(0x8000, 0x0030)
        self._I2CReadWords(0x0400, frameData, end=832)
        self._I2CReadWords(0x8000, statusRegister)
        dataReady = statusRegister[0] & 0x0008
        cnt += 1
        retry_count += 1
    t_retry_end = time.monotonic()
    retry_time_ms = (t_retry_end - t_retry_start) * 1000

    if cnt > 4:
        raise RuntimeError("Too many retries")

    self._I2CReadWords(0x800D, controlRegister)
    frameData[832] = controlRegister[0]
    frameData[833] = statusRegister[0] & 0x0001

    print(f"  Poll: {iterations:3d} iters, {poll_time_ms:5.1f}ms | Retry: {retry_count} times, {retry_time_ms:5.1f}ms")

    return frameData[833]

# Monkey patch
adafruit_mlx90640.MLX90640._GetFrameData = instrumented_getframedata

print("\nInitializing sensor...")
i2c = busio.I2C(board.GP1, board.GP0, frequency=1000000)
mlx = adafruit_mlx90640.MLX90640(i2c)
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_16_HZ
time.sleep(2)

print("\nReading 5 frames with instrumentation:")
print("-" * 60)

frame = [0.0] * 768

for i in range(5):
    t0 = time.monotonic()
    mlx.getFrame(frame)
    elapsed_ms = (time.monotonic() - t0) * 1000
    print(f"Frame {i+1:2d}: {elapsed_ms:6.1f}ms total")

print("\n" + "="*60)
print("Analysis:")
print("- If retry_count > 1, that's the bottleneck")
print("- If poll time is high, that's the bottleneck")
print("="*60)

i2c.deinit()

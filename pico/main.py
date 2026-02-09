"""
Main example for Pico thermal tyre driver
Demonstrates serial and I2C peripheral output
"""

import board
import time
from thermal_tyre_pico import TyreThermalSensor, SensorConfig
from communication import SerialCommunicator, I2CPeripheralExtended

# Configuration
OUTPUT_MODE = "both"  # Options: "serial", "i2c", "both"
COMPACT_SERIAL = False  # True for compact format, False for full JSON
I2C_PERIPHERAL_ADDRESS = 0x42
REFRESH_INTERVAL = 0.25  # 4Hz (250ms) - recommended for CircuitPython

def main():
    global OUTPUT_MODE  # Allow modification of OUTPUT_MODE

    print("Initializing thermal tyre sensor")

    # Create sensor configuration
    config = SensorConfig()
    config.refresh_rate = 4  # Hz

    # Initialize sensor
    # Sensor uses I2C0 (GP0=SDA, GP1=SCL)
    try:
        sensor = TyreThermalSensor(config=config)
        print("Sensor initialized successfully")
    except Exception as e:
        print(f"Failed to initialize sensor: {e}")
        return

    # Initialize communications
    serial_comm = None
    i2c_comm = None

    if OUTPUT_MODE in ["serial", "both"]:
        try:
            serial_comm = SerialCommunicator()
            print("Serial communication initialized")
        except Exception as e:
            print(f"Serial init warning: {e}")

    if OUTPUT_MODE in ["i2c", "both"]:
        try:
            # I2C peripheral on I2C1 (GP4=SDA, GP5=SCL)
            i2c_comm = I2CPeripheralExtended(
                scl_pin=board.GP5,
                sda_pin=board.GP4,
                address=I2C_PERIPHERAL_ADDRESS
            )
            print(f"I2C peripheral initialized at address 0x{I2C_PERIPHERAL_ADDRESS:02X}")
        except Exception as e:
            print(f"I2C peripheral init warning: {e}")
            if OUTPUT_MODE == "i2c":
                print("Switching to serial-only mode")
                OUTPUT_MODE = "serial"

    # Main loop
    print("\nStarting main loop...")
    frame_count = 0
    last_read_time = time.monotonic()

    while True:
        try:
            current_time = time.monotonic()

            # Read sensor at defined interval
            if current_time - last_read_time >= REFRESH_INTERVAL:
                # Read thermal data
                data = sensor.read()
                frame_count += 1
                last_read_time = current_time

                # Send via serial
                if serial_comm:
                    if COMPACT_SERIAL:
                        serial_comm.send_compact(data)
                    else:
                        serial_comm.send_data(data)

                # Update I2C peripheral data
                if i2c_comm:
                    i2c_comm.update_data(data)

                # Print summary to console every 10 frames
                if frame_count % 10 == 0:
                    print(
                        f"Frame {frame_count}: "
                        f"L={data.analysis.left.avg:.1f}C "
                        f"C={data.analysis.centre.avg:.1f}C "
                        f"R={data.analysis.right.avg:.1f}C "
                        f"conf={data.detection.confidence:.0%} "
                        f"warn={len(data.warnings)}"
                    )

            # Service I2C peripheral (non-blocking)
            if i2c_comm:
                i2c_comm.service()

            # Small sleep to prevent tight loop
            time.sleep(0.001)

        except KeyboardInterrupt:
            print("\nStopping...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(1.0)

    print("Shutdown complete")


if __name__ == "__main__":
    main()

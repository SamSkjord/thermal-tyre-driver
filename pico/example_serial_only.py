"""
Simple example: Serial output only
Minimal configuration for basic usage
"""

import time
from thermal_tyre_pico import TyreThermalSensor
from communication import SerialCommunicator


def main():
    # Initialize sensor with defaults
    sensor = TyreThermalSensor()
    serial = SerialCommunicator()

    print("Thermal tyre sensor ready - outputting to serial")

    while True:
        try:
            # Read and send
            data = sensor.read()
            serial.send_data(data)

            # Wait for next reading
            time.sleep(0.25)  # 4Hz

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1.0)


if __name__ == "__main__":
    main()

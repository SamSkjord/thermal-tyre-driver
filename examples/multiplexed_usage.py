"""
Example showing how to read all four tyres via a TCA9548A I2C multiplexer.
"""

from datetime import datetime

import board
import busio

from thermal_tyre_driver import SensorConfig, TyreThermalSensor


def main() -> None:
    config = SensorConfig(include_raw_frame=False, refresh_rate=4)

    try:
        i2c_bus = busio.I2C(board.SCL, board.SDA)
    except Exception as exc:
        print(f"[{datetime.now().isoformat()}] Failed to open I2C bus: {exc}")
        return

    sensors = {
        "FRONT_LEFT": TyreThermalSensor(
            sensor_id="FRONT_LEFT",
            config=config,
            mux_address=0x70,
            mux_channel=0,
            i2c_bus=i2c_bus,
        ),
        "FRONT_RIGHT": TyreThermalSensor(
            sensor_id="FRONT_RIGHT",
            config=config,
            mux_address=0x70,
            mux_channel=1,
            i2c_bus=i2c_bus,
        ),
        "REAR_LEFT": TyreThermalSensor(
            sensor_id="REAR_LEFT",
            config=config,
            mux_address=0x70,
            mux_channel=2,
            i2c_bus=i2c_bus,
        ),
        "REAR_RIGHT": TyreThermalSensor(
            sensor_id="REAR_RIGHT",
            config=config,
            mux_address=0x70,
            mux_channel=3,
            i2c_bus=i2c_bus,
        ),
    }

    for position, sensor in sensors.items():
        try:
            data = sensor.read()
        except Exception as exc:
            print(f"[{datetime.now().isoformat()}] {position} read failed: {exc}")
            continue

        print(
            f"{position}: span={data.detection.span_start}-{data.detection.span_end} "
            f"confidence={data.detection.confidence:.0%} "
            f"temps(L/C/R)=("
            f"{data.analysis.left.avg:.1f}/"
            f"{data.analysis.centre.avg:.1f}/"
            f"{data.analysis.right.avg:.1f}°C)"
        )


if __name__ == "__main__":
    main()

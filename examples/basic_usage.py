"""
Basic example demonstrating how to collect tyre thermal data with the library.
"""

from datetime import datetime

from thermal_tyre_driver import SensorConfig, TyreThermalSensor


def main() -> None:
    config = SensorConfig(
        include_raw_frame=False,
        refresh_rate=4,
    )
    sensor = TyreThermalSensor(sensor_id="FRONT_LEFT", config=config)

    try:
        data = sensor.read()
    except Exception as exc:
        print(f"[{datetime.now().isoformat()}] Sensor read failed: {exc}")
        return

    print(data.to_json())


if __name__ == "__main__":
    main()

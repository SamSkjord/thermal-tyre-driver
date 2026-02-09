"""
Example I2C controller (master) code
Reads thermal data from Pico acting as I2C peripheral

Run this on a Raspberry Pi or other controller to read data from the Pico
"""

import time
import board
import busio
import struct


class TyreDataReader:
    """Read thermal tyre data from Pico via I2C"""

    # Register addresses (must match I2CPeripheralExtended)
    REG_TEMP_LEFT = 0x00
    REG_TEMP_CENTRE = 0x02
    REG_TEMP_RIGHT = 0x04
    REG_CONFIDENCE = 0x06
    REG_WARNINGS = 0x07
    REG_SPAN_START = 0x08
    REG_SPAN_END = 0x09
    REG_WIDTH = 0x0A
    REG_GRADIENT = 0x0B
    REG_FRAME_COUNT = 0x0D

    def __init__(self, i2c_bus, device_address=0x42):
        """
        Initialize reader

        Args:
            i2c_bus: I2C bus instance
            device_address: Address of Pico I2C peripheral
        """
        self.i2c = i2c_bus
        self.address = device_address

    def _read_register(self, register, num_bytes=1):
        """Read bytes from a register"""
        result = bytearray(num_bytes)
        try:
            # Write register address
            self.i2c.writeto(self.address, bytes([register]))
            # Read data
            self.i2c.readfrom_into(self.address, result)
            return result
        except Exception as e:
            print(f"I2C read error: {e}")
            return None

    def _read_int16(self, register):
        """Read signed 16-bit integer from register"""
        data = self._read_register(register, 2)
        if data:
            return struct.unpack('<h', data)[0]
        return None

    def _read_uint8(self, register):
        """Read unsigned 8-bit integer from register"""
        data = self._read_register(register, 1)
        if data:
            return data[0]
        return None

    def read_temperatures(self):
        """
        Read left, centre, right temperatures

        Returns:
            Tuple of (left, centre, right) in degrees C, or None on error
        """
        left = self._read_int16(self.REG_TEMP_LEFT)
        centre = self._read_int16(self.REG_TEMP_CENTRE)
        right = self._read_int16(self.REG_TEMP_RIGHT)

        if left is not None and centre is not None and right is not None:
            return (left / 10.0, centre / 10.0, right / 10.0)
        return None

    def read_confidence(self):
        """Read detection confidence (0.0 - 1.0)"""
        conf = self._read_uint8(self.REG_CONFIDENCE)
        return conf / 100.0 if conf is not None else None

    def read_warnings_count(self):
        """Read number of warnings"""
        return self._read_uint8(self.REG_WARNINGS)

    def read_span(self):
        """
        Read detected tyre span

        Returns:
            Tuple of (start, end, width) or None
        """
        start = self._read_uint8(self.REG_SPAN_START)
        end = self._read_uint8(self.REG_SPAN_END)
        width = self._read_uint8(self.REG_WIDTH)

        if start is not None and end is not None and width is not None:
            return (start, end, width)
        return None

    def read_gradient(self):
        """Read lateral temperature gradient in degrees C"""
        grad = self._read_int16(self.REG_GRADIENT)
        return grad / 10.0 if grad is not None else None

    def read_frame_count(self):
        """Read frame counter"""
        data = self._read_register(self.REG_FRAME_COUNT, 2)
        if data:
            return struct.unpack('<H', data)[0]
        return None

    def read_all(self):
        """
        Read all data at once

        Returns:
            Dictionary with all available data
        """
        temps = self.read_temperatures()
        confidence = self.read_confidence()
        warnings = self.read_warnings_count()
        span = self.read_span()
        gradient = self.read_gradient()
        frame_count = self.read_frame_count()

        return {
            "temperatures": temps,
            "confidence": confidence,
            "warnings_count": warnings,
            "span": span,
            "gradient": gradient,
            "frame_count": frame_count
        }


def main():
    """Example usage"""
    print("I2C Controller - Reading from Pico thermal sensor")

    # Initialize I2C bus
    i2c = busio.I2C(board.SCL, board.SDA)

    # Create reader
    reader = TyreDataReader(i2c, device_address=0x42)

    print("Reading thermal data...")

    while True:
        try:
            # Read all data
            data = reader.read_all()

            if data["temperatures"]:
                left, centre, right = data["temperatures"]
                print(
                    f"Frame {data['frame_count']}: "
                    f"L={left:.1f}C C={centre:.1f}C R={right:.1f}C "
                    f"conf={data['confidence']:.0%} "
                    f"grad={data['gradient']:.1f}C "
                    f"warn={data['warnings_count']}"
                )
            else:
                print("No data available")

            time.sleep(0.5)

        except KeyboardInterrupt:
            print("\nStopping...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1.0)


if __name__ == "__main__":
    main()

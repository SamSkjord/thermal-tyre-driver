"""
Communication module for Pico thermal tyre driver
Handles serial (USB CDC) and I2C peripheral output
"""

import board
import busio
try:
    import json
except ImportError:
    import ujson as json

try:
    from i2ctarget import I2CTarget
except ImportError:
    # Fallback for older CircuitPython versions
    try:
        from i2cperipheral import I2CPeripheral as I2CTarget
    except ImportError:
        I2CTarget = None


class SerialCommunicator:
    """
    Handles serial communication over USB CDC
    Sends TyreThermalData as JSON over serial
    """

    def __init__(self, uart=None):
        """
        Initialize serial communicator

        Args:
            uart: Optional UART instance. If None, uses USB CDC (Serial)
        """
        if uart is not None:
            self.serial = uart
        else:
            # Use USB CDC Serial (available on Pico via USB)
            try:
                import usb_cdc
                # Use console for simplicity (single port, easier debugging)
                # For production, you could use usb_cdc.data
                self.serial = usb_cdc.console
            except ImportError:
                # For non-USB boards, would need UART
                raise RuntimeError("USB CDC not available, provide UART instance")

    def send_data(self, thermal_data):
        """
        Send TyreThermalData over serial as JSON

        Args:
            thermal_data: TyreThermalData instance
        """
        try:
            # Convert to dict
            data_dict = thermal_data.to_dict()

            # Serialize to JSON
            json_str = json.dumps(data_dict)

            # Send with newline delimiter
            message = json_str + "\n"

            if self.serial and hasattr(self.serial, 'write'):
                self.serial.write(message.encode('utf-8'))
                return True
            else:
                print(message)  # Fallback to print
                return True

        except Exception as e:
            print(f"Serial send error: {e}")
            return False

    def send_compact(self, thermal_data):
        """
        Send compact format (less bandwidth)

        Format: frame,L_avg,C_avg,R_avg,confidence,warnings_count
        """
        try:
            a = thermal_data.analysis
            d = thermal_data.detection

            compact_line = (
                f"{thermal_data.frame_number},"
                f"{a.left.avg:.1f},"
                f"{a.centre.avg:.1f},"
                f"{a.right.avg:.1f},"
                f"{d.confidence:.2f},"
                f"{len(thermal_data.warnings)}\n"
            )

            if self.serial and hasattr(self.serial, 'write'):
                self.serial.write(compact_line.encode('utf-8'))
                return True
            else:
                print(compact_line, end='')
                return True

        except Exception as e:
            print(f"Serial send error: {e}")
            return False


class I2CPeripheralCommunicator:
    """
    I2C Peripheral (slave) mode communicator
    Allows Pico to act as I2C device that can be read by a controller
    """

    def __init__(self, scl_pin, sda_pin, address=0x42):
        """
        Initialize I2C peripheral communicator

        Args:
            scl_pin: SCL pin (e.g., board.GP5)
            sda_pin: SDA pin (e.g., board.GP4)
            address: I2C address for this device (default 0x42)
        """
        if I2CTarget is None:
            raise RuntimeError("I2C peripheral mode not available")

        self.address = address
        self.latest_data = None
        self.data_buffer = bytearray()

        # Create I2C peripheral
        try:
            self.i2c_peripheral = I2CTarget(
                scl=scl_pin,
                sda=sda_pin,
                addresses=[address],
                smbus=False
            )
        except Exception as e:
            raise RuntimeError(f"Failed to init I2C peripheral: {e}")

    def update_data(self, thermal_data):
        """
        Update the data buffer with new thermal data

        Args:
            thermal_data: TyreThermalData instance
        """
        self.latest_data = thermal_data

        # Create compact binary format for I2C
        # Format: [L_avg(2), C_avg(2), R_avg(2), confidence(1), warnings_count(1)]
        # Total: 8 bytes
        try:
            a = thermal_data.analysis
            d = thermal_data.detection

            # Convert temps to int16 (tenths of degree)
            left_temp = int(a.left.avg * 10)
            centre_temp = int(a.centre.avg * 10)
            right_temp = int(a.right.avg * 10)

            # Confidence as uint8 (0-100)
            confidence = int(d.confidence * 100)

            # Warnings count
            warnings_count = min(len(thermal_data.warnings), 255)

            # Pack into bytes (little-endian)
            self.data_buffer = bytearray([
                left_temp & 0xFF,
                (left_temp >> 8) & 0xFF,
                centre_temp & 0xFF,
                (centre_temp >> 8) & 0xFF,
                right_temp & 0xFF,
                (right_temp >> 8) & 0xFF,
                confidence,
                warnings_count
            ])

        except Exception as e:
            print(f"I2C buffer update error: {e}")

    def service(self):
        """
        Service I2C requests (call this regularly in main loop)
        Non-blocking - returns immediately if no request pending
        """
        try:
            request = self.i2c_peripheral.request()

            if request:
                # Controller is requesting data
                if request.address == self.address and not request.is_write:
                    # Read request - send data
                    if self.data_buffer:
                        request.write(self.data_buffer)
                    else:
                        # No data yet, send zeros
                        request.write(bytearray(8))

                # Close the request
                request.close()

        except Exception as e:
            # Don't print every error - just return silently
            pass


class I2CPeripheralExtended:
    """
    Extended I2C peripheral with register-based access
    Allows reading different data via register addressing
    """

    # Register map
    REG_TEMP_LEFT = 0x00      # 2 bytes
    REG_TEMP_CENTRE = 0x02    # 2 bytes
    REG_TEMP_RIGHT = 0x04     # 2 bytes
    REG_CONFIDENCE = 0x06     # 1 byte
    REG_WARNINGS = 0x07       # 1 byte
    REG_SPAN_START = 0x08     # 1 byte
    REG_SPAN_END = 0x09       # 1 byte
    REG_WIDTH = 0x0A          # 1 byte
    REG_GRADIENT = 0x0B       # 2 bytes
    REG_FRAME_COUNT = 0x0D    # 2 bytes

    def __init__(self, scl_pin, sda_pin, address=0x42):
        """Initialize extended I2C peripheral with register map"""
        if I2CTarget is None:
            raise RuntimeError("I2C peripheral mode not available")

        self.address = address
        self.latest_data = None
        self.register_pointer = 0

        # Create register bank (16 bytes)
        self.registers = bytearray(16)

        try:
            self.i2c_peripheral = I2CTarget(
                scl=scl_pin,
                sda=sda_pin,
                addresses=[address],
                smbus=True  # Enable SMBus for register-based access
            )
        except Exception as e:
            raise RuntimeError(f"Failed to init I2C peripheral: {e}")

    def update_data(self, thermal_data):
        """Update register bank with new thermal data"""
        self.latest_data = thermal_data

        try:
            a = thermal_data.analysis
            d = thermal_data.detection

            # Convert temps to int16 (tenths of degree)
            left_temp = int(a.left.avg * 10)
            centre_temp = int(a.centre.avg * 10)
            right_temp = int(a.right.avg * 10)
            gradient = int(a.lateral_gradient * 10)

            # Update registers
            self.registers[self.REG_TEMP_LEFT] = left_temp & 0xFF
            self.registers[self.REG_TEMP_LEFT + 1] = (left_temp >> 8) & 0xFF

            self.registers[self.REG_TEMP_CENTRE] = centre_temp & 0xFF
            self.registers[self.REG_TEMP_CENTRE + 1] = (centre_temp >> 8) & 0xFF

            self.registers[self.REG_TEMP_RIGHT] = right_temp & 0xFF
            self.registers[self.REG_TEMP_RIGHT + 1] = (right_temp >> 8) & 0xFF

            self.registers[self.REG_CONFIDENCE] = int(d.confidence * 100)
            self.registers[self.REG_WARNINGS] = min(len(thermal_data.warnings), 255)

            self.registers[self.REG_SPAN_START] = d.span_start
            self.registers[self.REG_SPAN_END] = d.span_end
            self.registers[self.REG_WIDTH] = d.width

            self.registers[self.REG_GRADIENT] = gradient & 0xFF
            self.registers[self.REG_GRADIENT + 1] = (gradient >> 8) & 0xFF

            frame_count = thermal_data.frame_number & 0xFFFF
            self.registers[self.REG_FRAME_COUNT] = frame_count & 0xFF
            self.registers[self.REG_FRAME_COUNT + 1] = (frame_count >> 8) & 0xFF

        except Exception as e:
            print(f"Register update error: {e}")

    def service(self):
        """Service I2C requests with register addressing"""
        try:
            request = self.i2c_peripheral.request()

            if request and request.address == self.address:
                if request.is_write:
                    # Write request - set register pointer
                    data = request.read(1)
                    if data:
                        self.register_pointer = data[0] % len(self.registers)
                else:
                    # Read request - send data from register pointer
                    # Send up to 16 bytes from current register
                    bytes_to_send = min(16, len(self.registers) - self.register_pointer)
                    data = self.registers[self.register_pointer:
                                        self.register_pointer + bytes_to_send]
                    request.write(data)

                request.close()

        except Exception as e:
            pass

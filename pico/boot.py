"""
boot.py - Runs on startup before main code

Configures USB CDC for dual serial channels:
- Console (REPL)
- Data output

Place this in the root of CIRCUITPY drive
"""

import usb_cdc

# Enable dual USB serial channels
# - usb_cdc.console: REPL and debug output
# - usb_cdc.data: Thermal data output
usb_cdc.enable(console=True, data=True)

# Note: This will create two serial ports:
# - First port: Console (REPL)
# - Second port: Data channel for thermal readings
#
# On Linux:
#   /dev/ttyACM0 - Console
#   /dev/ttyACM1 - Data
#
# To read data in Python:
#   import serial
#   ser = serial.Serial('/dev/ttyACM1', 115200)
#   while True:
#       line = ser.readline()
#       print(line.decode())

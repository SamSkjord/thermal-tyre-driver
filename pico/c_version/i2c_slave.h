/**
 * i2c_slave.h
 * I2C slave/peripheral mode for downstream communication
 *
 * Uses i2c1 as slave while i2c0 remains master for MLX90640
 * Default slave address: 0x08
 */

#ifndef I2C_SLAVE_H
#define I2C_SLAVE_H

#include <stdint.h>
#include <stdbool.h>
#include "thermal_algorithm.h"

// Default I2C slave address
#define I2C_SLAVE_DEFAULT_ADDR 0x08

// Output modes
typedef enum {
    OUTPUT_MODE_USB_SERIAL = 0x00,  // USB serial (default)
    OUTPUT_MODE_I2C_SLAVE = 0x01,   // I2C slave/peripheral
    OUTPUT_MODE_CANBUS = 0x02,      // CAN bus (future)
    OUTPUT_MODE_ALL = 0xFF          // All outputs enabled
} OutputMode;

// I2C Register Map
// ================

// CONFIGURATION REGISTERS (0x00-0x0F) - Read/Write
#define REG_CONFIG_START        0x00
#define REG_I2C_ADDRESS         0x00  // I2C slave address (7-bit)
#define REG_OUTPUT_MODE         0x01  // Output mode select
#define REG_FRAME_RATE          0x02  // Target frame rate (future)
#define REG_FALLBACK_MODE       0x03  // Fallback mode: 0=zero temps when no tyre, 1=copy centre temp
#define REG_EMISSIVITY          0x04  // Emissivity × 100 (e.g., 95 = 0.95), default 95
#define REG_RAW_MODE            0x05  // Raw mode: 0=tyre algorithm, 1=16-channel raw data
#define REG_RESERVED_06         0x06
#define REG_RESERVED_07         0x07
#define REG_RESERVED_08         0x08
#define REG_RESERVED_09         0x09
#define REG_RESERVED_0A         0x0A
#define REG_RESERVED_0B         0x0B
#define REG_RESERVED_0C         0x0C
#define REG_RESERVED_0D         0x0D
#define REG_RESERVED_0E         0x0E
#define REG_RESERVED_0F         0x0F

// STATUS REGISTERS (0x10-0x1F) - Read Only
#define REG_STATUS_START        0x10
#define REG_FIRMWARE_VERSION    0x10  // Firmware version
#define REG_FRAME_NUMBER_L      0x11  // Frame counter (low byte)
#define REG_FRAME_NUMBER_H      0x12  // Frame counter (high byte)
#define REG_FPS                 0x13  // Current FPS (integer)
#define REG_DETECTED            0x14  // Tyre detected flag (0/1)
#define REG_CONFIDENCE          0x15  // Confidence (0-100%)
#define REG_TYRE_WIDTH          0x16  // Tyre width in pixels
#define REG_SPAN_START          0x17  // Tyre span start pixel
#define REG_SPAN_END            0x18  // Tyre span end pixel
#define REG_WARNINGS            0x19  // Warning flags
#define REG_RESERVED_1A         0x1A
#define REG_RESERVED_1B         0x1B
#define REG_RESERVED_1C         0x1C
#define REG_RESERVED_1D         0x1D
#define REG_RESERVED_1E         0x1E
#define REG_RESERVED_1F         0x1F

// TEMPERATURE DATA REGISTERS (0x20-0x3F) - Read Only
#define REG_TEMP_DATA_START     0x20
#define REG_LEFT_MEDIAN_L       0x20  // Left median temp (int16, tenths °C, low byte)
#define REG_LEFT_MEDIAN_H       0x21  // Left median temp (high byte)
#define REG_CENTRE_MEDIAN_L     0x22  // Centre median temp (low byte)
#define REG_CENTRE_MEDIAN_H     0x23  // Centre median temp (high byte)
#define REG_RIGHT_MEDIAN_L      0x24  // Right median temp (low byte)
#define REG_RIGHT_MEDIAN_H      0x25  // Right median temp (high byte)
#define REG_LEFT_AVG_L          0x26  // Left avg temp (low byte)
#define REG_LEFT_AVG_H          0x27  // Left avg temp (high byte)
#define REG_CENTRE_AVG_L        0x28  // Centre avg temp (low byte)
#define REG_CENTRE_AVG_H        0x29  // Centre avg temp (high byte)
#define REG_RIGHT_AVG_L         0x2A  // Right avg temp (low byte)
#define REG_RIGHT_AVG_H         0x2B  // Right avg temp (high byte)
#define REG_LATERAL_GRADIENT_L  0x2C  // Lateral gradient (low byte)
#define REG_LATERAL_GRADIENT_H  0x2D  // Lateral gradient (high byte)

// RAW 16-CHANNEL DATA (0x30-0x4F) - Read Only, active when RAW_MODE=1
// 16 channels × 2 bytes (int16 tenths) = 32 bytes
#define REG_RAW_CH0_L           0x30  // Channel 0 (leftmost) low byte
#define REG_RAW_CH0_H           0x31  // Channel 0 high byte
// Channels 1-15 follow sequentially at 0x32-0x4F
// Access via: 0x30 + (channel * 2) for low byte

// FULL FRAME ACCESS (0x50+) - Read Only
#define REG_FRAME_ACCESS        0x40  // Read pointer for full frame data
#define REG_FRAME_DATA_START    0x41  // Start of streaming frame data

// Special commands
#define REG_CMD                 0xFF  // Command register
#define CMD_RESET               0x01  // Software reset
#define CMD_CLEAR_WARNINGS      0x02  // Clear warning flags
#define CMD_FRAME_REQUEST       0x10  // Request new frame capture

// I2C slave state
typedef struct {
    uint8_t slave_address;      // Current I2C slave address
    OutputMode output_mode;     // Current output mode
    uint8_t current_register;   // Current register pointer
    uint16_t frame_read_offset; // Offset for full frame reads
    bool enabled;               // I2C slave enabled
} I2CSlaveState;

// Initialize I2C slave mode
void i2c_slave_init(uint8_t address);

// Update I2C slave registers with latest frame data
void i2c_slave_update(const FrameData *data, float fps, const float *frame);

// Get current output mode
OutputMode i2c_slave_get_output_mode(void);

// Set output mode
void i2c_slave_set_output_mode(OutputMode mode);

// Check if output mode is enabled
bool i2c_slave_output_enabled(OutputMode mode);

// Get emissivity value (as float 0.0-1.0)
float i2c_slave_get_emissivity(void);

// Get raw mode setting
bool i2c_slave_get_raw_mode(void);

#endif // I2C_SLAVE_H

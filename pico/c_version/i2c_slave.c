/**
 * i2c_slave.c
 * I2C slave/peripheral implementation
 */

#include "i2c_slave.h"
#include "hardware/i2c.h"
#include "hardware/irq.h"
#include "hardware/gpio.h"
#include <string.h>
#include <math.h>

// Use I2C1 for slave mode (I2C0 is used for MLX90640)
#define I2C_SLAVE_INST i2c1
#define I2C_SLAVE_SDA_PIN 26  // GP26
#define I2C_SLAVE_SCL_PIN 27  // GP27

// Internal state
static I2CSlaveState state;
static uint8_t register_map[256];  // Full register space
static const float *current_frame = NULL;  // Pointer to current frame data

// Helper to convert float temp to int16 tenths
static inline int16_t temp_to_int16_tenths(float temp) {
    if (!isfinite(temp)) return 0;
    return (int16_t)(temp * 10.0f);
}

// I2C slave IRQ handler
static void i2c_slave_handler(void) {
    uint32_t status = I2C_SLAVE_INST->hw->intr_stat;

    if (status & I2C_IC_INTR_STAT_R_RD_REQ_BITS) {
        // Master is reading from us
        uint8_t value = 0;

        if (state.current_register == REG_FRAME_DATA_START) {
            // Streaming full frame data
            if (current_frame && state.frame_read_offset < 768) {
                // Send as int16 tenths (2 bytes per pixel)
                uint16_t idx = state.frame_read_offset / 2;
                if (state.frame_read_offset % 2 == 0) {
                    // Low byte
                    int16_t temp = temp_to_int16_tenths(current_frame[idx]);
                    value = temp & 0xFF;
                } else {
                    // High byte
                    int16_t temp = temp_to_int16_tenths(current_frame[idx]);
                    value = (temp >> 8) & 0xFF;
                }
                state.frame_read_offset++;
            }
        } else {
            // Regular register read
            value = register_map[state.current_register];
            state.current_register++;  // Auto-increment
        }

        I2C_SLAVE_INST->hw->data_cmd = value;
        I2C_SLAVE_INST->hw->clr_rd_req;
    }

    if (status & I2C_IC_INTR_STAT_R_RX_FULL_BITS) {
        // Master is writing to us
        uint8_t value = (uint8_t)I2C_SLAVE_INST->hw->data_cmd;

        if (state.current_register == 0xFF) {
            // First byte is register address
            state.current_register = value;

            // Reset frame read offset when accessing frame data
            if (value == REG_FRAME_DATA_START) {
                state.frame_read_offset = 0;
            }
        } else {
            // Subsequent bytes are data writes
            if (state.current_register >= REG_CONFIG_START &&
                state.current_register <= REG_RESERVED_0F) {
                // Configuration registers are writable
                register_map[state.current_register] = value;

                // Handle special registers
                if (state.current_register == REG_I2C_ADDRESS) {
                    // I2C address change (requires restart)
                    state.slave_address = value & 0x7F;
                } else if (state.current_register == REG_OUTPUT_MODE) {
                    // Output mode change
                    state.output_mode = (OutputMode)value;
                }
            } else if (state.current_register == REG_CMD) {
                // Command register
                if (value == CMD_RESET) {
                    // Software reset (would need to implement)
                } else if (value == CMD_CLEAR_WARNINGS) {
                    register_map[REG_WARNINGS] = 0;
                }
            }

            state.current_register++;
        }
    }

    if (status & I2C_IC_INTR_STAT_R_STOP_DET_BITS) {
        // Stop condition - reset register pointer
        state.current_register = 0xFF;
        I2C_SLAVE_INST->hw->clr_stop_det;
    }
}

void i2c_slave_init(uint8_t address) {
    // Initialize state
    memset(&state, 0, sizeof(state));
    memset(register_map, 0, sizeof(register_map));

    state.slave_address = address;
    state.output_mode = OUTPUT_MODE_USB_SERIAL;  // Default to USB
    state.current_register = 0xFF;
    state.enabled = true;

    // Set firmware version
    register_map[REG_FIRMWARE_VERSION] = 0x01;  // Version 1

    // Set default config
    register_map[REG_I2C_ADDRESS] = address;
    register_map[REG_OUTPUT_MODE] = OUTPUT_MODE_USB_SERIAL;
    register_map[REG_FALLBACK_MODE] = 0;  // Default: return 0 when no tyre detected
    register_map[REG_EMISSIVITY] = 95;    // Default: 0.95 emissivity
    register_map[REG_RAW_MODE] = 0;       // Default: tyre algorithm enabled

    // Initialize I2C1 pins
    gpio_set_function(I2C_SLAVE_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SLAVE_SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SLAVE_SDA_PIN);
    gpio_pull_up(I2C_SLAVE_SCL_PIN);

    // Initialize I2C1 in slave mode
    i2c_init(I2C_SLAVE_INST, 100000);  // 100kHz (slave speed doesn't matter much)
    i2c_set_slave_mode(I2C_SLAVE_INST, true, address);

    // Enable I2C interrupts
    I2C_SLAVE_INST->hw->intr_mask =
        I2C_IC_INTR_MASK_M_RD_REQ_BITS |
        I2C_IC_INTR_MASK_M_RX_FULL_BITS |
        I2C_IC_INTR_MASK_M_STOP_DET_BITS;

    // Set up IRQ handler
    irq_set_exclusive_handler(I2C1_IRQ, i2c_slave_handler);
    irq_set_enabled(I2C1_IRQ, true);
}

void i2c_slave_update(const FrameData *data, float fps, const float *frame) {
    if (!state.enabled) return;

    // Store frame pointer for full frame access
    current_frame = frame;

    // Update status registers
    register_map[REG_FRAME_NUMBER_L] = data->frame_number & 0xFF;
    register_map[REG_FRAME_NUMBER_H] = (data->frame_number >> 8) & 0xFF;
    register_map[REG_FPS] = (uint8_t)fps;
    register_map[REG_DETECTED] = data->detection.detected ? 1 : 0;
    register_map[REG_CONFIDENCE] = (uint8_t)(data->detection.confidence * 100.0f);
    register_map[REG_TYRE_WIDTH] = data->detection.tyre_width;
    register_map[REG_SPAN_START] = data->detection.span_start;
    register_map[REG_SPAN_END] = data->detection.span_end;
    register_map[REG_WARNINGS] = data->warnings;

    // Update temperature data (as int16 tenths of degrees)
    int16_t left_med = temp_to_int16_tenths(data->left.median);
    int16_t centre_med = temp_to_int16_tenths(data->centre.median);
    int16_t right_med = temp_to_int16_tenths(data->right.median);
    int16_t left_avg = temp_to_int16_tenths(data->left.avg);
    int16_t centre_avg = temp_to_int16_tenths(data->centre.avg);
    int16_t right_avg = temp_to_int16_tenths(data->right.avg);
    int16_t lat_grad = temp_to_int16_tenths(data->lateral_gradient);

    // Check fallback mode - if no tyre detected and fallback enabled, copy centre temps
    if (!data->detection.detected && register_map[REG_FALLBACK_MODE] == 1) {
        left_med = centre_med;
        right_med = centre_med;
        left_avg = centre_avg;
        right_avg = centre_avg;
        lat_grad = 0;  // No gradient when copying centre temp
    }

    // Pack into registers (little-endian)
    register_map[REG_LEFT_MEDIAN_L] = left_med & 0xFF;
    register_map[REG_LEFT_MEDIAN_H] = (left_med >> 8) & 0xFF;
    register_map[REG_CENTRE_MEDIAN_L] = centre_med & 0xFF;
    register_map[REG_CENTRE_MEDIAN_H] = (centre_med >> 8) & 0xFF;
    register_map[REG_RIGHT_MEDIAN_L] = right_med & 0xFF;
    register_map[REG_RIGHT_MEDIAN_H] = (right_med >> 8) & 0xFF;

    register_map[REG_LEFT_AVG_L] = left_avg & 0xFF;
    register_map[REG_LEFT_AVG_H] = (left_avg >> 8) & 0xFF;
    register_map[REG_CENTRE_AVG_L] = centre_avg & 0xFF;
    register_map[REG_CENTRE_AVG_H] = (centre_avg >> 8) & 0xFF;
    register_map[REG_RIGHT_AVG_L] = right_avg & 0xFF;
    register_map[REG_RIGHT_AVG_H] = (right_avg >> 8) & 0xFF;

    register_map[REG_LATERAL_GRADIENT_L] = lat_grad & 0xFF;
    register_map[REG_LATERAL_GRADIENT_H] = (lat_grad >> 8) & 0xFF;

    // Calculate 16 raw channels if frame data is available
    // Each channel averages 2 columns × 4 middle rows = 8 pixels
    if (frame) {
        for (int ch = 0; ch < 16; ch++) {
            float sum = 0.0f;
            int col_start = ch * 2;  // Each channel covers 2 columns

            // Average 2 columns × 4 middle rows (rows 10-13)
            for (int row = 10; row < 14; row++) {
                for (int col = col_start; col < col_start + 2; col++) {
                    sum += frame[row * 32 + col];
                }
            }

            float avg = sum / 8.0f;  // 2 cols × 4 rows
            int16_t temp = temp_to_int16_tenths(avg);

            // Pack into registers at 0x30 + (ch * 2)
            uint8_t reg_base = REG_RAW_CH0_L + (ch * 2);
            register_map[reg_base] = temp & 0xFF;
            register_map[reg_base + 1] = (temp >> 8) & 0xFF;
        }
    }
}

OutputMode i2c_slave_get_output_mode(void) {
    return state.output_mode;
}

void i2c_slave_set_output_mode(OutputMode mode) {
    state.output_mode = mode;
    register_map[REG_OUTPUT_MODE] = (uint8_t)mode;
}

bool i2c_slave_output_enabled(OutputMode mode) {
    if (state.output_mode == OUTPUT_MODE_ALL) return true;
    return (state.output_mode == mode);
}

float i2c_slave_get_emissivity(void) {
    // Convert uint8 (0-100) to float (0.0-1.0)
    uint8_t emiss = register_map[REG_EMISSIVITY];
    if (emiss > 100) emiss = 100;  // Clamp to max 1.0
    return emiss / 100.0f;
}

bool i2c_slave_get_raw_mode(void) {
    return (register_map[REG_RAW_MODE] != 0);
}

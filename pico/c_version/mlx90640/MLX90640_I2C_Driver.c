/**
 * MLX90640_I2C_Driver.c
 * I2C driver implementation for Raspberry Pi Pico
 */

#include "MLX90640_I2C_Driver.h"
#include "hardware/i2c.h"
#include "pico/stdlib.h"
#include <string.h>

// I2C pins (moved to GP4/GP5 to free up UART0 for debug probe)
#define I2C_SDA_PIN 4
#define I2C_SCL_PIN 5
#define I2C_FREQ_HZ 1000000  // 1MHz

static i2c_inst_t *i2c = i2c0;

void MLX90640_I2CInit(void) {
    i2c_init(i2c, I2C_FREQ_HZ);
    gpio_set_function(I2C_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA_PIN);
    gpio_pull_up(I2C_SCL_PIN);
}

int MLX90640_I2CRead(uint8_t slaveAddr, uint16_t startAddress, uint16_t nWordsRead, uint16_t *data) {
    // For large reads (like EEPROM dump), split into chunks to avoid timeout
    // MLX90640 EEPROM is 832 words, which is 1664 bytes - too large for one transaction
    #define CHUNK_SIZE 32  // Read 32 words (64 bytes) at a time

    uint16_t words_remaining = nWordsRead;
    uint16_t current_address = startAddress;
    uint16_t *current_data = data;

    while (words_remaining > 0) {
        uint16_t words_this_chunk = (words_remaining > CHUNK_SIZE) ? CHUNK_SIZE : words_remaining;
        uint8_t addr_buf[2];
        uint8_t byte_buf[CHUNK_SIZE * 2];

        // Send register address (big-endian)
        addr_buf[0] = current_address >> 8;
        addr_buf[1] = current_address & 0xFF;

        int result = i2c_write_blocking(i2c, slaveAddr, addr_buf, 2, true);
        if (result < 0) {
            return -1;
        }

        // Read data chunk (will be in big-endian from sensor)
        int bytes_to_read = words_this_chunk * 2;
        result = i2c_read_blocking(i2c, slaveAddr, byte_buf, bytes_to_read, false);
        if (result < 0) {
            return -1;
        }

        // Convert from big-endian to host byte order
        for (int i = 0; i < words_this_chunk; i++) {
            uint16_t temp = (byte_buf[i*2] << 8) | byte_buf[i*2 + 1];
            current_data[i] = temp;
        }

        // Move to next chunk
        words_remaining -= words_this_chunk;
        current_address += words_this_chunk;
        current_data += words_this_chunk;

        // Small delay between chunks
        sleep_us(100);
    }

    return 0;
}

int MLX90640_I2CWrite(uint8_t slaveAddr, uint16_t writeAddress, uint16_t data) {
    uint8_t buf[4];

    // Address (big-endian)
    buf[0] = writeAddress >> 8;
    buf[1] = writeAddress & 0xFF;

    // Data (big-endian)
    buf[2] = data >> 8;
    buf[3] = data & 0xFF;

    int result = i2c_write_blocking(i2c, slaveAddr, buf, 4, false);
    if (result < 0) {
        return -1;
    }

    sleep_ms(1);  // Small delay for write to complete

    return 0;
}

void MLX90640_I2CFreqSet(int freq) {
    i2c_set_baudrate(i2c, freq);
}

/**
 * test_i2c_scan.c - Scan I2C bus to find MLX90640
 */

#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"

#define I2C_SDA_PIN 0
#define I2C_SCL_PIN 1
#define LED_PIN PICO_DEFAULT_LED_PIN

int main(void) {
    // Init LED
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    // Rapid blink
    for (int i = 0; i < 10; i++) {
        gpio_put(LED_PIN, 1);
        sleep_ms(50);
        gpio_put(LED_PIN, 0);
        sleep_ms(50);
    }

    // Init USB serial
    stdio_init_all();
    sleep_ms(3000);

    gpio_put(LED_PIN, 1);
    printf("\n=== I2C Scanner ===\n");
    printf("Initializing I2C on GP0 (SDA) and GP1 (SCL)...\n");

    i2c_init(i2c0, 400000);  // Start at 400kHz
    gpio_set_function(I2C_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA_PIN);
    gpio_pull_up(I2C_SCL_PIN);

    printf("Scanning I2C bus...\n");
    printf("   0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F\n");

    for (int addr = 0; addr < 128; addr++) {
        if (addr % 16 == 0) {
            printf("%02X ", addr);
        }

        uint8_t data;
        int ret = i2c_read_blocking(i2c0, addr, &data, 1, false);

        if (ret >= 0) {
            printf("%02X ", addr);
        } else {
            printf("-- ");
        }

        if (addr % 16 == 15) {
            printf("\n");
        }
    }

    printf("\nScan complete. MLX90640 should be at 0x33\n");
    printf("LED will blink slowly if found at 0x33\n");

    // Test 0x33 specifically
    uint8_t test_data;
    int ret = i2c_read_blocking(i2c0, 0x33, &test_data, 1, false);

    if (ret >= 0) {
        printf("\n✓ Device found at 0x33!\n");

        // Try to read the control register (0x800D)
        printf("Testing detailed read from control register 0x800D...\n");
        uint8_t addr_buf[2] = {0x80, 0x0D};
        uint8_t read_buf[2];

        ret = i2c_write_blocking(i2c0, 0x33, addr_buf, 2, true);
        printf("Write address result: %d\n", ret);

        if (ret >= 0) {
            ret = i2c_read_blocking(i2c0, 0x33, read_buf, 2, false);
            printf("Read data result: %d\n", ret);
            if (ret >= 0) {
                uint16_t value = (read_buf[0] << 8) | read_buf[1];
                printf("Control register value: 0x%04X\n", value);
            }
        }

        // Slow blink = success
        while (1) {
            gpio_put(LED_PIN, 1);
            sleep_ms(500);
            gpio_put(LED_PIN, 0);
            sleep_ms(500);
        }
    } else {
        printf("\n✗ No device at 0x33 (MLX90640 not detected)\n");
        printf("Check wiring:\n");
        printf("  MLX90640 VDD → Pico 3V3\n");
        printf("  MLX90640 GND → Pico GND\n");
        printf("  MLX90640 SDA → Pico GP0\n");
        printf("  MLX90640 SCL → Pico GP1\n");
        // Fast blink = error
        while (1) {
            gpio_put(LED_PIN, 1);
            sleep_ms(100);
            gpio_put(LED_PIN, 0);
            sleep_ms(100);
        }
    }

    return 0;
}

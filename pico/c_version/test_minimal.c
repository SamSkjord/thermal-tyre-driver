/**
 * test_minimal.c - Minimal test to verify USB serial works
 */

#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/gpio.h"

#define LED_PIN PICO_DEFAULT_LED_PIN

int main(void) {
    // Init LED
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    // Init USB serial
    stdio_init_all();

    // Wait for USB enumeration
    sleep_ms(2000);

    // Blink and print forever
    int count = 0;
    while (true) {
        gpio_put(LED_PIN, 1);
        printf("Hello from Pico! Count: %d\n", count++);
        sleep_ms(500);

        gpio_put(LED_PIN, 0);
        sleep_ms(500);
    }

    return 0;
}

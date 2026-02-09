/**
 * test_mlx_simple.c - Simple MLX90640 frame read test
 * Goal: Just read frames and print some temperatures to verify sensor works
 */

#include <stdio.h>
#include "pico/stdlib.h"
#include "pico/time.h"
#include "hardware/gpio.h"

#include "mlx90640/MLX90640_API.h"
#include "mlx90640/MLX90640_I2C_Driver.h"

#define MLX90640_ADDR 0x33
#define LED_PIN PICO_DEFAULT_LED_PIN

static paramsMLX90640 mlx_params;
static uint16_t mlx_frame_raw[834];
static float mlx_temps[768];

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
    printf("\n=== MLX90640 Simple Test ===\n");

    // Init I2C
    printf("Initializing I2C...\n");
    MLX90640_I2CInit();
    sleep_ms(100);

    // Read EEPROM
    printf("Reading EEPROM...\n");
    uint16_t eeData[832];
    int status = MLX90640_DumpEE(MLX90640_ADDR, eeData);
    if (status != 0) {
        printf("ERROR: DumpEE failed with code %d\n", status);
        while(1) {
            gpio_put(LED_PIN, 1);
            sleep_ms(100);
            gpio_put(LED_PIN, 0);
            sleep_ms(100);
        }
    }
    printf("EEPROM read OK\n");

    // Extract parameters
    printf("Extracting calibration parameters...\n");
    status = MLX90640_ExtractParameters(eeData, &mlx_params);
    if (status != 0) {
        printf("ERROR: ExtractParameters failed with code %d\n", status);
        while(1) { sleep_ms(1000); }
    }
    printf("Parameters extracted OK\n");

    // Set refresh rate
    printf("Setting refresh rate to 16Hz...\n");
    MLX90640_SetRefreshRate(MLX90640_ADDR, 0x05);  // 16Hz
    sleep_ms(100);

    printf("\nSensor ready! Reading frames...\n");
    printf("Format: Frame N | Time: Xms (X.X fps) | Center pixel: XX.XC\n\n");

    uint32_t frame_count = 0;

    while (1) {
        uint64_t t_start = time_us_64();

        // Read frame
        status = MLX90640_GetFrameData(MLX90640_ADDR, mlx_frame_raw);
        if (status < 0) {
            printf("Frame %lu: GetFrameData FAILED (code %d)\n", frame_count, status);
            sleep_ms(100);
            continue;
        }

        uint64_t t_read = time_us_64();

        // Calculate temperatures
        float emissivity = 0.95f;
        float tr = 23.15f;
        MLX90640_CalculateTo(mlx_frame_raw, &mlx_params, emissivity, tr, mlx_temps);

        uint64_t t_calc = time_us_64();

        // Print timing and center pixel temperature
        float frame_time_ms = (t_calc - t_start) / 1000.0f;
        float fps = 1000000.0f / (t_calc - t_start);
        float read_ms = (t_read - t_start) / 1000.0f;
        float calc_ms = (t_calc - t_read) / 1000.0f;

        // Center pixel is at (12, 16) = index 12*32+16 = 400
        float center_temp = mlx_temps[400];

        printf("Frame %lu | Time: %.1fms (%.1f fps) | Read: %.1fms | Calc: %.1fms | Center: %.1fC\n",
               frame_count, frame_time_ms, fps, read_ms, calc_ms, center_temp);

        // Every 10 frames, print a few more temps for sanity check
        if (frame_count % 10 == 0 && frame_count > 0) {
            printf("  Sample temps: [0,0]=%.1f [12,16]=%.1f [23,31]=%.1f\n",
                   mlx_temps[0], mlx_temps[400], mlx_temps[767]);
        }

        frame_count++;

        // Blink LED
        gpio_put(LED_PIN, frame_count % 2);
    }

    return 0;
}

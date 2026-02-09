/**
 * communication.c
 * Fast serial and I2C communication
 */

#include "communication.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "pico/stdlib.h"

// I2C peripheral register storage (for future I2C slave implementation)
static uint8_t i2c_registers[16];

void communication_init(void) {
    stdio_init_all();  // Initialize USB serial
    memset(i2c_registers, 0, sizeof(i2c_registers));
}

// Helper to sanitize float values (replace NaN/Inf with 0)
static inline float sanitize_float(float val) {
    if (!isfinite(val)) return 0.0f;
    return val;
}

void send_serial_compact(const FrameData *data, float fps) {
    // Compact CSV format matching visualizer expectations:
    // Frame,FPS,L_avg,L_med,C_avg,C_med,R_avg,R_med,Width,Conf,Det

    // Validate pointer first
    if (data == NULL) {
        printf("ERROR: NULL data pointer\n");
        fflush(stdout);
        return;
    }

    // Debug disabled to prevent USB buffer issues on early frames
    // if (data->frame_number <= 10) {
    //     printf("[DEBUG Frame %lu] fps=%.1f l_avg=%.1f l_med=%.1f c_avg=%.1f c_med=%.1f\n",
    //            data->frame_number,
    //            sanitize_float(fps),
    //            sanitize_float(data->left.avg),
    //            sanitize_float(data->left.median),
    //            sanitize_float(data->centre.avg),
    //            sanitize_float(data->centre.median));
    //     fflush(stdout);
    // }

    // Use safer output - format to fixed buffer first
    char buffer[128];
    int len = snprintf(buffer, sizeof(buffer),
                      "%lu,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%u,%.2f,%u\n",
                      data->frame_number,
                      sanitize_float(fps),
                      sanitize_float(data->left.avg),
                      sanitize_float(data->left.median),
                      sanitize_float(data->centre.avg),
                      sanitize_float(data->centre.median),
                      sanitize_float(data->right.avg),
                      sanitize_float(data->right.median),
                      data->detection.tyre_width,
                      sanitize_float(data->detection.confidence),
                      data->detection.detected ? 1 : 0);

    if (len > 0 && len < (int)sizeof(buffer)) {
        printf("%s", buffer);
    } else {
        printf("ERROR: Buffer overflow in send_serial_compact\n");
    }
    fflush(stdout);
}

void send_serial_json(const FrameData *data, float fps, const float *temperature_profile) {
    // Full JSON output matching visualizer expectations
    printf("{\n");
    printf("  \"frame_number\": %lu,\n", data->frame_number);
    printf("  \"fps\": %.1f,\n", sanitize_float(fps));
    printf("  \"analysis\": {\n");

    // Left zone
    printf("    \"left\": {\"avg\": %.1f, \"median\": %.1f, \"mad\": %.2f, "
           "\"min\": %.1f, \"max\": %.1f, \"range\": %.1f},\n",
           sanitize_float(data->left.avg), sanitize_float(data->left.median),
           sanitize_float(data->left.mad), sanitize_float(data->left.min),
           sanitize_float(data->left.max), sanitize_float(data->left.range));

    // Centre zone
    printf("    \"centre\": {\"avg\": %.1f, \"median\": %.1f, \"mad\": %.2f, "
           "\"min\": %.1f, \"max\": %.1f, \"range\": %.1f},\n",
           sanitize_float(data->centre.avg), sanitize_float(data->centre.median),
           sanitize_float(data->centre.mad), sanitize_float(data->centre.min),
           sanitize_float(data->centre.max), sanitize_float(data->centre.range));

    // Right zone
    printf("    \"right\": {\"avg\": %.1f, \"median\": %.1f, \"mad\": %.2f, "
           "\"min\": %.1f, \"max\": %.1f, \"range\": %.1f},\n",
           sanitize_float(data->right.avg), sanitize_float(data->right.median),
           sanitize_float(data->right.mad), sanitize_float(data->right.min),
           sanitize_float(data->right.max), sanitize_float(data->right.range));

    // Lateral gradient
    printf("    \"lateral_gradient\": %.1f\n", sanitize_float(data->lateral_gradient));

    printf("  },\n");
    printf("  \"detection\": {\n");
    printf("    \"detected\": %u,\n", data->detection.detected ? 1 : 0);
    printf("    \"span_start\": %u,\n", data->detection.span_start);
    printf("    \"span_end\": %u,\n", data->detection.span_end);
    printf("    \"tyre_width\": %u,\n", data->detection.tyre_width);
    printf("    \"confidence\": %.2f\n", sanitize_float(data->detection.confidence));
    printf("  },\n");

    // Temperature profile (average of 24 rows into single 32-pixel row)
    if (temperature_profile != NULL) {
        printf("  \"temperature_profile\": [");
        for (int i = 0; i < 32; i++) {
            printf("%.1f", sanitize_float(temperature_profile[i]));
            if (i < 31) printf(", ");
        }
        printf("],\n");
    } else {
        printf("  \"temperature_profile\": [],\n");
    }

    printf("  \"warnings\": []\n");
    printf("}\n");
    fflush(stdout);
}

void update_i2c_registers(const FrameData *data) {
    // Pack data into I2C registers (int16 tenths of degree C)
    // Register map (same as CircuitPython version):
    // 0x00-0x01: Left temp (int16, tenths)
    // 0x02-0x03: Centre temp (int16, tenths)
    // 0x04-0x05: Right temp (int16, tenths)
    // 0x06: Confidence (uint8, 0-100%)
    // 0x07: Warnings
    // 0x08: Span start
    // 0x09: Span end
    // 0x0A: Tyre width
    // 0x0B-0x0C: Lateral gradient (int16, tenths)
    // 0x0D-0x0E: Frame counter (uint16)

    int16_t left_temp = (int16_t)(data->left.avg * 10.0f);
    int16_t centre_temp = (int16_t)(data->centre.avg * 10.0f);
    int16_t right_temp = (int16_t)(data->right.avg * 10.0f);
    int16_t lat_grad = (int16_t)(data->lateral_gradient * 10.0f);
    uint8_t confidence = (uint8_t)(data->detection.confidence * 100.0f);
    uint16_t frame = (uint16_t)(data->frame_number & 0xFFFF);

    // Pack into registers (big-endian)
    i2c_registers[0x00] = (left_temp >> 8) & 0xFF;
    i2c_registers[0x01] = left_temp & 0xFF;
    i2c_registers[0x02] = (centre_temp >> 8) & 0xFF;
    i2c_registers[0x03] = centre_temp & 0xFF;
    i2c_registers[0x04] = (right_temp >> 8) & 0xFF;
    i2c_registers[0x05] = right_temp & 0xFF;
    i2c_registers[0x06] = confidence;
    i2c_registers[0x07] = data->warnings;
    i2c_registers[0x08] = data->detection.span_start;
    i2c_registers[0x09] = data->detection.span_end;
    i2c_registers[0x0A] = data->detection.tyre_width;
    i2c_registers[0x0B] = (lat_grad >> 8) & 0xFF;
    i2c_registers[0x0C] = lat_grad & 0xFF;
    i2c_registers[0x0D] = (frame >> 8) & 0xFF;
    i2c_registers[0x0E] = frame & 0xFF;

    // TODO: Implement I2C peripheral/slave mode on second I2C channel
    // For now, registers are just stored in memory
}

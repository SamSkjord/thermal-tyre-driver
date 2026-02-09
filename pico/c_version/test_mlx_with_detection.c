/**
 * test_mlx_with_detection.c - MLX90640 with MAD-based tyre detection
 * Full port of CircuitPython algorithm with temporal smoothing and constraints
 */

#include <stdio.h>
#include <string.h>
#include <math.h>
#include "pico/stdlib.h"
#include "pico/time.h"
#include "hardware/gpio.h"

#include "mlx90640/MLX90640_API.h"
#include "mlx90640/MLX90640_I2C_Driver.h"

#define MLX90640_ADDR 0x33
#define LED_PIN PICO_DEFAULT_LED_PIN
#define SENSOR_WIDTH 32
#define SENSOR_HEIGHT 24
#define MIDDLE_ROWS 4
#define START_ROW 10

// Configuration parameters (from CircuitPython)
typedef struct {
    float min_temp;
    float max_temp;
    float brake_temp_threshold;
    float mad_uniform_threshold;
    float k_floor;
    float k_multiplier;
    float delta_floor;
    float delta_multiplier;
    int max_fail_count;
    int centre_col;
    int min_tyre_width;
    int max_tyre_width;
    float max_width_change_ratio;
    float ema_alpha;
    int persistence_frames;
} DetectionConfig;

static const DetectionConfig config = {
    .min_temp = 0.0f,
    .max_temp = 180.0f,
    .brake_temp_threshold = 180.0f,
    .mad_uniform_threshold = 0.5f,
    .k_floor = 5.0f,
    .k_multiplier = 2.0f,
    .delta_floor = 3.0f,
    .delta_multiplier = 1.8f,
    .max_fail_count = 2,
    .centre_col = 16,
    .min_tyre_width = 6,
    .max_tyre_width = 28,
    .max_width_change_ratio = 0.3f,
    .ema_alpha = 0.3f,
    .persistence_frames = 2
};

// Zone statistics
typedef struct {
    float avg;
    float median;
    float mad;
    float min;
    float max;
    float range;
    float std;
} ZoneStats;

// Complete tyre data
typedef struct {
    ZoneStats left;
    ZoneStats centre;
    ZoneStats right;
    int detected;
    int span_start;
    int span_end;
    int tyre_width;
    float confidence;
    float lateral_gradient;
} TyreData;

// Temporal state
typedef struct {
    float prev_profile[SENSOR_WIDTH];
    int prev_detections[2][2];  // [frame][left, right]
    int prev_detection_count;
    int has_previous;
} TemporalState;

static paramsMLX90640 mlx_params;
static uint16_t mlx_frame_raw[834];
static float mlx_temps[768];
static TemporalState temporal_state = {0};

// Utility: Swap for sorting
static void swap_float(float *a, float *b) {
    float temp = *a;
    *a = *b;
    *b = temp;
}

// Quick select for median (in-place partition)
static float quick_select_median(float *arr, int n) {
    if (n == 0) return 0.0f;
    if (n == 1) return arr[0];

    // Simple sorting for small arrays
    for (int i = 0; i < n - 1; i++) {
        for (int j = i + 1; j < n; j++) {
            if (arr[i] > arr[j]) {
                swap_float(&arr[i], &arr[j]);
            }
        }
    }

    if (n % 2 == 0) {
        return (arr[n/2 - 1] + arr[n/2]) / 2.0f;
    } else {
        return arr[n/2];
    }
}

// Calculate median (non-destructive)
static float calculate_median(const float *data, int n) {
    float temp[SENSOR_WIDTH * MIDDLE_ROWS];
    if (n > SENSOR_WIDTH * MIDDLE_ROWS) n = SENSOR_WIDTH * MIDDLE_ROWS;

    memcpy(temp, data, n * sizeof(float));
    return quick_select_median(temp, n);
}

// Calculate MAD (Median Absolute Deviation)
static float calculate_mad(const float *data, int n) {
    if (n == 0) return 0.0f;

    float median = calculate_median(data, n);

    // Calculate absolute deviations
    float deviations[SENSOR_WIDTH * MIDDLE_ROWS];
    if (n > SENSOR_WIDTH * MIDDLE_ROWS) n = SENSOR_WIDTH * MIDDLE_ROWS;

    for (int i = 0; i < n; i++) {
        deviations[i] = fabsf(data[i] - median);
    }

    float mad = calculate_median(deviations, n);
    return mad * 1.4826f;  // Scale factor for consistency with std dev
}

// Calculate standard deviation
static float calculate_std(const float *data, int n) {
    if (n == 0) return 0.0f;

    float sum = 0.0f;
    for (int i = 0; i < n; i++) {
        sum += data[i];
    }
    float mean = sum / n;

    float sq_sum = 0.0f;
    for (int i = 0; i < n; i++) {
        float diff = data[i] - mean;
        sq_sum += diff * diff;
    }

    return sqrtf(sq_sum / n);
}

// Hot pixel removal (replace >180C with neighbor median)
static void remove_hot_pixels(float *row, int width) {
    for (int i = 0; i < width; i++) {
        if (row[i] > config.brake_temp_threshold) {
            // Get neighbors
            float neighbors[2];
            int count = 0;

            if (i > 0) neighbors[count++] = row[i-1];
            if (i < width - 1) neighbors[count++] = row[i+1];

            if (count > 0) {
                row[i] = calculate_median(neighbors, count);
            }
        }
    }
}

// 3-element median filter
static void median_filter_3(const float *input, float *output, int n) {
    for (int i = 0; i < n; i++) {
        if (i == 0) {
            // Left edge
            float vals[2] = {input[0], input[1]};
            output[i] = calculate_median(vals, 2);
        } else if (i == n - 1) {
            // Right edge
            float vals[2] = {input[n-2], input[n-1]};
            output[i] = calculate_median(vals, 2);
        } else {
            // Middle
            float vals[3] = {input[i-1], input[i], input[i+1]};
            output[i] = calculate_median(vals, 3);
        }
    }
}

// EMA temporal smoothing
static void apply_ema(const float *current, float *output, int n) {
    if (!temporal_state.has_previous) {
        memcpy(output, current, n * sizeof(float));
        memcpy(temporal_state.prev_profile, current, n * sizeof(float));
        temporal_state.has_previous = 1;
    } else {
        for (int i = 0; i < n; i++) {
            output[i] = config.ema_alpha * current[i] +
                       (1.0f - config.ema_alpha) * temporal_state.prev_profile[i];
            temporal_state.prev_profile[i] = output[i];
        }
    }
}

// Grow region from centre using dual criteria
static void grow_region(const float *profile, float median_temp, float mad_global,
                       int *left_out, int *right_out) {
    int centre = config.centre_col;
    float centre_temp = profile[centre];

    // Calculate dynamic threshold
    float delta = fmaxf(config.delta_floor, config.delta_multiplier * mad_global);

    // Detect inversion (cold tyre on hot ground)
    int inverted = (centre_temp < median_temp - delta);

    // Calculate local MAD around centre
    int local_start = (centre - 2 >= 0) ? centre - 2 : 0;
    int local_end = (centre + 2 < SENSOR_WIDTH) ? centre + 2 : SENSOR_WIDTH - 1;
    int local_n = local_end - local_start + 1;
    float local_mad = calculate_mad(&profile[local_start], local_n);

    float k = fmaxf(config.k_floor, config.k_multiplier * local_mad);

    // Grow left
    int left = centre;
    int fail_count = 0;
    for (int i = centre - 1; i >= 0; i--) {
        float temp = profile[i];

        // Dual criteria
        int within_k = fabsf(temp - centre_temp) <= k;
        int global_ok;
        if (inverted) {
            global_ok = (temp <= median_temp - delta);
        } else {
            global_ok = (temp >= median_temp + delta);
        }

        if (within_k || global_ok) {
            left = i;
            fail_count = 0;
        } else {
            fail_count++;
            if (fail_count > config.max_fail_count) break;
        }
    }

    // Grow right
    int right = centre;
    fail_count = 0;
    for (int i = centre + 1; i < SENSOR_WIDTH; i++) {
        float temp = profile[i];

        int within_k = fabsf(temp - centre_temp) <= k;
        int global_ok;
        if (inverted) {
            global_ok = (temp <= median_temp - delta);
        } else {
            global_ok = (temp >= median_temp + delta);
        }

        if (within_k || global_ok) {
            right = i;
            fail_count = 0;
        } else {
            fail_count++;
            if (fail_count > config.max_fail_count) break;
        }
    }

    *left_out = left;
    *right_out = right;
}

// Apply geometry constraints
static void apply_geometry_constraints(int *left, int *right) {
    int width = *right - *left + 1;

    // Minimum width
    if (width < config.min_tyre_width) {
        int expand = (config.min_tyre_width - width) / 2;
        *left -= expand;
        *right += expand;

        // Clamp to valid range
        if (*left < 0) {
            *right += (-*left);
            *left = 0;
        }
        if (*right >= SENSOR_WIDTH) {
            *left -= (*right - SENSOR_WIDTH + 1);
            *right = SENSOR_WIDTH - 1;
        }
    }

    // Maximum width
    if (width > config.max_tyre_width) {
        int shrink = (width - config.max_tyre_width) / 2;
        *left += shrink;
        *right -= shrink;
    }

    // Clamp to valid range
    if (*left < 0) *left = 0;
    if (*right >= SENSOR_WIDTH) *right = SENSOR_WIDTH - 1;
}

// Apply temporal constraints
static void apply_temporal_constraints(int *left, int *right) {
    if (temporal_state.prev_detection_count == 0) return;

    // Get previous width
    int prev_left = temporal_state.prev_detections[0][0];
    int prev_right = temporal_state.prev_detections[0][1];
    int prev_width = prev_right - prev_left + 1;
    int current_width = *right - *left + 1;

    float max_change = prev_width * config.max_width_change_ratio;

    // Width increased too much
    if (current_width > prev_width + max_change) {
        int target_width = prev_width + max_change;
        int shrink = (current_width - target_width) / 2;
        *left += shrink;
        *right -= shrink;
    }

    // Width decreased too much
    if (current_width < prev_width - max_change) {
        int target_width = prev_width - max_change;
        int expand = (target_width - current_width) / 2;
        *left -= expand;
        *right += expand;
    }

    // Clamp
    if (*left < 0) *left = 0;
    if (*right >= SENSOR_WIDTH) *right = SENSOR_WIDTH - 1;
}

// Persistence smoothing (quadratic weighted average)
static void apply_persistence(int *left, int *right) {
    if (temporal_state.prev_detection_count < config.persistence_frames) {
        // Not enough history, just store current
        if (temporal_state.prev_detection_count < 2) {
            temporal_state.prev_detections[temporal_state.prev_detection_count][0] = *left;
            temporal_state.prev_detections[temporal_state.prev_detection_count][1] = *right;
            temporal_state.prev_detection_count++;
        } else {
            // Shift buffer
            temporal_state.prev_detections[0][0] = temporal_state.prev_detections[1][0];
            temporal_state.prev_detections[0][1] = temporal_state.prev_detections[1][1];
            temporal_state.prev_detections[1][0] = *left;
            temporal_state.prev_detections[1][1] = *right;
        }
        return;
    }

    // Calculate quadratic weighted average
    float weighted_left = 0.0f;
    float weighted_right = 0.0f;
    float total_weight = 0.0f;

    for (int i = 0; i < config.persistence_frames; i++) {
        float weight = (i + 1) * (i + 1);  // Quadratic
        weighted_left += temporal_state.prev_detections[i][0] * weight;
        weighted_right += temporal_state.prev_detections[i][1] * weight;
        total_weight += weight;
    }

    // Add current with highest weight
    float current_weight = (config.persistence_frames + 1) * (config.persistence_frames + 1);
    weighted_left += (*left) * current_weight;
    weighted_right += (*right) * current_weight;
    total_weight += current_weight;

    *left = (int)(weighted_left / total_weight);
    *right = (int)(weighted_right / total_weight);

    // Update buffer
    temporal_state.prev_detections[0][0] = temporal_state.prev_detections[1][0];
    temporal_state.prev_detections[0][1] = temporal_state.prev_detections[1][1];
    temporal_state.prev_detections[1][0] = *left;
    temporal_state.prev_detections[1][1] = *right;
}

// Calculate zone statistics from 2D middle rows
static void calculate_zone_stats(const float *frame, int left, int right, ZoneStats *stats) {
    // Collect all pixels from middle rows in this zone
    float pixels[SENSOR_WIDTH * MIDDLE_ROWS];
    int count = 0;

    for (int row = START_ROW; row < START_ROW + MIDDLE_ROWS; row++) {
        for (int col = left; col <= right && col < SENSOR_WIDTH; col++) {
            pixels[count++] = frame[row * SENSOR_WIDTH + col];
        }
    }

    if (count == 0) {
        memset(stats, 0, sizeof(ZoneStats));
        return;
    }

    // Calculate statistics
    float sum = 0.0f;
    float min_val = pixels[0];
    float max_val = pixels[0];

    for (int i = 0; i < count; i++) {
        sum += pixels[i];
        if (pixels[i] < min_val) min_val = pixels[i];
        if (pixels[i] > max_val) max_val = pixels[i];
    }

    stats->avg = sum / count;
    stats->median = calculate_median(pixels, count);
    stats->mad = calculate_mad(pixels, count);
    stats->min = min_val;
    stats->max = max_val;
    stats->range = max_val - min_val;
    stats->std = calculate_std(pixels, count);
}

// Analyze tyre sections
static void analyze_tyre(const float *frame, const float *profile,
                        int left, int right, TyreData *result) {
    result->detected = 1;
    result->span_start = left;
    result->span_end = right;
    result->tyre_width = right - left + 1;

    // Split into thirds
    int third = result->tyre_width / 3;

    int left_start = left;
    int left_end = left + third - 1;
    if (left_end < left_start) left_end = left_start;

    int centre_start = left + third;
    int centre_end = right - third;
    if (centre_end < centre_start) centre_end = centre_start;

    int right_start = right - third + 1;
    int right_end = right;
    if (right_start > right_end) right_start = right_end;

    // Calculate zone statistics
    calculate_zone_stats(frame, left_start, left_end, &result->left);
    calculate_zone_stats(frame, centre_start, centre_end, &result->centre);
    calculate_zone_stats(frame, right_start, right_end, &result->right);

    // Lateral gradient (max - min of column averages across tyre)
    float min_col_avg = profile[left];
    float max_col_avg = profile[left];
    for (int i = left + 1; i <= right; i++) {
        if (profile[i] < min_col_avg) min_col_avg = profile[i];
        if (profile[i] > max_col_avg) max_col_avg = profile[i];
    }
    result->lateral_gradient = max_col_avg - min_col_avg;

    // Simple confidence based on width and gradient
    float width_score = (result->tyre_width >= config.min_tyre_width &&
                        result->tyre_width <= config.max_tyre_width) ? 1.0f : 0.5f;
    float gradient_score = fminf(result->lateral_gradient / 10.0f, 1.0f);
    result->confidence = (width_score + gradient_score) / 2.0f;
}

// Main detection pipeline
static int detect_tyre(const float *frame, TyreData *result) {
    float middle_rows[MIDDLE_ROWS][SENSOR_WIDTH];
    float profile[SENSOR_WIDTH];
    float filtered[SENSOR_WIDTH];
    float smoothed[SENSOR_WIDTH];

    // Extract middle rows
    for (int row = 0; row < MIDDLE_ROWS; row++) {
        int src_row = START_ROW + row;
        memcpy(middle_rows[row], &frame[src_row * SENSOR_WIDTH],
               SENSOR_WIDTH * sizeof(float));

        // Remove hot pixels
        remove_hot_pixels(middle_rows[row], SENSOR_WIDTH);
    }

    // Create 1D profile (median of each column)
    for (int col = 0; col < SENSOR_WIDTH; col++) {
        float col_vals[MIDDLE_ROWS];
        for (int row = 0; row < MIDDLE_ROWS; row++) {
            col_vals[row] = middle_rows[row][col];
        }
        profile[col] = calculate_median(col_vals, MIDDLE_ROWS);

        // Clip to valid range
        if (profile[col] < config.min_temp) profile[col] = config.min_temp;
        if (profile[col] > config.max_temp) profile[col] = config.max_temp;
    }

    // Spatial filtering
    median_filter_3(profile, filtered, SENSOR_WIDTH);

    // Temporal smoothing (EMA)
    apply_ema(filtered, smoothed, SENSOR_WIDTH);

    // Calculate global statistics
    float median_temp = calculate_median(smoothed, SENSOR_WIDTH);
    float mad_global = calculate_mad(smoothed, SENSOR_WIDTH);

    // Check if too uniform
    if (mad_global < config.mad_uniform_threshold) {
        result->detected = 0;

        // Still report temperatures even when no tyre detected
        // Use full sensor width divided into thirds
        int third = SENSOR_WIDTH / 3;
        calculate_zone_stats(frame, 0, third - 1, &result->left);
        calculate_zone_stats(frame, third, 2 * third - 1, &result->centre);
        calculate_zone_stats(frame, 2 * third, SENSOR_WIDTH - 1, &result->right);

        result->tyre_width = 0;
        result->confidence = 0.0f;
        result->lateral_gradient = 0.0f;

        return 0;
    }

    // Grow region from centre
    int left, right;
    grow_region(smoothed, median_temp, mad_global, &left, &right);

    // Apply constraints
    apply_geometry_constraints(&left, &right);
    apply_temporal_constraints(&left, &right);
    apply_persistence(&left, &right);

    // Analyze tyre zones
    analyze_tyre(frame, smoothed, left, right, result);

    return 1;
}

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
    printf("\n=== MLX90640 with MAD-based Tyre Detection ===\n");

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
    MLX90640_SetRefreshRate(MLX90640_ADDR, 0x05);
    sleep_ms(100);

    printf("\nSensor ready! Detecting tyres with MAD algorithm...\n");
    printf("CSV: Frame,FPS,L_avg,L_med,C_avg,C_med,R_avg,R_med,Width,Conf,Det\n\n");

    uint32_t frame_count = 0;
    TyreData tyre;

    while (1) {
        uint64_t t_start = time_us_64();

        // Read frame
        status = MLX90640_GetFrameData(MLX90640_ADDR, mlx_frame_raw);
        if (status < 0) {
            printf("Frame %lu: GetFrameData FAILED (code %d)\n", frame_count, status);
            sleep_ms(100);
            continue;
        }

        // Calculate temperatures
        float emissivity = 0.95f;
        float tr = 23.15f;
        MLX90640_CalculateTo(mlx_frame_raw, &mlx_params, emissivity, tr, mlx_temps);

        // Detect tyre
        memset(&tyre, 0, sizeof(TyreData));
        detect_tyre(mlx_temps, &tyre);

        uint64_t t_end = time_us_64();

        // Calculate FPS
        float fps = 1000000.0f / (t_end - t_start);

        // Output CSV
        printf("%lu,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%d,%.2f,%d\n",
               frame_count,
               fps,
               tyre.left.avg,
               tyre.left.median,
               tyre.centre.avg,
               tyre.centre.median,
               tyre.right.avg,
               tyre.right.median,
               tyre.tyre_width,
               tyre.confidence,
               tyre.detected);

        frame_count++;

        // Blink LED
        gpio_put(LED_PIN, frame_count % 2);
    }

    return 0;
}

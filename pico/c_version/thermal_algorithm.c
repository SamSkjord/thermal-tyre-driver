/**
 * thermal_algorithm.c
 * Optimized thermal tyre detection algorithm in C
 */

#include "thermal_algorithm.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

// Static frame counter
static uint32_t frame_counter = 0;

// Comparison function for qsort
static int compare_floats(const void *a, const void *b) {
    float fa = *(const float*)a;
    float fb = *(const float*)b;
    return (fa > fb) - (fa < fb);
}

void thermal_algorithm_init(ThermalConfig *config) {
    config->mad_threshold = 3.0f;
    config->grad_threshold = 5.0f;
    config->min_tyre_width = 6;
    config->max_tyre_width = 28;
    config->ema_alpha = 0.3f;
    frame_counter = 0;
}

float fast_mean(const float *data, uint16_t len) {
    if (len == 0) return 0.0f;

    float sum = 0.0f;
    for (uint16_t i = 0; i < len; i++) {
        sum += data[i];
    }
    return sum / (float)len;
}

float fast_median(float *data, uint16_t len) {
    if (len == 0) return 0.0f;
    if (len == 1) return data[0];

    // Use qsort for simplicity - on Pico this is fast enough
    qsort(data, len, sizeof(float), compare_floats);

    if (len % 2 == 0) {
        return (data[len/2 - 1] + data[len/2]) / 2.0f;
    } else {
        return data[len/2];
    }
}

float fast_mad(const float *data, uint16_t len, float median) {
    if (len < 2) return 0.0f;

    // Use static buffer instead of malloc to avoid heap issues
    static float deviations[SENSOR_WIDTH];
    if (len > SENSOR_WIDTH) return 0.0f;

    for (uint16_t i = 0; i < len; i++) {
        deviations[i] = fabsf(data[i] - median);
    }

    float mad = fast_median(deviations, len);

    return mad * 1.4826f;  // Scale factor for consistency with std dev
}

// Extract middle rows from 24x32 sensor
static void extract_middle_rows(const float *frame, float *profile) {
    // Extract rows 10-13 (middle 4 rows) and average them
    for (int col = 0; col < SENSOR_WIDTH; col++) {
        float sum = 0.0f;
        int count = 0;

        for (int row = 10; row <= 13; row++) {
            int idx = row * SENSOR_WIDTH + col;
            if (frame[idx] > -270.0f) {  // Valid temperature
                sum += frame[idx];
                count++;
            }
        }

        profile[col] = (count > 0) ? (sum / count) : 0.0f;
    }
}

// Simple region growing to find tyre span
static void detect_tyre_span(const float *profile, TyreDetection *detection, ThermalConfig *config) {
    // Calculate profile statistics
    float profile_median = 0.0f;
    float profile_mad = 0.0f;

    // Use static buffer instead of malloc
    static float temp_profile[SENSOR_WIDTH];
    memcpy(temp_profile, profile, SENSOR_WIDTH * sizeof(float));
    profile_median = fast_median(temp_profile, SENSOR_WIDTH);
    profile_mad = fast_mad(profile, SENSOR_WIDTH, profile_median);

    // Find hottest pixel as seed
    float max_temp = -300.0f;
    int seed_idx = SENSOR_WIDTH / 2;  // Default to center

    for (int i = 0; i < SENSOR_WIDTH; i++) {
        if (profile[i] > max_temp) {
            max_temp = profile[i];
            seed_idx = i;
        }
    }

    // Grow region from seed
    float threshold = profile_median + (config->mad_threshold * profile_mad);

    int start = seed_idx;
    int end = seed_idx;

    // Grow left
    for (int i = seed_idx - 1; i >= 0; i--) {
        if (profile[i] > threshold) {
            start = i;
        } else {
            break;
        }
    }

    // Grow right
    for (int i = seed_idx + 1; i < SENSOR_WIDTH; i++) {
        if (profile[i] > threshold) {
            end = i;
        } else {
            break;
        }
    }

    int width = end - start + 1;

    // Validate detection
    detection->detected = (width >= config->min_tyre_width &&
                          width <= config->max_tyre_width &&
                          profile_mad > 0.5f);

    if (detection->detected) {
        detection->span_start = start;
        detection->span_end = end;
        detection->tyre_width = width;

        // Calculate confidence based on MAD and width
        float width_score = (width >= 8 && width <= 24) ? 1.0f : 0.7f;
        float mad_score = fminf(profile_mad / 3.0f, 1.0f);
        detection->confidence = width_score * mad_score;
    } else {
        detection->span_start = 0;
        detection->span_end = SENSOR_WIDTH - 1;
        detection->tyre_width = SENSOR_WIDTH;
        detection->confidence = 0.0f;
    }
}

// Analyze a zone (left/center/right)
static void analyze_zone(const float *profile, int start, int end, ZoneAnalysis *result) {
    if (start < 0) start = 0;
    if (end >= SENSOR_WIDTH) end = SENSOR_WIDTH - 1;

    int len = end - start + 1;
    if (len <= 0 || len > SENSOR_WIDTH) {
        memset(result, 0, sizeof(ZoneAnalysis));
        return;
    }

    // Use static buffer instead of malloc
    static float zone_data[SENSOR_WIDTH];

    for (int i = 0; i < len; i++) {
        zone_data[i] = profile[start + i];
    }

    // Calculate statistics
    result->count = len;
    result->avg = fast_mean(zone_data, len);
    result->median = fast_median(zone_data, len);
    result->mad = fast_mad(zone_data, len, result->median);

    // Find min/max
    result->min = zone_data[0];
    result->max = zone_data[0];
    for (int i = 1; i < len; i++) {
        if (zone_data[i] < result->min) result->min = zone_data[i];
        if (zone_data[i] > result->max) result->max = zone_data[i];
    }
    result->range = result->max - result->min;
}

void thermal_algorithm_process(const float *frame, FrameData *result, ThermalConfig *config) {
    frame_counter++;
    result->frame_number = frame_counter;
    result->warnings = 0;

    // Extract horizontal profile from middle rows
    float profile[SENSOR_WIDTH];
    extract_middle_rows(frame, profile);

    // Detect tyre span
    detect_tyre_span(profile, &result->detection, config);

    // Split tyre into three zones
    if (result->detection.detected) {
        int tyre_start = result->detection.span_start;
        int tyre_end = result->detection.span_end;
        int tyre_width = result->detection.tyre_width;

        int third = tyre_width / 3;

        int left_start = tyre_start;
        int left_end = tyre_start + third - 1;

        int centre_start = left_end + 1;
        int centre_end = tyre_end - third;

        int right_start = centre_end + 1;
        int right_end = tyre_end;

        analyze_zone(profile, left_start, left_end, &result->left);
        analyze_zone(profile, centre_start, centre_end, &result->centre);
        analyze_zone(profile, right_start, right_end, &result->right);

        // Calculate lateral gradient (left to right)
        result->lateral_gradient = result->right.avg - result->left.avg;

        // Check for warnings
        if (fabsf(result->lateral_gradient) > 10.0f) {
            result->warnings |= 0x01;  // High gradient warning
        }

        if (result->centre.max - result->centre.min > 20.0f) {
            result->warnings |= 0x02;  // High variance warning
        }
    } else {
        // No tyre detected - analyze full profile
        analyze_zone(profile, 0, SENSOR_WIDTH - 1, &result->centre);
        memset(&result->left, 0, sizeof(ZoneAnalysis));
        memset(&result->right, 0, sizeof(ZoneAnalysis));
        result->lateral_gradient = 0.0f;
    }
}

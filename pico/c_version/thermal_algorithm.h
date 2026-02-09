/**
 * thermal_algorithm.h
 * Fast thermal tyre detection algorithm
 */

#ifndef THERMAL_ALGORITHM_H
#define THERMAL_ALGORITHM_H

#include <stdint.h>
#include <stdbool.h>

#define SENSOR_WIDTH 32
#define SENSOR_HEIGHT 24
#define SENSOR_PIXELS 768

// Configuration
typedef struct {
    float mad_threshold;
    float grad_threshold;
    uint8_t min_tyre_width;
    uint8_t max_tyre_width;
    float ema_alpha;
} ThermalConfig;

// Detection result
typedef struct {
    uint8_t span_start;
    uint8_t span_end;
    uint8_t tyre_width;
    float confidence;
    bool detected;
} TyreDetection;

// Analysis result for each zone
typedef struct {
    float avg;
    float median;
    float mad;
    float min;
    float max;
    float range;
    uint16_t count;
} ZoneAnalysis;

// Complete frame analysis
typedef struct {
    uint32_t frame_number;
    ZoneAnalysis left;
    ZoneAnalysis centre;
    ZoneAnalysis right;
    TyreDetection detection;
    float lateral_gradient;
    uint8_t warnings;
} FrameData;

// Initialize algorithm with default config
void thermal_algorithm_init(ThermalConfig *config);

// Process a frame and extract tyre data
void thermal_algorithm_process(const float *frame, FrameData *result, ThermalConfig *config);

// Fast median calculation (destructive to input array)
float fast_median(float *data, uint16_t len);

// Fast MAD calculation
float fast_mad(const float *data, uint16_t len, float median);

// Fast mean calculation
float fast_mean(const float *data, uint16_t len);

#endif // THERMAL_ALGORITHM_H

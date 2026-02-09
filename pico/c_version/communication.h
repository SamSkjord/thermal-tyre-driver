/**
 * communication.h
 * Serial and I2C peripheral communication
 */

#ifndef COMMUNICATION_H
#define COMMUNICATION_H

#include "thermal_algorithm.h"
#include <stdint.h>
#include <stdbool.h>

// Initialize communication (serial + I2C peripheral)
void communication_init(void);

// Send frame data over serial (compact CSV format)
// CSV format: Frame,FPS,L_avg,L_med,C_avg,C_med,R_avg,R_med,Width,Conf,Det
void send_serial_compact(const FrameData *data, float fps);

// Send frame data over serial (full JSON format)
void send_serial_json(const FrameData *data, float fps, const float *temperature_profile);

// Update I2C peripheral registers with latest data
void update_i2c_registers(const FrameData *data);

#endif // COMMUNICATION_H

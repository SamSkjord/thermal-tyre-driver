cmake_minimum_required(VERSION 3.13)

# Include Pico SDK
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(thermal_tyre_pico C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# Initialize the Pico SDK
pico_sdk_init()

# Add MLX90640 driver library
add_library(mlx90640_driver STATIC
    mlx90640/MLX90640_API.c
    mlx90640/MLX90640_I2C_Driver.c
)

target_include_directories(mlx90640_driver PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/mlx90640
)

target_link_libraries(mlx90640_driver
    pico_stdlib
    hardware_i2c
)

# Main thermal tyre application
add_executable(thermal_tyre_pico
    main.c
    thermal_algorithm.c
    communication.c
    i2c_slave.c
)

target_link_libraries(thermal_tyre_pico
    mlx90640_driver
    pico_stdlib
    hardware_i2c
    hardware_irq
    hardware_uart
    pico_multicore
)

# Enable USB output, disable UART
pico_enable_stdio_usb(thermal_tyre_pico 1)
pico_enable_stdio_uart(thermal_tyre_pico 0)

# Create map/bin/hex/uf2 files
pico_add_extra_outputs(thermal_tyre_pico)

# Optimization flags for speed
target_compile_options(thermal_tyre_pico PRIVATE
    -O3
    -ffast-math
    -funroll-loops
)

target_compile_options(mlx90640_driver PRIVATE
    -O3
    -ffast-math
    -funroll-loops
)

# Minimal test executable
add_executable(test_minimal
    test_minimal.c
)

target_link_libraries(test_minimal
    pico_stdlib
    hardware_gpio
)

pico_enable_stdio_usb(test_minimal 1)
pico_enable_stdio_uart(test_minimal 0)
pico_add_extra_outputs(test_minimal)

# I2C scanner test
add_executable(test_i2c_scan
    test_i2c_scan.c
)

target_link_libraries(test_i2c_scan
    pico_stdlib
    hardware_i2c
    hardware_gpio
)

pico_enable_stdio_usb(test_i2c_scan 1)
pico_enable_stdio_uart(test_i2c_scan 0)
pico_add_extra_outputs(test_i2c_scan)

# Simple MLX90640 test
add_executable(test_mlx_simple
    test_mlx_simple.c
)

target_link_libraries(test_mlx_simple
    mlx90640_driver
    pico_stdlib
    hardware_i2c
    hardware_gpio
)

pico_enable_stdio_usb(test_mlx_simple 1)
pico_enable_stdio_uart(test_mlx_simple 0)
pico_add_extra_outputs(test_mlx_simple)

# MLX90640 with tyre detection test
add_executable(test_mlx_with_detection
    test_mlx_with_detection.c
)

target_link_libraries(test_mlx_with_detection
    mlx90640_driver
    pico_stdlib
    hardware_i2c
    hardware_gpio
)

pico_enable_stdio_usb(test_mlx_with_detection 1)
pico_enable_stdio_uart(test_mlx_with_detection 0)
pico_add_extra_outputs(test_mlx_with_detection)

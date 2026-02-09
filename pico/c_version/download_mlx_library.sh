#!/bin/bash
# Download official Melexis MLX90640 C library

echo "Downloading official MLX90640 C library..."

mkdir -p mlx90640

# Download API files
curl -o mlx90640/MLX90640_API.c https://raw.githubusercontent.com/melexis/mlx90640-library/master/functions/MLX90640_API.c
curl -o mlx90640/MLX90640_API.h https://raw.githubusercontent.com/melexis/mlx90640-library/master/headers/MLX90640_API.h

echo "✓ Downloaded MLX90640 library files"
echo ""
echo "Files downloaded:"
ls -lh mlx90640/

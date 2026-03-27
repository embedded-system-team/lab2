#!/bin/bash

set -e

echo "========================================"
echo "  Step 1: Building project...           "
echo "========================================"
make -j$(nproc)

echo ""
echo "========================================"
echo "  Step 2: Flashing STM32L475...         "
echo "========================================"
openocd -f interface/stlink.cfg -f target/stm32l4x.cfg -c "program build/lab2.hex verify reset exit"

echo ""
echo "========================================"
echo "  Step 3: Starting Visualization...     "
echo "========================================"
python3 visualize_imu.py

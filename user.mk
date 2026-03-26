#######################################
# User defined sources and includes
#######################################

# Wi-Fi Driver Sources
USER_C_SOURCES = \
Drivers/BSP/Components/es_wifi/es_wifi.c \
Drivers/BSP/Components/es_wifi/es_wifi_io.c \
Drivers/BSP/B-L475E-IOT01A1/wifi.c

# Wi-Fi Driver Includes
USER_C_INCLUDES = \
-IDrivers/BSP/Components/es_wifi

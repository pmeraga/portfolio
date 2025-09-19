#include "uart_cmd.h"
#include "balance.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/uart.h"
#include <string.h>

void uart_cmd_init() {
    const uart_config_t uart_config = {
        .baud_rate = 115200,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE
    };
    uart_driver_install(UART_NUM_0, 1024, 0, 0, NULL, 0);
    uart_param_config(UART_NUM_0, &uart_config);
}

void uart_cmd_task(void* pvParameters) {
    uint8_t data[128];
    while (1) {
        int len = uart_read_bytes(UART_NUM_0, data, sizeof(data) - 1, pdMS_TO_TICKS(100));
        if (len > 0) {
            data[len] = '\0';
            if (strstr((char*)data, "b1")) balance_active = true;
            if (strstr((char*)data, "b0")) balance_active = false;
            if (strstr((char*)data, "w")) drive_command = 'w';
            if (strstr((char*)data, "a")) drive_command = 'a';
            if (strstr((char*)data, "s")) drive_command = 's';
            if (strstr((char*)data, "d")) drive_command = 'd';
        }
    }
}

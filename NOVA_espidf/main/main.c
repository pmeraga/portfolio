#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/i2c.h"
#include "pid.h"
#include "imu.h"
#include "motor.h"
#include "balance.h"
#include "uart_cmd.h"

void app_main() {
    init_imu();
    init_motors();
    uart_cmd_init();
    balance_init();

    xTaskCreate(imu_task, "imu_task", 4096, NULL, 5, NULL);
    xTaskCreate(control_task, "control_task", 4096, NULL, 6, NULL);
    xTaskCreate(motor_task, "motor_task", 4096, NULL, 5, NULL);
    xTaskCreate(uart_cmd_task, "uart_cmd_task", 4096, NULL, 4, NULL);
}
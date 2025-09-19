#include "balance.h"
#include "pid.h"
#include "imu.h"
#include "motor.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

PIDController pid;
volatile bool balance_active = false;
volatile char drive_command = ' ';

void balance_init() {
    pid_init(&pid, 1.0, 0.0, 0.0);
}

void control_task(void* pvParameters) {
    while(1) {
        if (balance_active) {
            float angle = read_imu_angle();
            float output = pid_compute(&pid, 0.0, angle, 0.005);
            step_motor(0, (int)output, output > 0);
            step_motor(1, (int)output, output > 0);
        }
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}
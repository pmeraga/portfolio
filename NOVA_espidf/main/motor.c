#include "motor.h"
#include "driver/gpio.h"
#include "balance.h"

void init_motors() {
    gpio_set_direction(GPIO_NUM_5, GPIO_MODE_OUTPUT);
    gpio_set_direction(GPIO_NUM_4, GPIO_MODE_OUTPUT);
    gpio_set_direction(GPIO_NUM_2, GPIO_MODE_OUTPUT);
    gpio_set_direction(GPIO_NUM_15, GPIO_MODE_OUTPUT);
}

void step_motor(int motor, int steps, int dir) {
    gpio_num_t step_pin = (motor == 0) ? GPIO_NUM_5 : GPIO_NUM_2;
    gpio_num_t dir_pin = (motor == 0) ? GPIO_NUM_4 : GPIO_NUM_15;

    gpio_set_level(dir_pin, dir);
    for (int i = 0; i < steps; i++) {
        gpio_set_level(step_pin, 1);
        ets_delay_us(5);
        gpio_set_level(step_pin, 0);
        ets_delay_us(5);
    }
}

void drive_control() {
    switch (drive_command) {
        case 'w':
            step_motor(0, 10, 1);
            step_motor(1, 10, 1);
            break;
        case 'a':
            step_motor(1, 10, 1);
            break;
        case 'd':
            step_motor(0, 10, 1);
            break;
        case 's':
            step_motor(0, 10, 0);
            step_motor(1, 10, 0);
            break;
        default:
            break;
    }
}

void motor_task(void* pvParameters) {
    while(1) {
        drive_control();
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

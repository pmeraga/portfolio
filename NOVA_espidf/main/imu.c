#include "imu.h"
#include "driver/i2c.h"
#define MPU6050_ADDR 0x68
#define I2C_MASTER_NUM I2C_NUM_0

void init_imu() {
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = 21,
        .scl_io_num = 22,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = 400000,
    };
    i2c_param_config(I2C_MASTER_NUM, &conf);
    i2c_driver_install(I2C_MASTER_NUM, conf.mode, 0, 0, 0);

    uint8_t data[2] = {0x6B, 0x00};
    i2c_master_write_to_device(I2C_MASTER_NUM, MPU6050_ADDR, data, 2, 1000 / portTICK_PERIOD_MS);
}

float read_imu_angle() {
    // Simplified for now; real implementation would read accelerometer and gyro
    return 0.0;
}

void imu_task(void* pvParameters) {
    while(1) {
        // Read sensors if needed
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}
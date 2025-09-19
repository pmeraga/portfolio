#ifndef IMU_H
#define IMU_H

void init_imu();
void imu_task(void* pvParameters);
float read_imu_angle();

#endif
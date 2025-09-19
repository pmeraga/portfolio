#ifndef MOTOR_H
#define MOTOR_H

void init_motors();
void motor_task(void* pvParameters);
void step_motor(int motor, int steps, int dir);
void drive_control();

#endif
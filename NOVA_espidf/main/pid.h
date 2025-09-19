#ifndef PID_H
#define PID_H

typedef struct {
    float kp, ki, kd;
    float integral;
    float prev_error;
} PIDController;

void pid_init(PIDController* pid, float kp, float ki, float kd);
float pid_compute(PIDController* pid, float setpoint, float measured, float dt);

#endif
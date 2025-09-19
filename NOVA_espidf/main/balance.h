#ifndef BALANCE_H
#define BALANCE_H

void balance_init();
void control_task(void* pvParameters);
extern volatile bool balance_active;
extern volatile char drive_command;

#endif
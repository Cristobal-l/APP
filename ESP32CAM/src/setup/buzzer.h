#ifndef BUZZER_H
#define BUZZER_H

#include <Arduino.h>

#define BUZZER_PIN 21

void initBuzzer();
void beep(int duration);
void playTone(int frequency, int duration);

#endif
#ifndef DISPLAY_H
#define DISPLAY_H

#include <Arduino.h>

bool initDisplay();

void show(int line, String text);

#endif
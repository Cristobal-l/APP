#include <Arduino.h>
#include "../setup/buton.h"

void initButton() {
    // Usamos PULLUP interno para no necesitar resistencias físicas
    pinMode(BUTTON_PIN, INPUT_PULLUP);
}

bool isButtonPressed() {
    return (digitalRead(BUTTON_PIN) == LOW);
}
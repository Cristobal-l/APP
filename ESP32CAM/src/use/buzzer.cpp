#include "../setup/buzzer.h"

void initBuzzer() {
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);
}

void beep(int duration) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(duration);
    digitalWrite(BUZZER_PIN, LOW);
}

void playTone(int frequency, int duration) {
    ledcAttachPin(BUZZER_PIN, 0);
    ledcWriteTone(0, frequency);
    delay(duration);
    ledcWriteTone(0, 0);
}

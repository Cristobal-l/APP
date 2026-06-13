#include <Wire.h>
#include <VL53L0X.h>
#include "../setup/laser.h"

VL53L0X sensor;

bool initLaser() {
    sensor.setTimeout(500);
    if (!sensor.init()) {
        Serial.println("Fallo al detectar el sensor VL53L0X");
        return false;
    }

    sensor.startContinuous();
    return true;
}

int getDistance() {
    int distance = sensor.readRangeContinuousMillimeters();
    if (sensor.timeoutOccurred()) {
        Serial.println("TIMEOUT en el sensor");
        return -1;
    }
    return distance;
}
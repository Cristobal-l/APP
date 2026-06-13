#include <Arduino.h>
#include "setup/wifi.h"


void connectWifi(const char* ssid, const char* password){
    Serial.printf("Conectando a:", ssid);
    WiFi.begin(ssid,password);

    while(WiFi.status() != WL_CONNECTED){
        delay(500);
        Serial.print(".");
    }
    Serial.println("\n[WiFi] Conectado exitosamente.");
    Serial.print("[WiFi] Dirección IP: ");
    Serial.println(WiFi.localIP());
}
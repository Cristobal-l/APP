#include <Arduino.h>
#include <HTTPClient.h>    
#include "setup/server.h"
#include <WiFi.h>         

const char* serverHeartbeatUrl = "http://TU_IP_DEL_SERVIDOR:8000/esp32/heartbeat";

void enviarHeartbeat() {
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        
        // Iniciar la conexión con el endpoint
        http.begin(serverHeartbeatUrl);
        http.addHeader("Content-Type", "application/json");
        
        // Enviamos un JSON vacío en el cuerpo del POST
        int httpResponseCode = http.POST("{}");
        
        if (httpResponseCode > 0) {
            Serial.print(" Heartbeat enviado. Código: ");
            Serial.println(httpResponseCode);
        } else {
            Serial.print(" Error en Heartbeat: ");
            Serial.println(http.errorToString(httpResponseCode).c_str());
        }
        
        http.end(); // Cerramos la conexión para liberar memoria RAM
    } else {
        Serial.println(" Heartbeat omitido: Sin conexión WiFi.");
    }
}
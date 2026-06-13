#include <Arduino.h>
#include "setup/wifi.h"
#include "setup/camera.h"
#include "setup/server.h"
#include "setup/display.h"
#include "setup/buton.h"
#include "setup/buzzer.h"
#include "setup/laser.h"
#include <HTTPClient.h>

const char* ssid = "Catalina";
const char* pswd = "Cata141592";

bool alarmaActiva = false;
int clicks = 0;
unsigned long tUltimoClick = 0;
const int ventana = 400;
bool ultimoBoton = false;



int obtenerIntervalo(int distancia){
    if(distancia <= 0 || distancia > 1000){
      return 0; 
    }

  int intervalo = map(distancia, 50, 1000, 50, 600);

  return constrain(intervalo, 50, 600);
}

void setup(){
  Serial.begin(115200);
  Serial.println();

  Serial.println("ESP32-cam activo");

  initDisplay();
  initButton();
  initBuzzer();
  initLaser();
  
  delay(200);
  connectWifi(ssid, pswd);
  
  
  //initFlash();
  //initCamera();
  //startServer();
}



void loop() {
  //handleWebClient();
  unsigned long tActual = millis();
  
  if (tActual - tUltimoHeartbeat >= intervaloHeartbeat) {
    enviarHeartbeat(); // <-- Llamada directa a la función que está en use/server.cpp
    tUltimoHeartbeat = tActual;
  }

  bool actualBoton = isButtonPressed();
  
  if(actualBoton && !ultimoBoton){
    unsigned long tActual = millis();

    if(tActual - tUltimoClick < ventana){
      clicks = clicks + 1;
    }
    else{
      clicks = 1;
    }
    tUltimoClick = tActual;

    if(clicks == 2){
      alarmaActiva = !alarmaActiva;
      clicks = 0;
      show(2, alarmaActiva ? "alarma: on" : "alarma off");
    }
    delay(50);
  }
  ultimoBoton = actualBoton;


  int d = getDistance();
  int espera = obtenerIntervalo(d);

  if(alarmaActiva && espera > 0){
    digitalWrite(BUZZER_PIN, HIGH);
    delay(40);
    digitalWrite(BUZZER_PIN, LOW);

    delay(espera);
  }

  if(d != -1){
    show(0, "dist: " + String(d) + "mm");
  }
}


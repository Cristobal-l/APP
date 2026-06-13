#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "../setup/display.h"

#define SCREEN_WIDTH 128 
#define SCREEN_HEIGHT 64 

#define I2C_SDA 19
#define I2C_SCL 18

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

bool initDisplay() {
  Wire.begin(I2C_SDA, I2C_SCL);

  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("Fallo al encontrar la pantalla OLED SSD1306");
    return false;
  }

  display.clearDisplay();
  display.setTextSize(1);             
  display.setTextColor(SSD1306_WHITE);
  
  display.setCursor(0, 0);
  display.println("pantalla ok");
  display.display();
  
  return true;
}

void show(int line, String text) {
  int y = line * 10; 

  display.setTextColor(SSD1306_WHITE, SSD1306_BLACK); 

  display.setCursor(0, y);
  display.println(text); 
  
  display.display();
}
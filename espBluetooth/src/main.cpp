#include <Arduino.h>
#include "esp_camera.h"
#include "BluetoothSerial.h"
#include <Wire.h>
#include "Adafruit_VL53L0X.h"

// Define ESP32-CAM AI-Thinker Pin Model
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// I2C pins for VL53L0X on ESP32-CAM
#define I2C_SDA           15
#define I2C_SCL           14

// Timing configuration
const unsigned long PHOTO_INTERVAL = 15000; // 15 seconds
const unsigned long SENSOR_INTERVAL = 200;  // 200 milliseconds

unsigned long lastPhotoTime = 0;
unsigned long lastSensorTime = 0;

// Bluetooth Serial object
BluetoothSerial SerialBT;

// VL53L0X Sensor object
Adafruit_VL53L0X lox = Adafruit_VL53L0X();

// Camera initialization function
bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Use low resolution / quality for faster transmission over Bluetooth
  if(psramFound()){
    config.frame_size = FRAMESIZE_QVGA; // 320x240
    config.jpeg_quality = 12;
    config.fb_count = 1;
  } else {
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }

  // Camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    return false;
  }
  return true;
}

// Function to take a photo and send it via Bluetooth
void captureAndSendPhoto() {
  Serial.println("Taking photo...");
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    return;
  }

  if (SerialBT.hasClient()) {
    // Send standard header for the image to distinguish it from sensor data
    SerialBT.print("IMAGE_START:");
    SerialBT.println(fb->len);
    
    // Write image bytes to Bluetooth Serial
    SerialBT.write(fb->buf, fb->len);
    
    // Send trailing marker
    SerialBT.println("IMAGE_END");
    Serial.printf("Photo sent successfully. Size: %d bytes\n", fb->len);
  } else {
    Serial.println("No Bluetooth client connected. Photo not sent.");
  }

  // Return the frame buffer back to the driver
  esp_camera_fb_return(fb);
}

// Function to read sensor and send data via Bluetooth
void readAndSendSensor() {
  VL53L0X_RangingMeasurementData_t measure;
  lox.rangingTest(&measure, false);

  if (measure.RangeStatus != 4) { // Phase out of range status
    int distance = measure.RangeMilliMeter;
    Serial.print("Distance (mm): ");
    Serial.println(distance);

    if (SerialBT.hasClient()) {
      SerialBT.print("VL53L0X:");
      SerialBT.println(distance);
    }
  } else {
    Serial.println("Sensor out of range");
    if (SerialBT.hasClient()) {
      SerialBT.println("VL53L0X:OUT_OF_RANGE");
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("Initializing system...");

  // Initialize Bluetooth
  if (!SerialBT.begin("ESP32CAM-VIA")) {
    Serial.println("An error occurred initializing Bluetooth");
  } else {
    Serial.println("Bluetooth initialized. Device name: ESP32CAM-VIA");
  }

  // Initialize Camera
  if (initCamera()) {
    Serial.println("Camera initialized successfully.");
  } else {
    Serial.println("Camera initialization FAILED.");
  }

  // Initialize I2C and VL53L0X Sensor
  Wire.begin(I2C_SDA, I2C_SCL);
  if (lox.begin()) {
    Serial.println("VL53L0X sensor initialized successfully.");
  } else {
    Serial.println("VL53L0X initialization FAILED.");
  }
}

void loop() {
  unsigned long currentMillis = millis();

  // Handle sensor reading every 200 ms
  if (currentMillis - lastSensorTime >= SENSOR_INTERVAL) {
    lastSensorTime = currentMillis;
    readAndSendSensor();
  }

  // Handle photo capture every 15 seconds
  if (currentMillis - lastPhotoTime >= PHOTO_INTERVAL) {
    lastPhotoTime = currentMillis;
    captureAndSendPhoto();
  }
}
#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>

// ==========================================
// CONFIGURACIÓN DE RED
// ==========================================
const char* ssid = "Catalina";
const char* password = "Cata141592";

// ==========================================
// CONFIGURACIÓN DE PINES I2C (SIN MICROSD)
// ==========================================
#define I2C_SDA 15
#define I2C_SCL 14

// ==========================================
// CONFIGURACIÓN DE PINES DE LA CÁMARA
// ==========================================
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

// Instancia del servidor web en el puerto 80
WebServer server(80);

// ==========================================
// LECTURA SIMULADA DEL SENSOR I2C
// ==========================================
float obtenerLecturaI2C() {
  static float valorSimulado = 24.5;
  valorSimulado += (random(-10, 11) / 10.0); 
  return valorSimulado;
}

// ==========================================
// INTERFAZ WEB (HTML + CSS + JAVASCRIPT)
// ==========================================
String construirPaginaWeb() {
  String html = "<!DOCTYPE html><html><head>";
  html += "<meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>Panel ESP32-CAM</title>";
  
  html += "<style>";
  html += "body { font-family: 'Segoe UI', Arial, sans-serif; text-align: center; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }";
  html += ".container { max-width: 600px; margin: 0 auto; background: #1e293b; padding: 25px; border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3); border: 1px solid #334155; }";
  html += "h1 { font-size: 24px; color: #38bdf8; margin-bottom: 5px; }";
  html += "p { color: #94a3b8; font-size: 14px; margin-bottom: 20px; }";
  html += ".monitor-stream { width: 100%; max-width: 480px; height: auto; border-radius: 8px; border: 2px solid #334155; background: #0f172a; margin-bottom: 15px; }";
  html += ".card { background: #0f172a; padding: 15px; border-radius: 12px; margin: 15px 0; border: 1px solid #1e293b; }";
  html += ".label { text-transform: uppercase; font-size: 11px; letter-spacing: 1px; color: #64748b; }";
  html += ".value { font-size: 36px; color: #4ade80; font-weight: bold; margin-top: 5px; }";
  html += ".status { font-size: 12px; color: #64748b; display: inline-flex; align-items: center; gap: 5px; justify-content: center; }";
  html += ".dot { width: 8px; height: 8px; background: #4ade80; border-radius: 50%; display: inline-block; animation: pulse 2s infinite; }";
  html += "@keyframes pulse { 0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.7); } 70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(74, 222, 128, 0); } 100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); } }";
  html += "</style>";
  
  // Script en JavaScript para actualizar los datos y la foto asíncronamente en segundo plano
  html += "<script>";
  html += "setInterval(function() {";
  // Actualizar el valor del texto del sensor
  html += "  fetch('/sensor').then(response => response.text()).then(data => {";
  html += "    document.getElementById('sensor-val').innerText = data;";
  html += "  });";
  // Actualizar la imagen añadiendo un timestamp dinámico para evitar el caché del navegador
  html += "  document.getElementById('stream').src = '/foto?t=' + new Date().getTime();";
  html += "}, 2000);"; // Frecuencia de actualización: cada 2 segundos
  html += "</script>";
  
  html += "</head><body>";
  html += "<div class='container'>";
  html += "<h1>Servidor Transmisión ESP32-CAM</h1>";
  html += "<p>Monitoreo de video y telemetría en tiempo real</p>";
  
  // Contenedor de la Imagen capturada
  html += "<img id='stream' src='/foto' class='monitor-stream' alt='Cargando captura...'>";
  
  // Tarjeta de datos del sensor
  html += "<div class='card'>";
  html += "<div class='label'>Lectura del Sensor I2C</div>";
  html += "<div id='sensor-val' class='value'>0.00</div>";
  html += "</div>";
  
  html += "<div class='status'><span class='dot'></span> Conectado - Video en Vivo</div>";
  html += "</div>";
  html += "</body></html>";
  
  return html;
}

// ==========================================
// MANEJADORES DE RUTAS HTTP
// ==========================================

// Envia la estructura principal HTML
void manejarRaiz() {
  server.send(200, "text/html", construirPaginaWeb());
}

// Devuelve únicamente el valor numérico del sensor
void manejarSensor() {
  server.send(200, "text/plain", String(obtenerLecturaI2C(), 2));
}

// Captura una foto en el momento y la transmite como imagen JPEG
void manejarFoto() {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[ERROR] Fallo al capturar imagen de la cámara");
    server.send(500, "text/plain", "Fallo al capturar imagen");
    return;
  }

  // Indicamos al navegador que lo que se envía es una imagen de tipo JPEG
  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.sendHeader("Access-Control-Allow-Origin", "*");
  
  // Enviamos el buffer binario crudo directamente a través de la red
  server.sendContent_P((const char *)fb->buf, fb->len);
  
  // Liberar el buffer para la siguiente captura
  esp_camera_fb_return(fb);
}

// ==========================================
// CONFIGURACIÓN INICIAL (SETUP)
// ==========================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  // 1. Inicializar bus I2C
  Wire.begin(I2C_SDA, I2C_SCL);
  Serial.println("\n[INFO] Bus I2C listo.");

  // 2. Configurar hardware de la cámara
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
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if(psramFound()){
    config.frame_size = FRAMESIZE_VGA;  // 640x480 (ideal para velocidad en servidor web local)
    config.jpeg_quality = 12;           
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[ERROR] Fallo en inicialización de cámara: 0x%x\n", err);
  } else {
    Serial.println("[INFO] Cámara configurada correctamente.");
  }

  // 3. Conexión Wi-Fi
  Serial.printf("[WIFI] Conectando a %s ", ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n[WIFI] Conexión establecida.");
  Serial.print("[WIFI] Ingresa a este enlace: http://");
  Serial.println(WiFi.localIP());

  // 4. Definición de rutas del servidor HTTP
  server.on("/", manejarRaiz);       // Página principal
  server.on("/sensor", manejarSensor); // Endpoint para datos numéricos
  server.on("/foto", manejarFoto);     // Endpoint que captura y envía el JPEG

  // Arrancar servidor
  server.begin();
  Serial.println("[SERVER] Servidor web HTTP en funcionamiento.");
}

// ==========================================
// BUCLE PRINCIPAL (LOOP)
// ==========================================
void loop() {
  // Atiende de forma asíncrona las solicitudes web entrantes
  server.handleClient();
  delay(10);
}
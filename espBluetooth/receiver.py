import serial
import time
import os

# Configuration
# Replace with your ESP32 Bluetooth COM port (e.g., 'COM3' on Windows or '/dev/rfcomm0' on Linux)
PORT = 'COM4' 
BAUD_RATE = 115200
OUTPUT_DIR = 'received_images'

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print(f"Connecting to ESP32 on {PORT}...")
    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
        print("Connected! Waiting for data...")
    except Exception as e:
        print(f"Error connecting to serial port: {e}")
        print("Make sure you have paired the ESP32-CAM via Bluetooth settings and set the correct COM port.")
        return

    buffer = bytearray()
    
    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline()
                try:
                    decoded = line.decode('utf-8', errors='ignore').strip()
                except Exception:
                    decoded = ""

                # Handle distance data
                if decoded.startswith("VL53L0X:"):
                    distance = decoded.split(":")[1]
                    print(f"[Sensor] Distance: {distance} mm")

                # Handle start of image transfer
                elif decoded.startswith("IMAGE_START:"):
                    try:
                        image_size = int(decoded.split(":")[1])
                    except ValueError:
                        print("Error parsing image size.")
                        continue
                    
                    print(f"[Camera] Receiving image of size {image_size} bytes...")
                    
                    # Read the exact binary image bytes
                    image_data = bytearray()
                    start_time = time.time()
                    while len(image_data) < image_size:
                        # Wait for bytes to become available
                        if ser.in_waiting > 0:
                            chunk = ser.read(min(ser.in_waiting, image_size - len(image_data)))
                            image_data.extend(chunk)
                        # Timeout protection (5 seconds)
                        if time.time() - start_time > 5.0:
                            print("[Camera] Timeout reached while receiving image bytes.")
                            break
                    
                    # Read the trailing new line/IMAGE_END line
                    trailing = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if len(image_data) == image_size:
                        filename = os.path.join(OUTPUT_DIR, f"photo_{int(time.time())}.jpg")
                        with open(filename, 'wb') as f:
                            f.write(image_data)
                        print(f"[Camera] Image saved to {filename}")
                    else:
                        print(f"[Camera] Image error: received {len(image_data)} of {image_size} bytes")

        except KeyboardInterrupt:
            print("\nExiting receiver...")
            break
        except Exception as e:
            print(f"Error reading: {e}")
            break

    ser.close()

if __name__ == '__main__':
    main()

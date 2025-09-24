#include <Servo.h>

// --- Servo Pins ---
const int SERVO_1_PIN = 2;
const int SERVO_2_PIN = 3;
const int SERVO_3_PIN = 4;
const int SERVO_4_PIN = 5;

// --- Servo Objects ---
Servo servo1, servo2, servo3, servo4;

// --- State Machine ---
enum Mode { IDLE, CONTINUOUS, TRIGGER };
Mode currentMode = IDLE;

void setup() {
  Serial.begin(9600);

  // Attach servos
  servo1.attach(SERVO_1_PIN);
  servo2.attach(SERVO_2_PIN);
  servo3.attach(SERVO_3_PIN);
  servo4.attach(SERVO_4_PIN);
  
  // Move all to 90 degrees for calibration
  servo1.write(90);
  servo2.write(90);
  servo3.write(90);
  servo4.write(90);
  
  Serial.println("Servo Controller Initialized. Mode: IDLE");
}

void loop() {
  checkSerialCommands();
}

void checkSerialCommands() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    Serial.println(command); // Print the command for debugging

    switch (command) {
      case '1':
        activateAllServos(90);  // Move all servos to 90 degrees
        break;
      case '2':
        activateAllServos(45);  // Move all servos to 45 degrees
        break;
      case '3':
        activateAllServos(135); // Move all servos to 135 degrees
        break;
      case '0':
        activateAllServos(0);   // Move all servos to 0 degrees
        break;
      case 'C':
        currentMode = CONTINUOUS; // Change mode to CONTINUOUS
        break;
      case 'T':
        currentMode = TRIGGER;    // Change mode to TRIGGER
        break;
      case 'X':
        currentMode = IDLE;       // Change mode to IDLE
        activateAllServos(90);    // Return to home position
        break;
      default:
        // Unknown command, do nothing
        break;
    }
  }
}

void activateAllServos(int angle) {
  servo1.write(angle);
  servo2.write(angle);
  servo3.write(angle);
  servo4.write(angle);
  delay(1000); // Hold position for 1 second
}

// Wood Sorting System - IR Trigger and Sorter Control

#include <Servo.h>

// --- Pin Definitions ---
const int IR_SENSOR_PIN = 11;

// Servos for sorting gates
const int SERVO_1_PIN = 2;
const int SERVO_2_PIN = 3;
const int SERVO_3_PIN = 4;

// Stepper motor pins (defined but not used in this sketch)
const int STEPPER_ENA_PIN = 8;
const int STEPPER_DIR_PIN = 9;
const int STEPPER_STEP_PIN = 10;

// --- Servo Objects ---
Servo servo1;
Servo servo2;
Servo servo3;

// --- State Variables ---
int lastIrState = HIGH; // Assume beam is initially unbroken
unsigned long lastTriggerTime = 0;
const long debounceDelay = 50; // 50ms debounce delay

void setup() {
  Serial.begin(9600);

  // Configure Pin Modes
  pinMode(IR_SENSOR_PIN, INPUT_PULLUP);
  pinMode(STEPPER_ENA_PIN, OUTPUT);
  pinMode(STEPPER_DIR_PIN, OUTPUT);
  pinMode(STEPPER_STEP_PIN, OUTPUT);
  digitalWrite(STEPPER_ENA_PIN, HIGH); // Disable stepper initially

  // Attach servos to their pins
  servo1.attach(SERVO_1_PIN);
  servo2.attach(SERVO_2_PIN);
  servo3.attach(SERVO_3_PIN);

  // Ensure all servo gates are closed (at 0 degrees)
  servo1.write(0);
  servo2.write(0);
  servo3.write(0);
}

void loop() {
  checkIrSensor();
  checkSerialCommands();
}

void checkIrSensor() {
  int currentIrState = digitalRead(IR_SENSOR_PIN);
  if (currentIrState != lastIrState && (millis() - lastTriggerTime) > debounceDelay) {
    if (currentIrState == LOW) { // Beam is broken
      Serial.println("B");
      lastTriggerTime = millis();
    }
    lastIrState = currentIrState;
  }
}

void checkSerialCommands() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    if (command == '1') {
      activateServoGate(servo1);
    } else if (command == '2') {
      activateServoGate(servo2);
    } else if (command == '3') {
      activateServoGate(servo3);
    }
  }
}

void activateServoGate(Servo& gateServo) {
  gateServo.write(90);  // Move servo to 90 degrees to open gate
  delay(1000);          // Keep gate open for 1 second
  gateServo.write(0);   // Move servo back to 0 degrees to close gate
}

/*
  Master Controller for Automated Wood Sorting System (v4)

  This sketch includes length measurement based on IR beam duration.

  Serial Commands:
  - 'B': Sent TO Python when IR beam is broken (triggers image capture).
  - 'L:[ms]': Sent TO Python when beam is cleared, reports time in ms.
  - '1', '2', '3': Received FROM Python for sorting gates.
  - 'C', 'T', 'X': Received FROM Python for mode control.
*/

#include <Servo.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// --- Pin Definitions ---
const int IR_SENSOR_PIN = 11;
const int SERVO_1_PIN = 2;
const int SERVO_2_PIN = 3;
const int SERVO_3_PIN = 4;
const int STEPPER_ENA_PIN = 8;
const int STEPPER_DIR_PIN = 9;
const int STEPPER_STEP_PIN = 10;

// --- Objects ---
Servo servo1, servo2, servo3;

// --- State Machine ---
enum Mode { IDLE, CONTINUOUS, TRIGGER };
Mode currentMode = IDLE;

// --- Stepper Control ---
unsigned long stepInterval = 500; // Microseconds, controls speed
unsigned long lastStepTime = 0;
bool stepState = false;

// --- Trigger Mode Control ---
bool motorActiveForTrigger = false;
bool inRunOutPhase = false;
unsigned long runOutStartTime = 0;
const long runOutDuration = 7000; // Run for 7 seconds after beam is cleared

// --- IR Sensor & Length Measurement ---
int lastStableIrState = HIGH;      // Last known stable state of the IR sensor
int lastFlickerIrState = HIGH;     // Last read state, used for debounce timing
unsigned long lastStateChangeTime = 0; // Time of the last state flicker
const long debounceDelay = 50;     // Debounce delay in milliseconds
unsigned long beamBrokenStartTime = 0; // Timestamp when the beam was broken
bool beamIsBroken = false;         // Tracks if the beam is currently considered broken

void setup() {
  Serial.begin(9600);

  // Pin Modes
  pinMode(IR_SENSOR_PIN, INPUT_PULLUP);
  pinMode(STEPPER_ENA_PIN, OUTPUT);
  pinMode(STEPPER_DIR_PIN, OUTPUT);
  pinMode(STEPPER_STEP_PIN, OUTPUT);
  
  digitalWrite(STEPPER_DIR_PIN, HIGH); // Set conveyor direction
  digitalWrite(STEPPER_ENA_PIN, HIGH); // Start with stepper disabled

  // Attach servos
  servo1.attach(SERVO_1_PIN);
  servo2.attach(SERVO_2_PIN);
  servo3.attach(SERVO_3_PIN);
  servo1.write(0); servo2.write(0); servo3.write(0);

  Serial.println("Master Controller V4 Initialized. Mode: IDLE");
}

void loop() {
  handleStepper();
  checkIrSensor();
  checkSerialCommands();
}

void handleStepper() {
  bool shouldBeActive = false;
  // Add a small delay to prevent spamming the serial port with status messages
  static unsigned long lastStatusTime = 0;
  bool printStatus = (millis() - lastStatusTime > 1000); // Print status every second
  if (printStatus) lastStatusTime = millis();

  if (currentMode == CONTINUOUS) {
    shouldBeActive = true;
  } 
  else if (currentMode == TRIGGER) {
    if (inRunOutPhase) {
      if (millis() - runOutStartTime < runOutDuration) {
        shouldBeActive = true; // Continue running during run-out
      } else {
        inRunOutPhase = false;
        motorActiveForTrigger = false;
        shouldBeActive = false;
      }
    } else {
      shouldBeActive = motorActiveForTrigger;
    }
  }

  digitalWrite(STEPPER_ENA_PIN, shouldBeActive ? LOW : HIGH);

  if (shouldBeActive) {
    unsigned long currentTime = micros();
    if (currentTime - lastStepTime >= stepInterval) {
      lastStepTime = currentTime;
      stepState = !stepState;
      digitalWrite(STEPPER_STEP_PIN, stepState);
    }
  }

  if (printStatus) {
    Serial.print("Mode: ");
    if (currentMode == IDLE) Serial.print("IDLE");
    else if (currentMode == CONTINUOUS) Serial.print("CONTINUOUS");
    else if (currentMode == TRIGGER) Serial.print("TRIGGER");
    Serial.print(" | Motor Active: ");
    Serial.println(shouldBeActive ? "YES" : "NO");
  }
}

void checkIrSensor() {
  int currentIrState = digitalRead(IR_SENSOR_PIN);

  // --- Debounce Logic ---
  // If the sensor reading has changed, reset the debounce timer
  if (currentIrState != lastFlickerIrState) {
    lastStateChangeTime = millis();
  }
  lastFlickerIrState = currentIrState;

  // If the sensor reading has been stable for the debounce delay
  if ((millis() - lastStateChangeTime) > debounceDelay) {
    // And if the stable state has changed
    if (currentIrState != lastStableIrState) {
      if (currentIrState == LOW) {
        // --- Beam Broken Event ---
        Serial.println("B");
        beamBrokenStartTime = millis();
        beamIsBroken = true; // Mark the beam as officially broken
        if (currentMode == TRIGGER) {
          motorActiveForTrigger = true;
          inRunOutPhase = false;
        }
      } else {
        // --- Beam Cleared Event ---
        // Only trigger if the beam was previously broken to avoid spurious signals
        if (beamIsBroken) {
          unsigned long duration = millis() - beamBrokenStartTime;
          String lengthMessage = "L:" + String(duration);
          Serial.println(lengthMessage);
          beamIsBroken = false; // Reset the flag
        }
        if (currentMode == TRIGGER && motorActiveForTrigger) {
          inRunOutPhase = true;
          runOutStartTime = millis();
        }
      }
      lastStableIrState = currentIrState; // Update the stable state
    }
  }
}

void checkSerialCommands() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    switch (command) {
      case '1': activateServoGate(servo1, 45); break;   // Grade G2-0
      case '2': activateServoGate(servo2, 90); break;   // Grade G2-1 to G2-3
      case '3': activateServoGate(servo3, 135); break;  // Grade G2-4
      case 'C': 
        currentMode = CONTINUOUS;
        Serial.println("Mode: CONTINUOUS");
        break;
      case 'T': 
        currentMode = TRIGGER;
        motorActiveForTrigger = false; // Reset trigger state
        inRunOutPhase = false;
        Serial.println("Mode: TRIGGER");
        break;
      case 'X': 
        currentMode = IDLE;
        motorActiveForTrigger = false; // Reset trigger state
        inRunOutPhase = false;
        Serial.println("Mode: IDLE (Stopped)");
        break;
    }
  }
}

void activateServoGate(Servo& gateServo, int angle) {
  gateServo.write(angle);  // Move to the specified sorting angle
  delay(1000);             // Hold position for 1 second
  gateServo.write(0);      // Return to home position (0 degrees)
}

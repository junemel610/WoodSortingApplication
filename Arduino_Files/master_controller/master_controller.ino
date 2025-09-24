/*
  Master Controller for Automated Wood Sorting System (v4)

  This sketch includes length measurement based on IR beam duration.

  Serial Commands:
  - 'B': Sent TO Python when IR beam is broken (triggers image capture).
  - 'L:[ms]': Sent TO Python when beam is cleared, reports time in ms.
  - '1': Grade 1 - Move all servos to 90 degrees
  - '2': Grade 2 - Move all servos to 45 degrees  
  - '3': Grade 3 - Move all servos to 135 degrees
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
const int SERVO_4_PIN = 5;
const int STEPPER_ENA_PIN = 8;
const int STEPPER_DIR_PIN = 9;
const int STEPPER_STEP_PIN = 10;

// --- Objects ---
Servo servo1, servo2, servo3, servo4;

// --- State Machine ---
enum Mode { IDLE, CONTINUOUS, TRIGGER };
Mode currentMode = IDLE;

// --- Stepper Control ---
unsigned long stepInterval = 500; // Microseconds, controls speed
unsigned long lastStepTime = 0;
bool stepState = false;

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
  servo4.attach(SERVO_4_PIN);
  servo1.write(90); servo2.write(90); servo3.write(90); servo4.write(90);

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
    // In TRIGGER mode, stepper runs continuously
    // Only detection/grading is triggered by IR beam, not motor control
    shouldBeActive = true;
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
    // Only print status when motor is not running to avoid timing issues
    if (currentMode == IDLE || !shouldBeActive) {
      Serial.print("M:");
      if (currentMode == IDLE) Serial.print("IDLE");
      else if (currentMode == CONTINUOUS) Serial.print("CONT");
      else if (currentMode == TRIGGER) Serial.print("TRIG-MOTOR");
      Serial.print("|");
      Serial.println(shouldBeActive ? "Y" : "N");
    }
  }
}

void checkIrSensor() {
  int currentIrState = digitalRead(IR_SENSOR_PIN);

  // Reduce debug frequency and make it conditional
  static unsigned long lastDebugTime = 0;
  if (millis() - lastDebugTime > 5000) { // Every 5 seconds instead of 2
    // Only print if motor is not active to avoid interrupting stepper timing
    if (currentMode == IDLE || !digitalRead(STEPPER_ENA_PIN)) {
      Serial.print("IR: ");
      Serial.println(currentIrState);
    }
    lastDebugTime = millis();
  }

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
        // Note: In TRIGGER mode, motor runs continuously
        // IR beam only triggers detection, not motor control
      } else {
        // --- Beam Cleared Event ---
        // Only trigger if the beam was previously broken to avoid spurious signals
        if (beamIsBroken) {
          unsigned long duration = millis() - beamBrokenStartTime;
          // Use faster serial output - avoid String class
          Serial.print("L:");
          Serial.println(duration);
          beamIsBroken = false; // Reset the flag
        }
        // Note: Motor continues running in TRIGGER mode
      }
      lastStableIrState = currentIrState; // Update the stable state
    }
  }
}

void checkSerialCommands() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    // Minimal serial output to reduce blocking time
    Serial.println(command);
    
    switch (command) {
      case '1': 
        activateAllServoGates(90); 
        break;   
      case '2': 
        activateAllServoGates(45); 
        break;   
      case '3': 
        activateAllServoGates(135); 
        break;
      case '0':
        activateAllServoGates(0);
        break;
      case 'C': 
        currentMode = CONTINUOUS;
        break;
      case 'T': 
        currentMode = TRIGGER;
        // Motor will run continuously in TRIGGER mode
        // IR beam only triggers detection, not motor control
        break;
      case 'X': 
        currentMode = IDLE;
        activateAllServoGates(90);
        // Stop motor in IDLE mode
        break;
      default:
        // Skip unknown command output to avoid blocking
        break;
    }
  }
}

void activateServoGate(Servo& gateServo, int angle) {
  gateServo.write(angle);  // Move to the specified sorting angle
  delay(1000);             // Hold position for 1 second
  gateServo.write(0);      // Return to home position (0 degrees)
}

void activateAllServoGates(int angle) {
  // Minimal serial output during servo operation
  
  // Move all servos to the specified angle simultaneously
  servo1.write(angle);
  servo2.write(angle);
  servo3.write(angle);
  servo4.write(angle);
  
  // Servos will hold this position until a new command is received
  // No automatic return to home position
}

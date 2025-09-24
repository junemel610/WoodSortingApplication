const int IR_SENSOR_PIN = 11;

void setup() {
  Serial.begin(9600);
  pinMode(IR_SENSOR_PIN, INPUT);  // no pull-up
}

void loop() {
  int val = digitalRead(IR_SENSOR_PIN);
  Serial.println(val);
  delay(200);
}

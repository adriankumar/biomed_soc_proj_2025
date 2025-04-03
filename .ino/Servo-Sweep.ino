#include <Servo.h>

// declares pre-void setup == global variables
Servo myServo;  // create servo object to control a servo
bool sweep_T = 0;  // declare sweep_T as a global variable
int callentry = 0;  // declare callentry as a global variable

void setup() {
  Serial.begin(9600);
  myServo.attach(6);  // attaches the servo on pin 6 to the servo object
  myServo.write(0);
}

void loop() {
  consoleinput();
  sweep_T = Sweep(sweep_T);
  // Serial.println(sweep_T);
}

void consoleinput() {
  if (callentry == 0) {
    Serial.println("Enter smth to sweep the servo");
    callentry = 1;
  }
  if (Serial.available() > 0) {
    // read the incoming byte:
    sweep_T = Serial.read() - '0';  // Convert char to int
    // say what you got:
    Serial.print("I received: ");
    Serial.println(sweep_T);
    callentry = 0;  // Reset callentry to allow the message to be printed again after an entry is received
  }
}

bool Sweep(bool sweep_T) {
  if (sweep_T == 1) {
    // Sweep from 0 to 180 degrees
    for (int angle = 0; angle <= 180; angle++) {
      myServo.write(angle);
      delay(15);  // Small delay for smooth movement
    }
    
    // Sweep back from 180 to 0 degrees
    for (int angle = 180; angle >= 0; angle--) {
      myServo.write(angle);
      delay(15);
    }
    sweep_T = 0;
    Serial.println("Servo sweep complete");
    Serial.println("sweep_T reset to 0");
  }
  return sweep_T;
}
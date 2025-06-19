#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// Create PCA9685 object with default I2C address (0x40)
Adafruit_PWMServoDriver pca = Adafruit_PWMServoDriver(0x40);

// Servo configuration
#define SERVO_MIN 150   // Pulse for 0 degrees
#define SERVO_MAX 600   // Pulse for 180 degrees
#define PWM_FREQ 50     // 50Hz frequency for servos
#define MAX_SERVOS 32   // Maximum number of servos the system can support

// Servo state tracking
struct ServoState {
  float targetAngle;    // Target angle from command
  float currentAngle;   // Current smoothed angle
  float lastSentAngle;  // Last angle sent to servo
};

// Array to track state of each servo
ServoState servoStates[MAX_SERVOS];
uint8_t activeNumServos = 5; // Default active servos, updated by NUM_SERVOS command

// Smoothing parameters
float smoothingFactor = 1.0;  // Default, updatable via GSF command

// Update interval for servo smoothing
unsigned long lastUpdateTime = 0;
const int updateInterval = 10;  // Update every 10ms (100Hz)

// Command parsing
String inputBuffer = "";
bool commandComplete = false;

// Control flags
bool isStopped = false; // Flag for STOP command

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  delay(1000);
  Serial.println("Servo Control System Starting...");
  
  // Initialize I2C on custom pins: SDA=21, SCL=47
  Wire.begin(21, 47);
  Serial.println("I2C started on SDA=21, SCL=47");
  
  // Initialize the PCA9685 board
  if (!pca.begin()) {
    Serial.println("PCA9685 initialization failed!");
    while (1); // Halt if PCA9685 not found
  }
  
  // Set the PWM frequency for servo operation
  pca.setPWMFreq(PWM_FREQ);
  Serial.println("PCA9685 initialized with PWM frequency of 50Hz");
  
  // Initialize all servos to middle position (90 degrees)
  for (uint8_t i = 0; i < MAX_SERVOS; i++) {
    // Set initial values for servo states
    servoStates[i].targetAngle = 90.0;
    servoStates[i].currentAngle = 90.0;
    servoStates[i].lastSentAngle = 90.0;
    
    // Only set the actual servo positions for active servos
    if (i < activeNumServos) {
      pca.setPWM(i, 0, angleToPulse(90));
    }
  }
  
  Serial.print("System initialized with ");
  Serial.print(activeNumServos);
  Serial.println(" active servos");
  Serial.println("Ready for commands");
}

void loop() {
  // Read and process serial commands
  readSerialCommands();
  
  // Process completed commands
  if (commandComplete) {
    processCommand(inputBuffer);
    inputBuffer = "";
    commandComplete = false;
  }
  
  // Update servo positions with smoothing at the defined interval
  if (!isStopped) {
    unsigned long currentTime = millis();
    if (currentTime - lastUpdateTime >= updateInterval) {
      lastUpdateTime = currentTime;
      updateServos();
    }
  }
}

void readSerialCommands() {
  while (Serial.available() > 0 && !commandComplete) {
    char inChar = (char)Serial.read();
    
    if (inChar == '\n') {
      commandComplete = true;
    } 
    else if (inChar != '\r') {
      inputBuffer += inChar;
    }
  }
}

void processCommand(String command) {
  //trim whitespace
  command.trim();
  
  //check for empty command
  if (command.length() == 0) {
    return;
  }
  
  //handle STOP command (special case)
  if (command.equals("STOP")) {
    isStopped = true;
    Serial.println("STOP command received - servo motion halted");
    return;
  }
  
  //parse command by finding the command type before the first colon
  int firstColon = command.indexOf(':');
  if (firstColon <= 0) {
    Serial.println("Invalid command format");
    return;
  }
  
  String cmdType = command.substring(0, firstColon);
  
  //handle each command type
  if (cmdType.equals("NUM_SERVOS")) {
    //set number of servos
    if (firstColon < command.length() - 1) {
      int numServos = command.substring(firstColon + 1).toInt();
      setNumServos(numServos);
    }
  }
  else if (cmdType.equals("GSF")) {
    //set global smoothing factor
    if (firstColon < command.length() - 1) {
      float factor = command.substring(firstColon + 1).toFloat();
      setGlobalSmoothing(factor);
    }
  }
  else if (cmdType.equals("MA")) {
    //set master angle (all servos)
    if (firstColon < command.length() - 1) {
      float angle = command.substring(firstColon + 1).toFloat();
      setMasterAngle(angle);
    }
  }
  else if (cmdType.equals("SA")) {
    //set single servo angle
    int secondColon = command.indexOf(':', firstColon + 1);
    if (secondColon > firstColon && secondColon < command.length() - 1) {
      int servoId = command.substring(firstColon + 1, secondColon).toInt();
      float angle = command.substring(secondColon + 1).toFloat();
      setServoAngle(servoId, angle);
    }
  }
  else if (cmdType.equals("SF")) {
    //servo-specific smoothing (ignored)
    Serial.println("SF command received (ignored - using global smoothing only)");
  }
  else {
    Serial.print("Unknown command type: ");
    Serial.println(cmdType);
  }
}

void setNumServos(int numServos) {
  //validate range
  if (numServos > 0 && numServos <= MAX_SERVOS) {
    activeNumServos = numServos;
    
    //initialize any newly active servos
    for (uint8_t i = 0; i < activeNumServos; i++) {
      if (i >= activeNumServos) {
        pca.setPWM(i, 0, angleToPulse(90));
      }
    }
    
    Serial.print("Number of active servos set to ");
    Serial.println(activeNumServos);
  } else {
    Serial.print("Invalid number of servos. Valid range: 1-");
    Serial.println(MAX_SERVOS);
  }
}

void setGlobalSmoothing(float factor) {
  //validate range
  if (factor >= 0.0 && factor <= 1.0) {
    smoothingFactor = factor;
    Serial.print("Global smoothing factor set to ");
    Serial.println(smoothingFactor);
  } else {
    Serial.println("Invalid smoothing factor. Must be between 0.0 and 1.0");
  }
}

void setMasterAngle(float angle) {
  //validate angle range
  if (angle >= 0 && angle <= 180) {
    //set target angle for all active servos
    for (uint8_t i = 0; i < activeNumServos; i++) {
      servoStates[i].targetAngle = angle;
    }
    
    //resume motion if stopped
    isStopped = false;
    
    Serial.print("All servos target set to ");
    Serial.println(angle);
  } else {
    Serial.println("Invalid angle value. Must be between 0 and 180");
  }
}

void setServoAngle(int servoId, float angle) {
  //validate servo ID and angle
  if (servoId >= 0 && servoId < activeNumServos && angle >= 0 && angle <= 180) {
    //set target angle for a single servo
    servoStates[servoId].targetAngle = angle;
    
    //resume motion if stopped
    isStopped = false;
    
    Serial.print("Servo ");
    Serial.print(servoId);
    Serial.print(" target set to ");
    Serial.println(angle);
  } else {
    if (servoId < 0 || servoId >= activeNumServos) {
      Serial.print("Invalid servo ID. Valid range: 0-");
      Serial.println(activeNumServos - 1);
    } else {
      Serial.println("Invalid angle value. Must be between 0 and 180");
    }
  }
}

void updateServos() {
  //update each active servo based on its current state
  for (uint8_t i = 0; i < activeNumServos; i++) {
    //apply smoothing algorithm
    servoStates[i].currentAngle = (servoStates[i].targetAngle * smoothingFactor) + 
                                 (servoStates[i].currentAngle * (1.0 - smoothingFactor));
    
    //only send commands to the servo if the angle has changed significantly
    if (abs(servoStates[i].currentAngle - servoStates[i].lastSentAngle) > 0.1) {
      //calculate pulse width and send to servo
      uint16_t pulse = angleToPulse(servoStates[i].currentAngle);
      pca.setPWM(i, 0, pulse);
      
      //update last sent angle
      servoStates[i].lastSentAngle = servoStates[i].currentAngle;
    }
  }
}

uint16_t angleToPulse(float angle) {
  //ensure angle is within 0-180 range
  angle = constrain(angle, 0, 180);
  
  //map angle to pulse width
  return map(angle, 0, 180, SERVO_MIN, SERVO_MAX);
}
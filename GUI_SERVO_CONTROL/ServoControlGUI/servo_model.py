import json
import time
import serial
import serial.tools.list_ports

class ServoModel:
    #GLOBAL INFORMATION-----------------------------------------------------
    #configure servo information (will need to add pin numbers in future) 
    #you can add/remove servos here
    SERVO_CONFIG = [
        {"id": 0, "name": "Servo 1", "default_value": 90},
        {"id": 1, "name": "Servo 2", "default_value": 90},
        {"id": 2, "name": "Servo 3", "default_value": 90},
        {"id": 3, "name": "Servo 4", "default_value": 90},
        {"id": 4, "name": "Servo 5", "default_value": 90}
    ]
    
    #serial connection parameters
    SERIAL_BAUDRATE = 115200 #default
    THROTTLE_DELAY = 0.001 #delay between GUI control and servo response
    DEFAULT_DELAY_MS = 500 #default duration between recorded sequence steps (is adjustable in GUI)
    
    #class specific variables------------------------------------------------
    def __init__(self):
        #connection state
        self.serial_connection = None #serial object
        self.status = "Disconnected" #text display of connection status
        
        #sequence data/control
        self.sequence = [] #saved into json file
        self.sequence_playing = False
        self.sequence_thread = None
        
        #callback for external logging
        self.log_callback = None
    
    #set custom log callbacks for logging messages; 
    #assuming callback argument is a function that takes a 'message' as input i.e callback(message)
    def set_log_callback(self, callback):
        self.log_callback = callback
    
    #log the message to the custom callback
    def log_message(self, message):
        if self.log_callback:
            self.log_callback(message) #callback(message) 
    
    #check if connection is established
    def is_connected(self):
        return self.serial_connection is not None and self.serial_connection.is_open

    #find available serial ports on current device to display and choose
    def find_available_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if not ports:
            self.log_message("No serial ports found")

        return ports
    
    #connect to specified port (i.e COM3, COM4)
    #returns boolean if connection was successful or not
    def connect_to_serial(self, port):
        if not port:
            self.log_message("No port selected")
            return False
        
        try:
            #create serial object
            self.serial_connection = serial.Serial(port, self.SERIAL_BAUDRATE, timeout=1) 
            time.sleep(2)
            
            #log connection status
            self.status = f"Connected to {port}"
            self.log_message(f"Connected to {port}")
            return True #return connection status as True
            
        except Exception as e:
            #log exception
            self.log_message(f"Connection error: {str(e)}")
            self.serial_connection = None #serial object back to None
            return False #return connection status as False
    
    #disconnect from serial port to prevent unwanted GUI input being sent to servos
    def disconnect_from_serial(self):
        #close connection if open
        if self.is_connected():
            self.serial_connection.close()
        
        #reset serial parameters
        self.serial_connection = None
        self.status = "Disconnected"
        self.log_message("Disconnected from serial port") #log
        return True #indicate success
    
    #send command to serial port for esp listening code
    #boolean to indicate success of command sent
    def send_to_serial(self, command, log_message=None):
        if not self.is_connected():
            return False #cant send if not connected to serial port

        #handle command transmission    
        try:
            full_command = f"{command}\n"
            self.serial_connection.write(full_command.encode('utf-8'))
            
            if log_message:
                self.log_message(log_message)
                
            #optionally wait for response from esp if needed
            # time.sleep(0.1)
            # if self.serial_connection.in_waiting:
            #     response = self.serial_connection.readline().decode('utf-8').strip()
            #     self.log_message(f"ESP32: {response}")
            
            return True
            
        except Exception as e:
            self.log_message(f"Error sending command: {str(e)}")
            return False
    
    #sending signal from master control (all servos move to master orientation from current position)
    #boolean to indicate success
    def send_master_position(self, value): 
        return self.send_to_serial(f"A:{value}", f"Sent position to all servos: {value}°")

    #sending signal from individual control(s) 
    #(specified servo index/indicies to move)
    #boolean to indicate success
    def send_servo_position(self, servo_id, value):
        return self.send_to_serial(f"S:{servo_id}:{value}", f"Sent position to servo {servo_id}: {value}°")
    
    #saving recorded sequences into json file with format:
    # servo_x = {"id": <>, "name": <>, "position": <> }
    # servos_state_x = {"servos": [servo_1, servo_2,... servo_n], "delay": <ms> }
    # final_json format = [ servos_state_1, servos_state_2,... servos_state_n ]
    #stored into the self.sequence list; boolean to indicate success
    def save_sequence(self, filepath):
        if not self.sequence or not filepath:
            return False
        
        #open file path
        try:
            with open(filepath, 'w') as file:
                json.dump(self.sequence, file, indent=2) #save as json file
            
            self.log_message(f"Sequence saved to {filepath}")
            return True
        
        except Exception as e:
            self.log_message(f"Error saving sequence: {str(e)}")
            return False
    
    #loading saved json sequences, assuming its saved in the format above
    #boolean to indicate success
    def load_sequence(self, filepath):
        if not filepath:
            return False
        
        #open file path
        try:
            with open(filepath, 'r') as file:
                loaded_sequence = json.load(file)
            
            #validate structure, ensuring it is a list, but we will assume it will always be
            # if not isinstance(loaded_sequence, list):
            #     raise ValueError("Invalid sequence format")
            # for state in loaded_sequence:
            #     if not isinstance(state, dict) or "servos" not in state or "delay" not in state:
            #         raise ValueError("Invalid step format in sequence")
                
            #     for servo in state["servos"]:
            #         if not all(key in servo for key in ["id", "name", "position"]):
            #             raise ValueError("Invalid servo data in sequence")
            
            self.sequence = loaded_sequence
            self.log_message(f"Sequence loaded from {filepath}")
            
            return True
                
        except Exception as e:
            self.log_message(f"Error loading sequence: {str(e)}")
            return False
    
    #add state to end of current sequence
    #boolean to indicate success
    def add_sequence_step(self, servo_positions, delay):

        state = {
            "servos": servo_positions, #list of all n servos used (n dictionaries)
            "delay": delay #its current delay input
        }
        
        self.sequence.append(state)
        
        #log
        servo_text = ", ".join([f"{s['name']}: {s['position']}°" for s in servo_positions])
        self.log_message(f"Recorded step {self.get_sequence_length()}: {servo_text}, Delay: {delay}ms")
        
        return True
    
    #remove individual selected sequence step
    #boolean to indicate success
    def remove_sequence_step(self, index):
        if 0 <= index < len(self.sequence):
            self.sequence.pop(index)
            self.log_message(f"Removed step {index + 1}")
            return True
        
        return False
    
    #clear the entire current sequences
    def clear_sequence(self):
        self.sequence = [] #reset list
        self.log_message("Sequence cleared")
        return True
        
    def get_sequence_length(self):
        return len(self.sequence)
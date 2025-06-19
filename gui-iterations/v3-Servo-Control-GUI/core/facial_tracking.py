#facial tracking system for eye servo control with mediapipe

import cv2
import mediapipe as mp
import random
import time

class FacialTracker:
    #manages face detection and servo position calculations for eye tracking
    def __init__(self, state_manager, serial_connection, log_callback):
        self.state = state_manager
        self.serial_connection = serial_connection
        self.log_callback = log_callback
        
        #mediapipe face detection setup
        self.mp_face_detection = mp.solutions.face_detection
        self.mp_drawing = mp.solutions.drawing_utils
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0,  #short range model for better performance
            min_detection_confidence=0.5
        )
        
        #tracking state variables
        self.is_tracking = False
        self.detected_faces = []
        self.current_target_index = 0
        self.last_switch_time = time.time()
        self.switch_interval = 0  #will be set randomly
        
        #no face timer variables for default reset
        self.no_face_timer_start = None
        self.no_face_timeout_duration = 0  #will be set randomly
        self.is_returning_to_default = False
        
        #smoothing variables to prevent servo jumps
        self.previous_horizontal = None
        self.previous_vertical = None
        self.max_change_per_frame = 15  #maximum pulse width change per frame
        
        #camera dimensions - will be set when tracking starts
        self.camera_width = 320
        self.camera_height = 240
    
    #start facial tracking with given camera dimensions
    def start_tracking(self, camera_width, camera_height):
        self.is_tracking = True
        self.camera_width = camera_width
        self.camera_height = camera_height
        
        #initialise previous positions to current servo positions
        h_config = self.state.get_component_config("eye_horizontal")
        v_config = self.state.get_component_config("eye_vertical")
        self.previous_horizontal = h_config["current_position"]
        self.previous_vertical = v_config["current_position"]
        
        #set initial random switch interval
        self._set_random_switch_interval()
        
        #reset timer variables
        self.no_face_timer_start = None
        self.is_returning_to_default = False
        
        self.log_callback("facial tracking started")
    
    #stop facial tracking and return eyes to default positions
    def stop_tracking(self):
        self.is_tracking = False
        self.detected_faces = []
        self.current_target_index = 0
        
        #reset timer variables
        self.no_face_timer_start = None
        self.is_returning_to_default = False
        
        #return eyes to default positions
        h_config = self.state.get_component_config("eye_horizontal")
        v_config = self.state.get_component_config("eye_vertical")
        
        self._move_servo_smooth("eye_horizontal", h_config["default_position"])
        self._move_servo_smooth("eye_vertical", v_config["default_position"])
        
        self.log_callback("facial tracking stopped - eyes returned to default")
    
    #process camera frame for face detection and servo control
    def process_frame(self, frame):
        if not self.is_tracking:
            return frame
        
        #convert frame to rgb for mediapipe processing
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_detection.process(rgb_frame)
        
        #clear previous face detections
        self.detected_faces = []
        
        #process detected faces
        if results.detections:
            for detection in results.detections:
                #get bounding box coordinates
                bbox = detection.location_data.relative_bounding_box
                
                #convert relative coordinates to pixel coordinates
                x = int(bbox.xmin * self.camera_width)
                y = int(bbox.ymin * self.camera_height)
                width = int(bbox.width * self.camera_width)
                height = int(bbox.height * self.camera_height)
                
                #calculate face center point
                center_x = x + width // 2
                center_y = y + height // 2
                
                #store face data
                face_data = {
                    'bbox': (x, y, width, height),
                    'center': (center_x, center_y),
                    'confidence': detection.score[0]
                }
                self.detected_faces.append(face_data)
        
        #handle face detection and default reset logic
        if self.detected_faces:
            #faces detected - cancel any return to default and resume tracking
            self._cancel_default_reset()
            self._handle_face_switching()
            self._move_eyes_to_target()
            frame = self._draw_tracking_box(frame)
        else:
            #no faces detected - handle timer for default reset
            self._handle_no_face_timer()
        
        return frame
    
    #handle timer when no faces are detected
    def _handle_no_face_timer(self):
        current_time = time.time()
        
        #start timer if not already started
        if self.no_face_timer_start is None and not self.is_returning_to_default:
            self.no_face_timer_start = current_time
            self._set_random_no_face_timeout()
            
        #check if timer expired and start return to default
        elif (self.no_face_timer_start is not None and 
              not self.is_returning_to_default and 
              (current_time - self.no_face_timer_start) > self.no_face_timeout_duration):
            
            self._start_return_to_default()
        
        #continue returning to default if in progress
        elif self.is_returning_to_default:
            self._continue_return_to_default()
    
    #cancel default reset when faces reappear
    def _cancel_default_reset(self):
        if self.no_face_timer_start is not None or self.is_returning_to_default:
            self.no_face_timer_start = None
            self.is_returning_to_default = False
    
    #set random timeout duration for no face detection
    def _set_random_no_face_timeout(self):
        self.no_face_timeout_duration = random.uniform(2.0, 4.0)  #reset after 2-4 seconds
    
    #start returning eyes to default positions
    def _start_return_to_default(self):
        self.is_returning_to_default = True
        self.no_face_timer_start = None
        self.log_callback("no faces detected - returning eyes to default position")
    
    #continue smooth return to default positions
    def _continue_return_to_default(self):
        h_config = self.state.get_component_config("eye_horizontal")
        v_config = self.state.get_component_config("eye_vertical")
        
        #move towards default positions using existing smoothing
        self._move_servo_smooth("eye_horizontal", h_config["default_position"])
        self._move_servo_smooth("eye_vertical", v_config["default_position"])
        
        #check if reached default positions
        current_h = h_config["current_position"]
        current_v = v_config["current_position"]
        default_h = h_config["default_position"]
        default_v = v_config["default_position"]
        
        #stop returning when close to default positions
        if abs(current_h - default_h) <= 2 and abs(current_v - default_v) <= 2:
            self.is_returning_to_default = False
    
    #handle switching between detected faces based on random timing
    def _handle_face_switching(self):
        current_time = time.time()
        
        #check if enough time has passed to switch faces
        if len(self.detected_faces) > 1 and (current_time - self.last_switch_time) > self.switch_interval:
            #randomly select different face
            available_indices = list(range(len(self.detected_faces)))
            if self.current_target_index in available_indices:
                available_indices.remove(self.current_target_index)
            
            if available_indices:
                self.current_target_index = random.choice(available_indices)
                self.last_switch_time = current_time
                self._set_random_switch_interval()
                
                self.log_callback(f"switched focus to face {self.current_target_index + 1}")
        
        #ensure target index is valid
        if self.current_target_index >= len(self.detected_faces):
            self.current_target_index = 0
    
    #set random interval for next face switch
    def _set_random_switch_interval(self):
        self.switch_interval = random.uniform(2.0, 8.0)  #switch every 2-8 seconds
    
    #move eyes to currently targeted face
    def _move_eyes_to_target(self):
        if not self.detected_faces or self.current_target_index >= len(self.detected_faces):
            return
        
        target_face = self.detected_faces[self.current_target_index]
        center_x, center_y = target_face['center']
        
        #calculate pulse widths for horizontal and vertical movement
        horizontal_pulse = self._calculate_horizontal_pulse(center_x)
        vertical_pulse = self._calculate_vertical_pulse(center_y)
        
        #apply smoothing and move servos
        self._move_servo_smooth("eye_horizontal", horizontal_pulse)
        self._move_servo_smooth("eye_vertical", vertical_pulse)
    
    #calculate horizontal servo pulse width from face x coordinate
    def _calculate_horizontal_pulse(self, face_x):
        h_config = self.state.get_component_config("eye_horizontal")
        
        #calculate offset from camera center
        camera_center_x = self.camera_width / 2
        x_offset = face_x - camera_center_x
        
        #convert to ratio (-1.0 to +1.0)
        x_ratio = x_offset / (self.camera_width / 2)
        
        #calculate servo pulse width
        servo_range_half = (h_config["pulse_max"] - h_config["pulse_min"]) / 2
        horizontal_pulse = h_config["default_position"] + (x_ratio * servo_range_half)
        
        #ensure within bounds
        horizontal_pulse = max(h_config["pulse_min"], min(h_config["pulse_max"], horizontal_pulse))
        
        return int(horizontal_pulse)
    
    #calculate vertical servo pulse width from face y coordinate
    def _calculate_vertical_pulse(self, face_y):
        v_config = self.state.get_component_config("eye_vertical")
        
        #calculate offset from camera center
        camera_center_y = self.camera_height / 2
        y_offset = face_y - camera_center_y
        
        #convert to ratio (-1.0 to +1.0)
        y_ratio = y_offset / (self.camera_height / 2)
        
        #calculate servo pulse width
        servo_range_half = (v_config["pulse_max"] - v_config["pulse_min"]) / 2
        vertical_pulse = v_config["default_position"] + (y_ratio * servo_range_half)
        
        #ensure within bounds
        vertical_pulse = max(v_config["pulse_min"], min(v_config["pulse_max"], vertical_pulse))
        
        return int(vertical_pulse)
    
    #move servo with smoothing to prevent instant jumps
    def _move_servo_smooth(self, component_name, target_pulse):
        config = self.state.get_component_config(component_name)
        current_pulse = config["current_position"]
        
        #get previous position for smoothing
        if component_name == "eye_horizontal":
            previous_pulse = self.previous_horizontal if self.previous_horizontal is not None else current_pulse
        else:
            previous_pulse = self.previous_vertical if self.previous_vertical is not None else current_pulse
        
        #calculate change and limit it
        change = target_pulse - previous_pulse
        if abs(change) > self.max_change_per_frame:
            if change > 0:
                new_pulse = previous_pulse + self.max_change_per_frame
            else:
                new_pulse = previous_pulse - self.max_change_per_frame
        else:
            new_pulse = target_pulse
        
        #ensure within component bounds
        new_pulse = max(config["pulse_min"], min(config["pulse_max"], new_pulse))
        
        #update servo position if within bounds and different from current
        if config["pulse_min"] <= new_pulse <= config["pulse_max"] and new_pulse != current_pulse:
            #send command to servo
            if self.serial_connection and self.serial_connection.is_connected:
                servo_index = config["index"]
                if self.serial_connection.send_command(f"SP:{servo_index}:{new_pulse}"):
                    #update state manager
                    self.state.update_servo_position(component_name, new_pulse)
        
        #update previous position for next frame
        if component_name == "eye_horizontal":
            self.previous_horizontal = new_pulse
        else:
            self.previous_vertical = new_pulse
    
    #draw bounding box around currently tracked face
    def _draw_tracking_box(self, frame):
        if not self.detected_faces or self.current_target_index >= len(self.detected_faces):
            return frame
        
        target_face = self.detected_faces[self.current_target_index]
        x, y, width, height = target_face['bbox']
        confidence = target_face['confidence']
        
        #draw green bounding box for tracked face
        cv2.rectangle(frame, (x, y), (x + width, y + height), (0, 255, 0), 2)
        
        #draw center point
        center_x, center_y = target_face['center']
        cv2.circle(frame, (center_x, center_y), 5, (0, 255, 0), -1)
        
        #draw confidence text
        confidence_text = f"tracking: {confidence:.2f}"
        cv2.putText(frame, confidence_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        #draw face count info
        face_count_text = f"faces: {len(self.detected_faces)}"
        cv2.putText(frame, face_count_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return frame
    
    #check if currently tracking faces
    def is_tracking_active(self):
        return self.is_tracking
    
    #get current tracking statistics
    def get_tracking_stats(self):
        return {
            'is_tracking': self.is_tracking,
            'faces_detected': len(self.detected_faces),
            'current_target': self.current_target_index + 1 if self.detected_faces else 0,
            'switch_interval': self.switch_interval,
            'returning_to_default': self.is_returning_to_default
        }
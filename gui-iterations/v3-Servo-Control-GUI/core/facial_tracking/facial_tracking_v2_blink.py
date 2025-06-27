import cv2
import mediapipe as mp
import random
import time
import threading

#manages face detection and servo position calculations for eye tracking
class FacialTracker:
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
        
        #confidence threshold for face tracking (prevents false positives)
        self.confidence_threshold = 0.85  #only track faces with 85% confidence or higher
        
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
        
        #incremental calculation parameters
        self.tracking_alpha = 0.5  #adjustment factor for face tracking
        self.return_alpha = 0.5  #adjustment factor for returning to default
        self.movement_threshold = 10  #minimum pixel movement to trigger servo adjustment
        
        #previous face position for change detection
        self.previous_face_center_x = None
        self.previous_face_center_y = None
        
        #smoothing variables to prevent servo jumps
        self.previous_horizontal = None
        self.previous_vertical = None
        self.max_change_per_frame = 15  #maximum pulse width change per frame
        
        #camera dimensions - will be set when tracking starts (automatically set and found when finding camera devices)
        self.camera_width = 320
        self.camera_height = 240
        
        #blinking animation variables
        self.blink_thread = None
        self.blink_interval = 0  #will be set randomly between 6-13 seconds
        self.last_blink_time = 0
        
    #get eye component names from head group positions
    def _get_eye_component_names(self):
        head_components = self.state.get_component_group("head")
        if len(head_components) >= 2:
            return head_components[0], head_components[1]  #horizontal, vertical
        else:
            #fallback to default names if head group insufficient
            return "eye_horizontal", "eye_vertical"
    
    #get eyelid component names from head group positions
    def _get_eyelid_component_names(self):
        head_components = self.state.get_component_group("head")
        if len(head_components) >= 4:
            return head_components[2], head_components[3]  #left eyelid, right eyelid
        else:
            #fallback to default names if head group insufficient
            return "left_eyelid", "right_eyelid"
    
    #execute synchronized blink animation sequence
    def _execute_blink_sequence(self):
        left_eyelid_name, right_eyelid_name = self._get_eyelid_component_names()
        left_config = self.state.get_component_config(left_eyelid_name)
        right_config = self.state.get_component_config(right_eyelid_name)
        
        #move eyelids to closed positions (left to min, right to max)
        left_servo_index = left_config["index"]
        left_close_pulse = left_config["pulse_min"]
        self.serial_connection.send_command(f"SP:{left_servo_index}:{left_close_pulse}")
        self.state.update_servo_position(left_eyelid_name, left_close_pulse)
        
        #small delay for synchronized movement
        time.sleep(0.01)  #10ms delay
        
        right_servo_index = right_config["index"]
        right_close_pulse = right_config["pulse_max"]
        self.serial_connection.send_command(f"SP:{right_servo_index}:{right_close_pulse}")
        self.state.update_servo_position(right_eyelid_name, right_close_pulse)
        
        #wait before opening eyelids
        time.sleep(0.2)  #200ms blink duration
        
        #return eyelids to default positions
        left_default_pulse = left_config["default_position"]
        self.serial_connection.send_command(f"SP:{left_servo_index}:{left_default_pulse}")
        self.state.update_servo_position(left_eyelid_name, left_default_pulse)
        
        #small delay for synchronized movement
        time.sleep(0.01)  #10ms delay
        
        right_default_pulse = right_config["default_position"]
        self.serial_connection.send_command(f"SP:{right_servo_index}:{right_default_pulse}")
        self.state.update_servo_position(right_eyelid_name, right_default_pulse)
    
    #set random interval for next blink animation
    def _set_random_blink_interval(self):
        self.blink_interval = random.uniform(6.0, 13.0)  #blink every 6-13 seconds
    
    #background thread for blink animation timing
    def _blink_timer_thread(self):
        self._set_random_blink_interval()
        self.last_blink_time = time.time()
        
        while self.is_tracking:
            current_time = time.time()
            
            #check if blink interval has elapsed
            if (current_time - self.last_blink_time) >= self.blink_interval:
                #execute blink animation if serial connection available
                if self.serial_connection and self.serial_connection.is_connected:
                    self._execute_blink_sequence()
                
                #set new random interval and reset timer
                self._set_random_blink_interval()
                self.last_blink_time = current_time
            
            #check every 100ms to avoid excessive cpu usage
            time.sleep(0.1)
    
    #start facial tracking with given camera dimensions
    def start_tracking(self, camera_width, camera_height):
        self.is_tracking = True
        self.camera_width = camera_width
        self.camera_height = camera_height
        
        #get current eye component names
        h_component, v_component = self._get_eye_component_names()
        
        #initialise previous positions to current servo positions
        h_config = self.state.get_component_config(h_component)
        v_config = self.state.get_component_config(v_component)
        self.previous_horizontal = h_config["current_position"]
        self.previous_vertical = v_config["current_position"]
        
        #reset previous face positions for change detection
        self.previous_face_center_x = None
        self.previous_face_center_y = None
        
        #set initial random switch interval
        self._set_random_switch_interval()
        
        #reset timer variables
        self.no_face_timer_start = None
        self.is_returning_to_default = False
        
        #start blink animation thread
        self.blink_thread = threading.Thread(target=self._blink_timer_thread, daemon=True)
        self.blink_thread.start()
        
        self.log_callback(f"facial tracking started using {h_component} and {v_component}")
        self.log_callback(f"confidence threshold set to {self.confidence_threshold:.0%}")
        self.log_callback(f"incremental tracking with alpha {self.tracking_alpha}")
        self.log_callback("blink animation started")
    
    #stop facial tracking and return eyes to default positions
    def stop_tracking(self):
        self.is_tracking = False
        self.detected_faces = []
        self.current_target_index = 0
        
        #stop blink animation thread
        if self.blink_thread and self.blink_thread.is_alive():
            self.blink_thread.join(timeout=1.0)
        self.blink_thread = None
        
        #reset timer variables
        self.no_face_timer_start = None
        self.is_returning_to_default = False
        
        #reset previous face positions
        self.previous_face_center_x = None
        self.previous_face_center_y = None
        
        #get current eye component names and return to defaults
        h_component, v_component = self._get_eye_component_names()
        h_config = self.state.get_component_config(h_component)
        v_config = self.state.get_component_config(v_component)
        
        self._move_servo_smooth(h_component, h_config["default_position"])
        self._move_servo_smooth(v_component, v_config["default_position"])
        
        #return eyelids to default positions
        left_eyelid_name, right_eyelid_name = self._get_eyelid_component_names()
        left_config = self.state.get_component_config(left_eyelid_name)
        right_config = self.state.get_component_config(right_eyelid_name)
        
        if self.serial_connection and self.serial_connection.is_connected:
            left_servo_index = left_config["index"]
            left_default_pulse = left_config["default_position"]
            self.serial_connection.send_command(f"SP:{left_servo_index}:{left_default_pulse}")
            self.state.update_servo_position(left_eyelid_name, left_default_pulse)
            
            right_servo_index = right_config["index"]
            right_default_pulse = right_config["default_position"]
            self.serial_connection.send_command(f"SP:{right_servo_index}:{right_default_pulse}")
            self.state.update_servo_position(right_eyelid_name, right_default_pulse)
        
        self.log_callback("facial tracking stopped - eyes returned to default")
        self.log_callback("blink animation stopped - eyelids returned to default")
    
    #process camera frame for face detection and servo control
    def process_frame(self, frame):
        if not self.is_tracking:
            return frame
        
        #convert frame to rgb for mediapipe processing
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_detection.process(rgb_frame)
        
        #clear previous face detections
        self.detected_faces = []
        
        #process detected faces with confidence filtering
        if results.detections:
            for detection in results.detections:
                #check confidence threshold before processing face
                face_confidence = detection.score[0]
                if face_confidence < self.confidence_threshold:
                    continue  #skip low confidence detections
                
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
                
                #store face data for high confidence detections only
                face_data = {
                    'bbox': (x, y, width, height),
                    'center': (center_x, center_y),
                    'confidence': face_confidence
                }
                self.detected_faces.append(face_data)
        
        #handle face detection and default reset logic
        if self.detected_faces:
            #faces detected - cancel any return to default and resume tracking
            self._cancel_default_reset()
            self._handle_face_switching()
            self._move_eyes_to_target_incremental()
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
            self._continue_return_to_default_incremental()
    
    #cancel default reset when faces reappear
    def _cancel_default_reset(self):
        if self.no_face_timer_start is not None or self.is_returning_to_default:
            self.no_face_timer_start = None
            self.is_returning_to_default = False
            #reset previous face positions to allow immediate tracking
            self.previous_face_center_x = None
            self.previous_face_center_y = None
    
    #set random timeout duration for no face detection
    def _set_random_no_face_timeout(self):
        self.no_face_timeout_duration = random.uniform(4.0, 6.0)  #reset after 4-6 seconds
    
    #start returning eyes to default positions
    def _start_return_to_default(self):
        self.is_returning_to_default = True
        self.no_face_timer_start = None
        self.log_callback("no faces detected - returning eyes to default position")
    
    #continue incremental return to default positions
    def _continue_return_to_default_incremental(self):
        h_component, v_component = self._get_eye_component_names()
        h_config = self.state.get_component_config(h_component)
        v_config = self.state.get_component_config(v_component)
        
        #calculate incremental movement toward default positions
        current_h = h_config["current_position"]
        current_v = v_config["current_position"]
        default_h = h_config["default_position"]
        default_v = v_config["default_position"]
        
        #horizontal incremental adjustment
        h_difference = default_h - current_h
        h_adjustment = h_difference * self.return_alpha
        new_h_pulse = current_h + h_adjustment
        
        #vertical incremental adjustment
        v_difference = default_v - current_v
        v_adjustment = v_difference * self.return_alpha
        new_v_pulse = current_v + v_adjustment
        
        #apply constraints
        new_h_pulse = max(h_config["pulse_min"], min(h_config["pulse_max"], new_h_pulse))
        new_v_pulse = max(v_config["pulse_min"], min(v_config["pulse_max"], new_v_pulse))
        
        #move servos incrementally toward default
        self._move_servo_smooth(h_component, int(new_h_pulse))
        self._move_servo_smooth(v_component, int(new_v_pulse))
        
        #check if reached default positions (within 2 pulse units)
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
                
                #reset previous face positions to allow immediate adjustment to new target
                self.previous_face_center_x = None
                self.previous_face_center_y = None
                
                self.log_callback(f"switched focus to face {self.current_target_index + 1}")
        
        #ensure target index is valid
        if self.current_target_index >= len(self.detected_faces):
            self.current_target_index = 0
    
    #set random interval for next face switch
    def _set_random_switch_interval(self):
        self.switch_interval = random.uniform(8.0, 16.0)  #switch every 8-16 seconds
    
    #move eyes to currently targeted face using incremental calculation
    def _move_eyes_to_target_incremental(self):
        if not self.detected_faces or self.current_target_index >= len(self.detected_faces):
            return
        
        target_face = self.detected_faces[self.current_target_index]
        center_x, center_y = target_face['center']
        
        #check if face position changed significantly
        face_moved = self._check_face_movement(center_x, center_y)
        
        if face_moved:
            #get current eye component names
            h_component, v_component = self._get_eye_component_names()
            
            #calculate incremental pulse widths for horizontal and vertical movement
            horizontal_pulse = self._calculate_horizontal_pulse_incremental(center_x, h_component)
            vertical_pulse = self._calculate_vertical_pulse_incremental(center_y, v_component)
            
            #apply smoothing and move servos
            self._move_servo_smooth(h_component, horizontal_pulse)
            self._move_servo_smooth(v_component, vertical_pulse)
            
            #update previous face positions for next frame
            self.previous_face_center_x = center_x
            self.previous_face_center_y = center_y
    
    #check if face has moved enough to warrant servo adjustment
    def _check_face_movement(self, current_x, current_y):
        #if no previous position, always consider it moved
        if self.previous_face_center_x is None or self.previous_face_center_y is None:
            return True
        
        #calculate movement distance
        x_movement = abs(current_x - self.previous_face_center_x)
        y_movement = abs(current_y - self.previous_face_center_y)
        
        #check if movement exceeds threshold
        return x_movement > self.movement_threshold or y_movement > self.movement_threshold
    
    #calculate horizontal servo pulse width from face x coordinate using incremental method
    def _calculate_horizontal_pulse_incremental(self, face_x, component_name):
        h_config = self.state.get_component_config(component_name)
        
        #calculate offset from camera center
        camera_center_x = self.camera_width / 2
        face_offset_from_center = face_x - camera_center_x
        
        #get current servo position
        current_servo_pulse = h_config["current_position"]
        
        #calculate incremental adjustment with orientation correction
        pulse_adjustment = -face_offset_from_center * self.tracking_alpha
        new_horizontal_pulse = current_servo_pulse + pulse_adjustment
        
        #apply component constraints
        new_horizontal_pulse = max(h_config["pulse_min"], min(h_config["pulse_max"], new_horizontal_pulse))
        
        return int(new_horizontal_pulse)
    
    #calculate vertical servo pulse width from face y coordinate using incremental method
    def _calculate_vertical_pulse_incremental(self, face_y, component_name):
        v_config = self.state.get_component_config(component_name)
        
        #calculate offset from camera center
        camera_center_y = self.camera_height / 2
        face_offset_from_center = face_y - camera_center_y
        
        #get current servo position
        current_servo_pulse = v_config["current_position"]
        
        #calculate incremental adjustment with orientation correction
        pulse_adjustment = -face_offset_from_center * self.tracking_alpha
        new_vertical_pulse = current_servo_pulse + pulse_adjustment
        
        #apply component constraints
        new_vertical_pulse = max(v_config["pulse_min"], min(v_config["pulse_max"], new_vertical_pulse))
        
        return int(new_vertical_pulse)
    
    #move servo with smoothing to prevent instant jumps
    def _move_servo_smooth(self, component_name, target_pulse):
        config = self.state.get_component_config(component_name)
        current_pulse = config["current_position"]
        
        #get previous position for smoothing based on component type
        h_component, v_component = self._get_eye_component_names()
        if component_name == h_component:
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
        
        #update previous position for next frame based on component type
        if component_name == h_component:
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
        
        #draw confidence text with threshold indicator
        confidence_text = f"tracking: {confidence:.2f}"
        cv2.putText(frame, confidence_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        #draw face count info for high confidence faces only
        face_count_text = f"faces: {len(self.detected_faces)}"
        cv2.putText(frame, face_count_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return frame
    
    #set confidence threshold for face tracking
    def set_confidence_threshold(self, threshold):
        if 0.0 <= threshold <= 1.0:
            self.confidence_threshold = threshold
            self.log_callback(f"confidence threshold updated to {threshold:.0%}")
            return True
        return False
    
    #set tracking alpha for incremental adjustments
    def set_tracking_alpha(self, alpha):
        if 0.0 < alpha <= 2.0:
            self.tracking_alpha = alpha
            self.log_callback(f"tracking alpha updated to {alpha}")
            return True
        return False
    
    #set movement threshold for change detection
    def set_movement_threshold(self, threshold):
        if threshold >= 0:
            self.movement_threshold = threshold
            self.log_callback(f"movement threshold updated to {threshold} pixels")
            return True
        return False
    
    #get current confidence threshold
    def get_confidence_threshold(self):
        return self.confidence_threshold
    
    #get current tracking alpha
    def get_tracking_alpha(self):
        return self.tracking_alpha
    
    #get current movement threshold
    def get_movement_threshold(self):
        return self.movement_threshold
    
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
            'returning_to_default': self.is_returning_to_default,
            'confidence_threshold': self.confidence_threshold,
            'tracking_alpha': self.tracking_alpha,
            'movement_threshold': self.movement_threshold
        }
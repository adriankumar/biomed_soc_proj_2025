import tkinter as tk
from tkinter import ttk
from core.state_manager import ServoState
from gui.sequence_system import SequenceManager
from hardware.esp_communication import SerialConnection
from gui.servo_controls import ServoControlsManager
from gui.command_interface import CommandTerminal, ConsoleLogger
from gui.sequence_system import SequenceRecorderWidget
from core.event_system import subscribe, Events, cleanup
import threading
import time

#Content switcher is the additional tools frame
class ContentSwitcher:
    #manages additional tools and content switching including eye display
    def __init__(self, parent, state, serial_connection, log_callback):
        self.frame = ttk.LabelFrame(parent, text="additional tools")
        self.state = state
        self.serial_connection = serial_connection
        self.log_callback = log_callback
        
        #content switching state
        self.selected_content = tk.StringVar()
        self.content_options = ["visualisation", "sequence recording", "eye display"]
        
        #sequence recording components
        self.sequence_recorder_widget = None
        self.sequence_manager = None
        
        #eye display components
        self.eye_display_widget = None
        
        #3d Visualisation components
        self.visualisation_widget = None
        self.ax = None
        self.scatter_dict = None
        self.fig = None
        self.canvas_obj = None
        self.canvas_widget = None
        self.coord_dict_3d = None
        
        self.streaming_active = False
        self.stream_thread = None
        
        self._create_ui()
    
    #set dependencies for sequence recording
    def set_sequence_dependencies(self, sequence_manager):
        self.sequence_manager = sequence_manager
    
    #create content switcher interface
    def _create_ui(self):
        selection_frame = ttk.Frame(self.frame)
        selection_frame.pack(fill="x", padx=15, pady=10)
        
        ttk.Label(selection_frame, text="select tool:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 8))
        
        self.selected_content.set(self.content_options[0])
        
        for option in self.content_options:
            display_name = option.replace("_", " ")
            ttk.Radiobutton(
                selection_frame, 
                text=display_name,
                variable=self.selected_content, 
                value=option,
                command=self._on_content_changed
            ).pack(side="left", padx=10, pady=2)
        
        #content container
        self.content_container = ttk.Frame(self.frame)
        self.content_container.pack(fill="both", expand=True, padx=15, pady=(5, 15))
        
        self._create_content_frame()
    
    #handle content selection change
    def _on_content_changed(self):
        self._hide_current_content()
        self._create_content_frame()
        
        selected = self.selected_content.get()
        self.log_callback(f"switched to {selected} tool")
    
    #hide current content
    def _hide_current_content(self):
        if self.sequence_recorder_widget and self.sequence_recorder_widget.is_visible():
            self.sequence_recorder_widget.hide()
        
        if self.eye_display_widget and self.eye_display_widget.is_visible():
            self.eye_display_widget.hide()
        
        for widget in self.content_container.winfo_children():
            if (widget != getattr(self.sequence_recorder_widget, 'frame', None) and 
                widget != getattr(self.eye_display_widget, 'frame', None)):
                widget.destroy()
    
    #create content frame based on selection
    def _create_content_frame(self):
        selected = self.selected_content.get()
        
        if selected == "visualisation":
            self._create_visualisation_placeholder()
        elif selected == "sequence recording":
            self._create_sequence_recording_content()
        elif selected == "eye display":
            self._create_eye_display_content()
        else:
            self._create_default_placeholder()
    
    #create sequence recording content
    def _create_sequence_recording_content(self):
        if not self.sequence_manager or not self.serial_connection:
            self._create_sequence_unavailable_placeholder()
            return
        
        if self.sequence_recorder_widget is None:
            self.sequence_recorder_widget = SequenceRecorderWidget(
                parent=self.content_container,
                sequence_manager=self.sequence_manager,
                serial_connection=self.serial_connection,
                log_callback=self.log_callback
            )
        
        self.sequence_recorder_widget.show()
    
    #create eye display content with facial tracking
    def _create_eye_display_content(self):
        if self.eye_display_widget is None:
            from gui.eye_display import EyeDisplayWidget
            
            self.eye_display_widget = EyeDisplayWidget(
                parent=self.content_container,
                state_manager=self.state,
                serial_connection=self.serial_connection,
                log_callback=self.log_callback
            )
        
        self.eye_display_widget.show()
    
    #create placeholder content
    # Visualisation for Pose Estimation throught the box plot
    def _create_visualisation_placeholder(self):
        from gui.pose_tracker import init_3d_plot
        from gui.pose_tracker import draw_selected_dots
        from gui.pose_tracker import update_3d_plot
        from gui.pose_tracker import calculate_left_shoulder_servo_1, calculate_left_shoulder_servo_2, calculate_left_shoulder_servo_3
        from gui.pose_tracker import calculate_left_elbow_servo_1, calculate_left_elbow_servo_2
        from gui.pose_tracker import left_hand_servo_thumb, left_hand_servo_index, left_hand_servo_middle, left_hand_servo_ring, left_hand_servo_pinky   
        from gui.pose_tracker import get_selected_coords_for_3d_plot
        from gui.pose_tracker import draw_selected_dots
        
        import cv2
        import mediapipe as mp
        import matplotlib.pyplot as plt
        import numpy as np
        import concurrent.futures
        
        # Init MediaPipe modules
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles
        mp_holistic = mp.solutions.holistic
        
        def stream_loop(ax, scatter_dict, canvas_obj):
            cap = cv2.VideoCapture(0)
            
            with mp_holistic.Holistic(
                model_complexity=1,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7
            ) as holistic:
            
  
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    last_print_time = time.time()  # Add this before the loop starts
                    
                    while cap.isOpened():
                        ret, frame = cap.read()
                        if not ret:
                            break

                        # Convert to RGB
                        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        image.flags.writeable = False
                        results = holistic.process(image)

                        # Convert back to BGR
                        image.flags.writeable = True
                        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                        
                        # Draw and get landmark coordinates
                        coord_dict = draw_selected_dots(image, results)
                        
                        self.coord_dict_3d = get_selected_coords_for_3d_plot(results)
                        
                        update_3d_plot(ax, scatter_dict, self.coord_dict_3d, canvas_obj)
                        
                
                        # Calculate angles in parallel
                        futures = [
                            executor.submit(calculate_left_shoulder_servo_1, self.coord_dict_3d ),
                            executor.submit(calculate_left_shoulder_servo_2, self.coord_dict_3d ),
                            executor.submit(calculate_left_shoulder_servo_3, self.coord_dict_3d ),
                            executor.submit(calculate_left_elbow_servo_1, self.coord_dict_3d ),
                            executor.submit(calculate_left_elbow_servo_2, self.coord_dict_3d ),
                            executor.submit(left_hand_servo_thumb, self.coord_dict_3d ),
                            executor.submit(left_hand_servo_index, self.coord_dict_3d ),
                            executor.submit(left_hand_servo_middle, self.coord_dict_3d ),
                            executor.submit(left_hand_servo_ring, self.coord_dict_3d ),
                            executor.submit(left_hand_servo_pinky, self.coord_dict_3d ),
                        ]
                        results_angles = [f.result() for f in futures]

                        # Unpack results as needed
                        (left_shoulder_servo_1, left_shoulder_servo_2, left_shoulder_servo_3,
                        left_elbow_servo_1, left_elbow_servo_2,
                        left_hand_servo_thumb_angle, left_hand_servo_index_angle,
                        left_hand_servo_middle_angle, left_hand_servo_ring_angle,
                        left_hand_servo_pinky_angle) = results_angles

                        # Inside while loop, after unpacking results
                        current_time = time.time()
                        if current_time - last_print_time >= 0.5:
                            print("___________________________________________________________________________________________________________________________________________________________________________________________________-")
                            """ print(f"Left Shoulder Servo 1 Angle: {left_shoulder_servo_1}, Left Shoulder Servo 2 Angle: {left_shoulder_servo_2}, Left Shoulder Servo 3 Angle: {left_shoulder_servo_3}") """
                            """print(f"Left Elbow Servo 1 Angle: {left_elbow_servo_1}, Left Elbow Servo 2 Angle: {left_elbow_servo_2}")"""
                            print(f"Thumb: {left_hand_servo_thumb_angle}, Index: {left_hand_servo_index_angle}, Middle: {left_hand_servo_middle_angle}, Ring: {left_hand_servo_ring_angle}, Pinky: {left_hand_servo_pinky_angle}") 
                            print("___________________________________________________________________________________________________________________________________________________________________________________________________-")
                            last_print_time = current_time
                    
                        # Show the annotated frame
                        cv2.imshow("Hand + Body Detector", image)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
            
            cap.release()
            cv2.destroyAllWindows()
            plt.ioff()
            plt.close()
                
        if self.visualisation_widget is None:
            
            self.fig, self.ax, self.scatter_dict, self.canvas_obj, self.canvas_widget = init_3d_plot(self.content_container)
            self.canvas_widget.pack(expand=True, fill="both")
            self.visualisation_widget = self.canvas_widget
            
            threading.Thread(
                target=stream_loop,
                args=(self.ax, self.scatter_dict, self.canvas_obj),
                daemon=True
            ).start()
 
                      
    
    def _create_sequence_unavailable_placeholder(self):
        self._create_placeholder("sequence recording unavailable", "red", "dependencies not initialised")
    
    def _create_default_placeholder(self):
        self._create_placeholder("TBI: unknown tool", "gray")
    
    def _create_placeholder(self, main_text, colour, detail_text=None):
        placeholder_frame = ttk.Frame(self.content_container)
        placeholder_frame.pack(expand=True, fill="both")
        
        center_frame = ttk.Frame(placeholder_frame)
        center_frame.pack(expand=True, fill="both")
        
        main_label = ttk.Label(
            center_frame, 
            text=main_text, 
            font=("Arial", 16, "italic"),
            foreground=colour,
            anchor="center"
        )
        main_label.pack(expand=True)
        
        if detail_text:
            detail_label = ttk.Label(
                center_frame, 
                text=detail_text, 
                font=("Arial", 10),
                foreground="gray",
                anchor="center"
            )
            detail_label.pack()
    
    #public interface methods
    def get_selected_content(self):
        return self.selected_content.get()
    
    def get_sequence_recorder_widget(self):
        return self.sequence_recorder_widget
    
    def is_sequence_recording_active(self):
        return (
            self.selected_content.get() == "sequence recording" and 
            self.sequence_recorder_widget is not None and 
            self.sequence_recorder_widget.is_visible()
        )
    
    def cleanup(self):
        if self.sequence_recorder_widget:
            pass  #cleanup handled by frame destruction
        
        if self.eye_display_widget:
            self.eye_display_widget.cleanup()


class ServoControlGUI:
    #main application window and controller
    def __init__(self, config_data):
        #initialise state and sequence managers
        self.state = ServoState(config_data)
        self.sequence_manager = SequenceManager(self.state)
        self.state.set_sequence_manager(self.sequence_manager)
        
        #create main window
        self.root = tk.Tk()
        self.root.title("servo control system")
        self.root.geometry("1400x1000")
        
        #component references
        self.serial_connection = None
        self.servo_controls = None
        self.content_switcher = None
        self.command_terminal = None
        self.console_logger = None
        
        self._create_ui()
        self._setup_sequence_integration()
        self._log_startup_info()
        
        #subscribe to connection events for cleanup tracking
        subscribe([Events.CONNECTION_CHANGED], self._on_connection_changed)
        
        #bind cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
    
    #create main user interface
    def _create_ui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        #serial connection frame (top)
        self.serial_connection = SerialConnection(main_frame, self._log_message)
        self.serial_connection.frame.pack(fill="x", pady=(0, 5))
        
        #main content area
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True, pady=5)
        
        content_frame.columnconfigure(0, weight=0)  #servo controls natural width
        content_frame.columnconfigure(1, weight=1)  #content switcher expands
        content_frame.rowconfigure(0, weight=1)
        
        #servo controls (left)
        self.servo_controls = ServoControlsManager(
            content_frame, 
            self.state, 
            self.serial_connection.send_command
        )
        self.servo_controls.frame.grid(row=0, column=0, sticky="nw", padx=(0, 10))
        
        #content switcher (right) - pass serial connection for facial tracking
        self.content_switcher = ContentSwitcher(
            content_frame, self.state, self.serial_connection, self._log_message
        )
        self.content_switcher.frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        
        #terminal section (bottom)
        self._create_terminal_section(main_frame)
    
    #create terminal and console section
    def _create_terminal_section(self, parent):
        terminal_section = ttk.LabelFrame(parent, text="terminal & console")
        terminal_section.pack(fill="both", expand=True, pady=(5, 0))
        
        terminal_section.rowconfigure(1, weight=1)  #console expands
        terminal_section.columnconfigure(0, weight=1)
        
        #command terminal
        self.command_terminal = CommandTerminal(
            terminal_section,
            self.state,
            self.serial_connection,
            self.sequence_manager,
            self.content_switcher,
            self._log_message
        )
        self.command_terminal.frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        
        #console logger
        self.console_logger = ConsoleLogger(terminal_section)
        self.console_logger.frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    
    #setup sequence recording integration
    def _setup_sequence_integration(self):
        if self.content_switcher and self.serial_connection:
            self.content_switcher.set_sequence_dependencies(self.sequence_manager)
            self._log_message("sequence recording system initialised")
    
    #log startup information
    def _log_startup_info(self):
        self._log_message(f"initialised with {self.state.num_servos} servos")
        
        config_source = "custom" if hasattr(self.state, '_custom_config') else "default"
        self._log_message(f"loaded {config_source} servo configuration")
        
        self._log_message("servo control system ready")
        self._log_message("command terminal ready - type commands above or click help")
        # self._log_message("eye display system available with facial tracking")
    
    #handle connection state changes
    def _on_connection_changed(self, event_type, *args, **kwargs):
        connected = args[0]
        if connected:
            self._log_message("sequence recording and facial tracking now available")
        else:
            self._log_message("sequence recording and facial tracking disabled - no serial connection")
    
    #log message to console
    def _log_message(self, message):
        if self.console_logger:
            self.console_logger.log_message(message)
    
    #focus command terminal
    def focus_command_terminal(self):
        if self.command_terminal:
            self.command_terminal.focus_command_entry()
    
    #handle window close event
    def _on_window_close(self):
        self._log_message("shutting down servo control system...")
        
        #stop sequence playback if active
        if self.content_switcher.is_sequence_recording_active():
            sequence_widget = self.content_switcher.get_sequence_recorder_widget()
            if sequence_widget and hasattr(sequence_widget, 'playback_manager'):
                sequence_widget.playback_manager.stop_playback()
                self._log_message("stopped sequence playback")
        
        #cleanup eye display and facial tracking if active
        if hasattr(self.content_switcher, 'eye_display_widget') and self.content_switcher.eye_display_widget:
            self.content_switcher.eye_display_widget.cleanup()
            self._log_message("stopped eye display cameras and facial tracking")
        
        #cleanup components
        if self.serial_connection:
            self.serial_connection.cleanup()
        
        if self.state:
            self.state.cleanup()
        
        if self.content_switcher:
            self.content_switcher.cleanup()
        
        #cleanup event system
        cleanup()
        
        self._log_message("cleanup completed")
        self.root.destroy()
    
    #run the application
    def run(self):
        self.root.mainloop()
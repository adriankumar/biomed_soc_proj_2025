#real-time camera display for robotic eye positioning with facial tracking

import tkinter as tk
from tkinter import ttk
import cv2
import threading
import queue
import time
from PIL import Image, ImageTk
from core.facial_tracking import FacialTracker

class CameraManager:
    #manages camera enumeration with optimised detection for maximum 3 cameras
    def __init__(self):
        self.available_cameras = {}
        self.refresh_cameras()
    
    #enumerate camera devices 0-2 only for faster detection
    def refresh_cameras(self):
        self.available_cameras = {}
        
        #suppress opencv logging to eliminate enumeration noise
        original_log_level = cv2.getLogLevel()
        cv2.setLogLevel(0)
        
        try:
            #fixed enumeration for indices 0, 1, 2 only since max 3 cameras
            for index in range(3):
                cap = cv2.VideoCapture(index)
                
                if cap.isOpened():
                    #test if we can actually read a frame to confirm camera works
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        #get camera resolution for display in dropdown
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        
                        self.available_cameras[index] = {
                            'name': f"camera {index}",
                            'resolution': f"{width}x{height}",
                            'working': True
                        }
                
                cap.release()
        
        finally:
            #restore original opencv logging level
            cv2.setLogLevel(original_log_level)
        
        return list(self.available_cameras.keys())
    
    #get list of camera names for dropdown menu
    def get_camera_options(self):
        options = ["no camera"]
        
        for index, info in self.available_cameras.items():
            options.append(f"{info['name']} ({info['resolution']})")
        
        return options
    
    #get camera index from dropdown selection text
    def get_camera_index_from_selection(self, selection):
        if selection == "no camera" or not selection:
            return -1
        
        #extract index from selection string format "camera X (resolution)"
        try:
            parts = selection.split(" ")
            if len(parts) >= 2 and parts[0] == "camera":
                return int(parts[1])
        except (ValueError, IndexError):
            pass
        
        return -1


class ThreadedCameraCapture:
    #background camera capture with thread safety for smooth video feed
    def __init__(self, camera_index):
        self.camera_index = camera_index
        self.capture = None
        self.thread = None
        self.running = False
        self.frame_queue = queue.Queue(maxsize=2)
        
    #start camera capture thread for background frame grabbing
    def start(self):
        if self.camera_index == -1:
            return False
        
        try:
            #suppress opencv logging during capture initialisation
            original_log_level = cv2.getLogLevel()
            cv2.setLogLevel(0)
            
            self.capture = cv2.VideoCapture(self.camera_index)
            
            #restore logging level
            cv2.setLogLevel(original_log_level)
            
            if not self.capture.isOpened():
                return False
            
            #set capture properties for better performance
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.capture.set(cv2.CAP_PROP_FPS, 20)
            
            self.running = True
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            
            return True
            
        except Exception:
            return False
    
    #stop camera capture and cleanup resources
    def stop(self):
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        
        if self.capture:
            self.capture.release()
            self.capture = None
        
        #clear frame queue of any remaining frames
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
    
    #main capture loop in background thread for continuous frame grabbing
    def _capture_loop(self):
        while self.running and self.capture and self.capture.isOpened():
            try:
                ret, frame = self.capture.read()
                
                if ret and frame is not None:
                    #put frame in queue, remove old frame if queue full for latest frame
                    try:
                        self.frame_queue.put_nowait(frame)
                    except queue.Full:
                        #remove old frame and add new one to keep display current
                        try:
                            self.frame_queue.get_nowait()
                            self.frame_queue.put_nowait(frame)
                        except queue.Empty:
                            pass
                else:
                    #camera error detected, stop capture
                    break
                    
                time.sleep(0.033)  #approximately 30 fps
                
            except Exception:
                break
    
    #get latest frame without blocking if none available
    def get_latest_frame(self):
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None
    
    #check if camera is running and thread is alive
    def is_running(self):
        return self.running and self.thread and self.thread.is_alive()


class VideoFrameWidget:
    #video display widget for camera feed with facial tracking controls
    def __init__(self, parent, camera_manager, state_manager, serial_connection, log_callback):
        self.camera_manager = camera_manager
        self.state_manager = state_manager
        self.serial_connection = serial_connection
        self.log_callback = log_callback
        
        #camera state variables
        self.camera_capture = None
        self.selected_camera = tk.StringVar()
        self.display_width = 320
        self.display_height = 240
        
        #facial tracking system
        self.facial_tracker = FacialTracker(state_manager, serial_connection, log_callback)
        
        #create widget frame
        self.frame = ttk.LabelFrame(parent, text="camera feed & facial tracking")
        
        self._create_widget()
        self._create_fallback_image()
        
        #start display update timer for smooth video
        self.update_timer_active = False
        self._start_display_timer()
    
    #create video display widget with camera selection and tracking controls
    def _create_widget(self):
        #camera selection controls
        selection_frame = ttk.Frame(self.frame)
        selection_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(selection_frame, text="camera source:").pack(side="left", padx=(0, 10))
        
        self.camera_combo = ttk.Combobox(
            selection_frame, 
            textvariable=self.selected_camera,
            values=self.camera_manager.get_camera_options(),
            state="readonly",
            width=20
        )
        self.camera_combo.pack(side="left", padx=5)
        self.camera_combo.bind("<<ComboboxSelected>>", self._on_camera_changed)
        
        #facial tracking control button
        self.tracking_button = ttk.Button(
            selection_frame, 
            text="start tracking",
            command=self._toggle_tracking,
            state="disabled"
        )
        self.tracking_button.pack(side="left", padx=10)
        
        #set default selection to first option
        options = self.camera_manager.get_camera_options()
        if options:
            self.selected_camera.set(options[0])
            self._update_tracking_button_state()
        
        #video display canvas for showing camera feed
        self.canvas = tk.Canvas(
            self.frame,
            width=self.display_width,
            height=self.display_height,
            bg="black"
        )
        self.canvas.pack(padx=10, pady=10)
        
        #status label for connection and tracking info
        self.status_label = ttk.Label(self.frame, text="no camera selected", foreground="gray")
        self.status_label.pack(pady=(0, 10))
    
    #create fallback image for when no camera is available
    def _create_fallback_image(self):
        #create black image with text overlay
        fallback_img = Image.new('RGB', (self.display_width, self.display_height), color='black')
        self.fallback_photo = ImageTk.PhotoImage(fallback_img)
        
        #display fallback image initially
        self.canvas.create_image(
            self.display_width // 2, 
            self.display_height // 2, 
            image=self.fallback_photo, 
            anchor=tk.CENTER
        )
        
        #add text overlay for user info
        self.canvas.create_text(
            self.display_width // 2,
            self.display_height // 2,
            text="no camera source",
            fill="white",
            font=("Arial", 16)
        )
    
    #handle camera selection change from dropdown
    def _on_camera_changed(self, event=None):
        #stop tracking if active
        if self.facial_tracker.is_tracking_active():
            self.facial_tracker.stop_tracking()
            self.tracking_button.config(text="start tracking")
        
        self._stop_current_camera()
        self._start_selected_camera()
        self._update_tracking_button_state()
    
    #start selected camera capture based on dropdown choice
    def _start_selected_camera(self):
        selection = self.selected_camera.get()
        camera_index = self.camera_manager.get_camera_index_from_selection(selection)
        
        if camera_index == -1:
            self.status_label.config(text="no camera selected", foreground="gray")
            self._show_fallback_display()
            return
        
        #start camera capture thread
        self.camera_capture = ThreadedCameraCapture(camera_index)
        
        if self.camera_capture.start():
            self.status_label.config(text=f"camera {camera_index} active", foreground="green")
            self.log_callback(f"started camera {camera_index}")
        else:
            self.status_label.config(text=f"camera {camera_index} failed", foreground="red")
            self.log_callback(f"failed to start camera {camera_index}")
            self._show_fallback_display()
            self.camera_capture = None
    
    #stop current camera capture and cleanup
    def _stop_current_camera(self):
        if self.camera_capture:
            self.camera_capture.stop()
            self.camera_capture = None
    
    #show fallback display when no camera is working
    def _show_fallback_display(self):
        self.canvas.delete("all")
        self.canvas.create_image(
            self.display_width // 2, 
            self.display_height // 2, 
            image=self.fallback_photo, 
            anchor=tk.CENTER
        )
        self.canvas.create_text(
            self.display_width // 2,
            self.display_height // 2,
            text="no camera source",
            fill="white",
            font=("Arial", 16)
        )
    
    #toggle facial tracking on and off
    def _toggle_tracking(self):
        if self.facial_tracker.is_tracking_active():
            #stop tracking
            self.facial_tracker.stop_tracking()
            self.tracking_button.config(text="start tracking")
            self.status_label.config(text="camera active - tracking stopped", foreground="orange")
        else:
            #start tracking
            if self.camera_capture and self.camera_capture.is_running():
                #get actual camera dimensions
                frame = self.camera_capture.get_latest_frame()
                if frame is not None:
                    height, width = frame.shape[:2]
                    self.facial_tracker.start_tracking(width, height)
                    self.tracking_button.config(text="stop tracking")
                    self.status_label.config(text="camera active - tracking enabled", foreground="blue")
                else:
                    self.log_callback("cannot start tracking - no camera frame available")
            else:
                self.log_callback("cannot start tracking - camera not active")
    
    #update tracking button state based on camera selection
    def _update_tracking_button_state(self):
        selection = self.selected_camera.get()
        camera_index = self.camera_manager.get_camera_index_from_selection(selection)
        
        if camera_index == -1:
            self.tracking_button.config(state="disabled")
        else:
            self.tracking_button.config(state="normal")
    
    #start display update timer for smooth video playback
    def _start_display_timer(self):
        if not self.update_timer_active:
            self.update_timer_active = True
            self._update_display()
    
    #stop display update timer
    def _stop_display_timer(self):
        self.update_timer_active = False
    
    #update video display called by timer for smooth frame updates
    def _update_display(self):
        if not self.update_timer_active:
            return
        
        if self.camera_capture and self.camera_capture.is_running():
            frame = self.camera_capture.get_latest_frame()
            
            if frame is not None:
                #process frame through facial tracker if active
                if self.facial_tracker.is_tracking_active():
                    frame = self.facial_tracker.process_frame(frame)
                
                self._display_frame(frame)
        
        #schedule next update for 20 fps display
        self.frame.after(50, self._update_display)
    
    #display camera frame on canvas with proper sizing
    def _display_frame(self, frame):
        try:
            #resize frame to display size
            frame_resized = cv2.resize(frame, (self.display_width, self.display_height))
            
            #convert BGR to RGB for proper colour display
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            
            #convert to PIL image for tkinter compatibility
            pil_image = Image.fromarray(frame_rgb)
            
            #convert to PhotoImage for tkinter canvas
            photo = ImageTk.PhotoImage(pil_image)
            
            #update canvas with new frame
            self.canvas.delete("all")
            self.canvas.create_image(
                self.display_width // 2,
                self.display_height // 2,
                image=photo,
                anchor=tk.CENTER
            )
            
            #keep reference to prevent garbage collection
            self.canvas.image = photo
            
        except Exception as e:
            #on error show fallback to maintain stability
            self._show_fallback_display()
    
    #refresh camera options and update dropdown
    def refresh_camera_options(self):
        current_selection = self.selected_camera.get()
        new_options = self.camera_manager.get_camera_options()
        
        self.camera_combo['values'] = new_options
        
        #restore selection if still available
        if current_selection in new_options:
            self.selected_camera.set(current_selection)
        else:
            #set to first available option
            self.selected_camera.set(new_options[0] if new_options else "no camera")
            self._on_camera_changed()
        
        self._update_tracking_button_state()
    
    #cleanup when widget destroyed to prevent memory leaks
    def cleanup(self):
        #stop facial tracking if active
        if self.facial_tracker.is_tracking_active():
            self.facial_tracker.stop_tracking()
        
        self._stop_display_timer()
        self._stop_current_camera()


class EyeDisplayWidget:
    #main widget for single camera eye display system with facial tracking
    def __init__(self, parent, state_manager, serial_connection, log_callback):
        self.frame = ttk.LabelFrame(parent, text="robotic eye display & facial tracking")
        self.state_manager = state_manager
        self.serial_connection = serial_connection
        self.log_callback = log_callback
        
        #camera management components
        self.camera_manager = CameraManager()
        self.video_widget = None
        
        self._create_widget()
    
    #create main eye display interface with controls
    def _create_widget(self):
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        #header with refresh button for camera detection
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(header_frame, text="refresh cameras", 
                  command=self._refresh_cameras).pack(side="right")
        
        #camera display area for video feed and tracking
        display_frame = ttk.Frame(main_frame)
        display_frame.pack(fill="both", expand=True)
        
        #single camera feed widget with facial tracking
        self.video_widget = VideoFrameWidget(
            display_frame, self.camera_manager, self.state_manager, 
            self.serial_connection, self.log_callback
        )
        self.video_widget.frame.pack(fill="both", expand=True)
        
        #status area for system information
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill="x", pady=(10, 0))
        
        self.status_label = ttk.Label(status_frame, text="eye display ready", foreground="green")
        self.status_label.pack(side="left")
        
        #camera count display for user info
        camera_count = len(self.camera_manager.available_cameras)
        self.camera_count_label = ttk.Label(status_frame, text=f"{camera_count} camera(s) detected")
        self.camera_count_label.pack(side="right")
        
        self.log_callback(f"eye display with facial tracking initialised - {camera_count} camera(s)")
    
    #refresh available cameras using optimised detection
    def _refresh_cameras(self):
        self.log_callback("refreshing camera devices...")
        
        #refresh camera manager with fast enumeration
        available_cameras = self.camera_manager.refresh_cameras()
        
        #update video widget options
        if self.video_widget:
            self.video_widget.refresh_camera_options()
        
        #update status display
        camera_count = len(available_cameras)
        self.camera_count_label.config(text=f"{camera_count} camera(s) detected")
        
        self.log_callback(f"found {camera_count} camera(s): {available_cameras}")
    
    #show widget when selected
    def show(self):
        self.frame.pack(fill="both", expand=True)
    
    #hide widget when not selected
    def hide(self):
        self.frame.pack_forget()
    
    #check if widget is currently visible
    def is_visible(self):
        return self.frame.winfo_manager() == "pack"
    
    #cleanup when widget destroyed to prevent resource leaks
    def cleanup(self):
        if self.video_widget:
            self.video_widget.cleanup()
        
        self.log_callback("eye display system cleaned up")
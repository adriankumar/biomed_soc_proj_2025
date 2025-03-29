import tkinter as tk
from tkinter import ttk
from tkinter import messagebox, filedialog
import threading
from threading import Timer
import time

from servo_model import ServoModel
from servo_view import ServoView
from servo_sequence_plot import ServoSequencePlot

class ServoController:
    def __init__(self, root):
        
        #initialise model (data) and view (display) objects
        self.model = ServoModel()
        self.view = ServoView(root)
        
        #set call back to view's log message which just displays connectivity status
        self.model.set_log_callback(self.view.log_message)
        
        #initialise servo variables from model config
        self.servos = []
        for servo in ServoModel.SERVO_CONFIG:
            self.servos.append({
                "id": servo["id"],
                "name": servo["name"],
                "value": tk.IntVar(value=servo["default_value"])
            })
        
        #for throttling updates
        self.update_timers = {}

        self.sequence_plot = None
        
        #set up event handlers
        self.setup_connection_handlers()
        self.setup_view_toggle_handlers()
        self.setup_sequence_handlers()
        
        #initial view setup
        self.update_view_mode()
        self.find_available_ports()
    
    #setting handlers for connection-related GUI stuff from create_connection_frame()
    def setup_connection_handlers(self):
        components = self.view.connection_components
        
        #connect/disconnect button
        components["connect_button"].config(command=self.toggle_connection)
        
        #refresh ports button
        components["refresh_button"].config(command=self.find_available_ports)
    
    #view toggle handlers for servo control between master and individual
    def setup_view_toggle_handlers(self):
        components = self.view.view_toggle_components
        
        # View mode radio buttons
        components["master_radio"].config(command=self.update_view_mode)
        components["individual_radio"].config(command=self.update_view_mode)
    
    #set up handlers for sequence playback controls
    def setup_sequence_handlers(self):
        components = self.view.sequence_components
        
        #sequence control buttons
        components["record_button"].config(command=self.record_step)
        components["play_button"].config(command=self.play_sequence)
        components["stop_button"].config(command=self.stop_sequence)
        components["clear_button"].config(command=self.clear_sequence)
        components["save_button"].config(command=self.save_sequence)
        components["load_button"].config(command=self.load_sequence)
        components["remove_button"].config(command=self.remove_step)
        components["plot_button"].config(command=self.toggle_sequence_plot)
    
    #handler for finding ports
    def find_available_ports(self):
        ports = self.model.find_available_ports()
        self.view.port_combo["values"] = ports
        if ports:
            self.view.port_var.set(ports[0])
    
    #changing connection button to connect or disconnect based on current connection status
    def toggle_connection(self):
        if not self.model.is_connected():
            #connect
            if self.model.connect_to_serial(self.view.port_var.get()):
                self.view.update_connection_status(self.model.status, True)
        else:
            #diconnect
            self.model.disconnect_from_serial()
            self.view.update_connection_status(self.model.status, False)
    
    #update servo control view (master or individual)
    def update_view_mode(self):
        mode = self.view.view_mode.get()
        
        if mode == "master":
            #create master control view
            master_controls = self.view.create_master_control_frame(self.servos)
            
            #set up event handlers
            master_controls["slider"].config(
                command=lambda e: self.slider_changed(None, is_master=True)
            )
            
            for button, angle in master_controls["preset_buttons"]:
                button.config(
                    command=lambda a=angle: self.set_preset(a, is_master=True)
                )
        else:
            servo_controls = self.view.create_individual_controls_frame(self.servos)
            for i, control in enumerate(servo_controls):
                self.servos[i]["label"] = control["label"]

                servo = self.servos[i]
                
                #slider events
                control["slider"].config(
                    command=lambda e, s=servo: self.slider_changed(s)
                )
                
                #preset button events
                for button, angle in control["preset_buttons"]:
                    button.config(
                        command=lambda s=servo, a=angle: self.set_preset(a, servo=s)
                    )
    
    #handle slider value changing with throttling (very small delay to prevent serial overload)
    def slider_changed(self, servo=None, is_master=False):
        if is_master:
            #update all servos to match master value
            value = self.view.master_value.get()
            self.view.master_value_label.config(text=f"Position: {value} degrees")
            
            #update individual servo values
            for s in self.servos:
                s["value"].set(value)
            
            #cancel pending update if any
            timer_key = "master"
            if timer_key in self.update_timers and self.update_timers[timer_key] is not None:
                self.update_timers[timer_key].cancel()
            
            #schedule update
            self.update_timers[timer_key] = Timer(
                self.model.THROTTLE_DELAY, 
                lambda: self.model.send_master_position(value)
            )
            self.update_timers[timer_key].start()
            
        else:
            #individual servo update
            value = servo["value"].get()
            servo_id = servo["id"]
            
            if "label" in servo:
                servo["label"].config(text=f"Position: {value} degrees")
            
            #cancel pending update for this servo
            timer_key = f"servo_{servo_id}"
            if timer_key in self.update_timers and self.update_timers[timer_key] is not None:
                self.update_timers[timer_key].cancel()
            
            #schedule update
            self.update_timers[timer_key] = Timer(
                self.model.THROTTLE_DELAY, 
                lambda: self.model.send_servo_position(servo_id, value)
            )
            self.update_timers[timer_key].start()
    
    #handling if preset buttons are chosen
    def set_preset(self, value, servo=None, is_master=False):
        if is_master:
            #set master value
            self.view.master_value.set(value)
            self.view.master_value_label.config(text=f"Position: {value} degrees")
            
            #set all servo values
            for s in self.servos:
                s["value"].set(value)
            
            #send to all servos
            self.model.send_master_position(value)
        else:
            #set individual servo
            servo["value"].set(value)
            
            #update the label directly using stored reference
            if "label" in servo:
                servo["label"].config(text=f"Position: {value} degrees")
            
            #send to specific servo
            self.model.send_servo_position(servo["id"], value)
    
    #record the current servo positions as a state/step
    def record_step(self):
        #create position data from current servo values
        servo_positions = []
        for servo in self.servos:
            servo_positions.append({
                "id": servo["id"],
                "name": servo["name"],
                "position": servo["value"].get()
            })
        
        #record step in model
        if self.model.add_sequence_step(servo_positions, self.view.delay_var.get()):
            #update display
            self.view.update_sequence_display(self.model.sequence)
            
            #update button states
            has_sequence = self.model.get_sequence_length() > 0
            self.view.update_playback_controls(False, has_sequence)
        
        if self.sequence_plot:
            self.sequence_plot.update() #update sequence plot
    
    #removing selected step/state in the current sequence
    def remove_step(self):
        selected = self.view.step_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "No step selected")
            return
        
        #get index
        item = selected[0]
        index = self.view.step_tree.index(item)
        
        if self.model.remove_sequence_step(index):
            #update display
            self.view.update_sequence_display(self.model.sequence)
            
            #update button states
            has_sequence = self.model.get_sequence_length() > 0
            self.view.update_playback_controls(False, has_sequence)

        if self.sequence_plot:
            self.sequence_plot.update() #update sequence plot
    
    #toggle sequence plot window
    def toggle_sequence_plot(self):
        if not self.model.sequence:
            messagebox.showinfo("Info", "No sequence to plot")
            return
            
        if self.sequence_plot is None:
            self.sequence_plot = ServoSequencePlot(self.view.root, self.model)
        
        self.sequence_plot.show()

    #send the sequence signals to serial
    def play_sequence(self):
        if not self.model.sequence:
            messagebox.showinfo("Info", "No sequence to play")
            return
            
        if not self.model.is_connected():
            messagebox.showerror("Error", "Not connected to serial port")
            return
        
        #update button states
        self.view.update_playback_controls(True, True)
        
        #start sequence thread
        self.model.sequence_playing = True
        self.model.sequence_thread = threading.Thread(
            target=self.sequence_player_thread
        )
        self.model.sequence_thread.daemon = True
        self.model.sequence_thread.start()
    
    #thread for playing sequence 
    def sequence_player_thread(self):
        try:
            #inform ESP that sequence is starting
            self.model.send_to_serial("P:start")
            
            for i, step in enumerate(self.model.sequence):
                if not self.model.sequence_playing:
                    break
                
                #highlight current step in GUI
                self.view.root.after(0, lambda idx=i: self.view.highlight_step(idx))
                
                #send each servo position
                for servo_data in step["servos"]:
                    if not self.model.sequence_playing:
                        break
                    
                    servo_id = servo_data["id"]
                    position = servo_data["position"]
                    
                    #update GUI representation
                    self.view.root.after(0, lambda s_id=servo_id, pos=position: self.update_servo_display(s_id, pos))
                    
                    #send to hardware
                    self.model.send_servo_position(servo_id, position)
                    time.sleep(0.01)  #small delay between commands
                
                #wait for the step delay
                time.sleep(step["delay"] / 1000.0)
            
            #sequence complete
            if self.model.sequence_playing:
                self.model.send_to_serial("P:end")
                self.model.log_message("Sequence playback completed")
                
        except Exception as e:
            self.model.log_message(f"Error during playback: {str(e)}")
        finally:
            #reset button states
            self.view.root.after(0, lambda: self.view.update_playback_controls(
                False, self.model.get_sequence_length() > 0
            ))
            self.model.sequence_playing = False
    
    #live update the servo control display as sequence plays
    def update_servo_display(self, servo_id, position):
        #find the servo with matching ID
        for servo in self.servos:
            if servo["id"] == servo_id:
                #update value
                servo["value"].set(position)
                
                #update label if it exists
                if "label" in servo and servo["label"].winfo_exists():
                    servo["label"].config(text=f"Position: {position} degrees")
                break
                
        #update master view if all servos have same position
        if self.view.view_mode.get() == "master":
            all_same = True
            first_pos = self.servos[0]["value"].get()
            for servo in self.servos:
                if servo["value"].get() != first_pos:
                    all_same = False
                    break
                    
            if all_same:
                self.view.master_value.set(first_pos)
                self.view.master_value_label.config(text=f"Position: {first_pos} degrees")
    
    #if stop button is clicked during sequence playback
    def stop_sequence(self):
        self.model.sequence_playing = False
        
        #notify ESP
        if self.model.is_connected():
            self.model.send_to_serial("P:stop")
        
        self.model.log_message("Sequence playback stopped")
        self.view.update_playback_controls(False, self.model.get_sequence_length() > 0)
    
    #clear the current sequence
    def clear_sequence(self):
        if not self.model.sequence:
            return
        
        if messagebox.askyesno("Confirm", "Are you sure you want to clear the sequence?"):
            self.model.clear_sequence()
            self.view.update_sequence_display([])
            self.view.update_playback_controls(False, False)

        if self.sequence_plot:
            self.sequence_plot.update() #update sequence plot
    
    #save current sequence to json file
    def save_sequence(self):
        """Save sequence to file"""
        if not self.model.sequence:
            messagebox.showinfo("Info", "No sequence to save")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Sequence"
        )
        
        self.model.save_sequence(file_path)
    
    #load in selected json file
    def load_sequence(self):
        
        file_path = filedialog.askopenfilename(
        filetypes=[("JSON files", "*.json"), 
                   ("All files", "*.*")], 
                   title="Load Sequence")
            
        if self.model.load_sequence(file_path):
            self.view.update_sequence_display(self.model.sequence)
            self.view.update_playback_controls(False, self.model.get_sequence_length() > 0)
                
            #check for servo configuration mismatch
            sequence_servo_ids = set()
            for step in self.model.sequence:
                for servo in step["servos"]:
                    sequence_servo_ids.add(servo["id"])
                
            current_servo_ids = {servo["id"] for servo in self.servos}
                
            if sequence_servo_ids != current_servo_ids:
                messagebox.showwarning(
                    "Servo Configuration Mismatch",
                    "The loaded sequence contains servos that don't match the current configuration. " +
                    "Playback may not work as expected."
                    )
                
        if self.sequence_plot:
            self.sequence_plot.update() #update sequence plot
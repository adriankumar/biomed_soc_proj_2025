import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import time
import threading
from servo_motion_editor import ServoMotionEditor

class SequenceRecording:
    def __init__(self, parent, num_servos, get_servo_angles_callback=None, send_command_callback=None):
        #create main frame
        self.frame = ttk.LabelFrame(parent, text="Sequence Recording")
        
        #store parameters
        self.num_servos = num_servos
        self.get_servo_angles = get_servo_angles_callback
        self.send_command = send_command_callback
        
        #sequence data
        self.sequence = []
        self.is_playing = False
        self.play_thread = None
        
        #delay between steps (milliseconds)
        self.delay_var = tk.IntVar(value=500)
        
        #create ui components
        self._create_ui()
        
    #-----------------------------------------------------------------------
    #ui creation
    #-----------------------------------------------------------------------
    def _create_ui(self):
        #delay setting
        delay_frame = ttk.Frame(self.frame)
        delay_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(delay_frame, text="Step Delay (ms):").pack(side="left", padx=5)
        
        self.delay_spinbox = ttk.Spinbox(
            delay_frame,
            from_=50,
            to=5000,
            increment=50,
            textvariable=self.delay_var,
            width=5
        )
        self.delay_spinbox.pack(side="left", padx=5)
        
        #control buttons
        buttons_frame = ttk.Frame(self.frame)
        buttons_frame.pack(fill="x", padx=5, pady=5)
        
        self.record_button = ttk.Button(
            buttons_frame,
            text="Record Step",
            command=self.record_step
        )
        self.record_button.pack(side="left", padx=5)
        
        self.play_button = ttk.Button(
            buttons_frame,
            text="Play Sequence",
            command=self.play_sequence,
            state="disabled"
        )
        self.play_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(
            buttons_frame,
            text="Stop",
            command=self.stop_sequence,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=5)
        
        self.clear_button = ttk.Button(
            buttons_frame,
            text="Clear Sequence",
            command=self.clear_sequence,
            state="disabled"
        )
        self.clear_button.pack(side="left", padx=5)
        
        #save/load buttons
        file_frame = ttk.Frame(self.frame)
        file_frame.pack(fill="x", padx=5, pady=5)
        
        self.save_button = ttk.Button(
            file_frame,
            text="Save Sequence",
            command=self.save_sequence
        )
        self.save_button.pack(side="left", padx=5)
        
        self.load_button = ttk.Button(
            file_frame,
            text="Load Sequence",
            command=self.load_sequence
        )
        self.load_button.pack(side="left", padx=5)
        
        #sequence display
        display_frame = ttk.LabelFrame(self.frame, text="Recorded Steps")
        display_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        #treeview for steps
        columns = ("Step", "Servos", "Delay")
        self.step_tree = ttk.Treeview(
            display_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )
        
        #column headings
        self.step_tree.heading("Step", text="Step")
        self.step_tree.heading("Servos", text="Servo Positions")
        self.step_tree.heading("Delay", text="Delay (ms)")
        
        #column widths
        self.step_tree.column("Step", width=50, anchor="center")
        self.step_tree.column("Servos", width=350, anchor="w")
        self.step_tree.column("Delay", width=80, anchor="center")
        
        #scrollbar
        scrollbar = ttk.Scrollbar(display_frame, orient="vertical", command=self.step_tree.yview)
        self.step_tree.configure(yscrollcommand=scrollbar.set)
        
        self.step_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        #buttons under treeview
        tree_buttons_frame = ttk.Frame(self.frame)
        tree_buttons_frame.pack(fill="x", padx=5, pady=5)
        
        self.remove_button = ttk.Button(
            tree_buttons_frame,
            text="Remove Selected Step",
            command=self.remove_step
        )
        self.remove_button.pack(side="left", padx=5)
        
        self.edit_motion_button = ttk.Button(
            tree_buttons_frame,
            text="Edit Motion Graph",
            command=self.edit_motion_graph,
            state="disabled"
        )
        self.edit_motion_button.pack(side="left", padx=5)
    
    #-----------------------------------------------------------------------
    #sequence control methods
    #-----------------------------------------------------------------------
    def record_step(self):
        #check if we can get servo angles
        if not self.get_servo_angles:
            messagebox.showerror("Error", "Cannot get servo angles")
            return
        
        #get current servo positions
        servo_positions = self.get_servo_angles()
        
        if not servo_positions or len(servo_positions) != self.num_servos:
            messagebox.showerror("Error", "Invalid servo positions")
            return
        
        #create step data
        step = {
            "servos": servo_positions,
            "delay": self.delay_var.get()
        }
        
        #add to sequence
        self.sequence.append(step)
        
        #update display
        self._update_sequence_display()
        
        #update button states
        self._update_buttons()
    
    def remove_step(self):
        selected = self.step_tree.selection()
        
        if not selected:
            messagebox.showinfo("Info", "No step selected")
            return
        
        #get index
        item = selected[0]
        index = self.step_tree.index(item)
        
        #remove from sequence
        if 0 <= index < len(self.sequence):
            self.sequence.pop(index)
            
            #update display
            self._update_sequence_display()
            
            #update button states
            self._update_buttons()
    
    def play_sequence(self):
        if not self.sequence:
            messagebox.showinfo("Info", "No sequence to play")
            return
        
        #check if we can send commands
        if not self.send_command:
            messagebox.showerror("Error", "Cannot send commands")
            return
        
        #update ui state
        self.is_playing = True
        self._update_buttons()
        
        #start sequence playback thread
        self.play_thread = threading.Thread(target=self._playback_thread)
        self.play_thread.daemon = True
        self.play_thread.start()
    
    def _playback_thread(self):
        try:
            for i, step in enumerate(self.sequence):
                if not self.is_playing:
                    break
                
                #highlight current step
                self.step_tree.selection_set(self.step_tree.get_children()[i])
                self.step_tree.see(self.step_tree.get_children()[i])
                
                #send commands for each servo
                for servo in step["servos"]:
                    if not self.is_playing:
                        break
                    
                    servo_id = servo["id"]
                    position = servo["position"]
                    
                    #send servo command
                    self.send_command(f"SA:{servo_id}:{position}")
                    time.sleep(0.01)  #small delay between commands
                
                #wait for delay
                if self.is_playing:
                    time.sleep(step["delay"] / 1000.0) #in ms
                    
        except Exception as e:
            print(f"Error during playback: {str(e)}")
            messagebox.showerror("Playback Error", str(e))
            
        finally:
            #reset play state
            self.is_playing = False
            
            #update ui from main thread
            self.frame.after(0, self._update_buttons)
    
    def stop_sequence(self):
        #stop playback
        self.is_playing = False
        
        #send stop command
        if self.send_command:
            self.send_command("STOP")
        
        #update buttons
        self._update_buttons()
    
    def clear_sequence(self):
        if not self.sequence:
            return
            
        if messagebox.askyesno("Confirm", "Are you sure you want to clear the sequence?"):
            self.sequence = []
            self._update_sequence_display()
            self._update_buttons()
    
    #-----------------------------------------------------------------------
    #file operations
    #-----------------------------------------------------------------------
    def save_sequence(self):
        if not self.sequence:
            messagebox.showinfo("Info", "No sequence to save")
            return
            
        #get file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'w') as file:
                json.dump(self.sequence, file, indent=2)
                
            messagebox.showinfo("Success", f"Sequence saved to {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error saving sequence: {str(e)}")
    
    def load_sequence(self):
        #get file path
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r') as file:
                loaded_sequence = json.load(file)
                
            #validate sequence
            if not isinstance(loaded_sequence, list):
                raise ValueError("Invalid sequence format")
                
            for step in loaded_sequence:
                if not isinstance(step, dict) or "servos" not in step or "delay" not in step:
                    raise ValueError("Invalid step format")
                    
            #update sequence
            self.sequence = loaded_sequence
            self._update_sequence_display()
            self._update_buttons()
            
            messagebox.showinfo("Success", f"Sequence loaded from {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error loading sequence: {str(e)}")
    
    def edit_motion_graph(self):
        if not self.sequence:
            messagebox.showinfo("Info", "No sequence to edit")
            return
            
        #create motion editor (currently just a stub)
        editor = ServoMotionEditor(self.frame, self.sequence)
        editor.show()
    
    #-----------------------------------------------------------------------
    #ui update helpers
    #-----------------------------------------------------------------------
    def _update_sequence_display(self):
        #clear current display
        for item in self.step_tree.get_children():
            self.step_tree.delete(item)
            
        #add sequence steps
        for i, step in enumerate(self.sequence):
            #format servo positions text
            positions_text = ", ".join([
                f"Servo {servo['id']}: {servo['position']}°" 
                for servo in step["servos"]
            ])
            
            #add to treeview
            self.step_tree.insert(
                "",
                "end",
                values=(i+1, positions_text, step["delay"])
            )
    
    def _update_buttons(self):
        has_sequence = bool(self.sequence)
        
        #enable/disable buttons based on state
        self.record_button.config(state="disabled" if self.is_playing else "normal")
        self.play_button.config(state="disabled" if self.is_playing or not has_sequence else "normal")
        self.stop_button.config(state="normal" if self.is_playing else "disabled")
        self.clear_button.config(state="disabled" if self.is_playing or not has_sequence else "normal")
        self.edit_motion_button.config(state="disabled" if self.is_playing or not has_sequence else "normal")
        self.remove_button.config(state="disabled" if self.is_playing or not has_sequence else "normal")
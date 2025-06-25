"""
================================================================================
3D PRINT QUEUE MANAGER - Bytes and Bolts Biomedical Engineering Society
================================================================================

FUNCTION:
This script manages a queue system for 3D printing requests from multiple teams.
It scans a Google Drive folder structure for STL files, tracks print status,
and provides a GUI for queue management with fair first-come-first-served ordering.

REQUIRED FILE STRUCTURE:
The script expects the following Google Drive folder structure:

📁 Bytes and Bolts Print Submissions/
├── 📁 team 1/
│   ├── 📁 project_name_1/
│   │   ├── 📄 part1.stl
│   │   ├── 📄 part2.stl
│   │   └── 📄 assembly.stl
│   └── 📁 project_name_2/
│       └── 📄 gear.stl
├── 📁 team 2/
│   └── 📁 robot_arm/
│       ├── 📄 base.stl
│       └── 📄 joint.stl
├── 📁 team 3/
│   └── 📁 sensor_housing/
│       └── 📄 case.stl
...
└── 📁 team 14/
    └── 📁 final_project/
        └── 📄 prototype.stl

FEATURES:
- Automatic scanning for new print requests (folders containing .stl files)
- Fair queue ordering (first-come-first-served based on folder creation time)
- Individual STL file tracking within each request
- Print status management (waiting, printing, completed, deleted)
- Multi-selection support for batch operations
- Auto-refresh with configurable intervals
- Persistent state storage in JSON format
- Cross-platform folder opening
- Detailed progress tracking and statistics

REQUIREMENTS:
- Python 3.6+
- tkinter (usually included with Python)
- Standard library modules: os, json, time, datetime, pathlib, threading
- Google Drive desktop app (for folder synchronization)
- Write permissions in the script directory (for print_queue_state.json)

USAGE:
1. Ensure Google Drive is synced and the folder structure exists
2. Update the base_directory path in main() function if needed
3. Run: python print-queue.py
4. The GUI will open with current queue state
5. Use "Scan for New Requests" to refresh manually
6. Double-click requests to manage individual STL files
7. Use status buttons to update print progress

PERSISTENCE:
The script saves queue state to 'print_queue_state.json' in the same directory
as the script. This file contains all request history and print status.

SORTING OPTIONS:
- Default: Creation time (oldest first) - ensures fair queue ordering
- Team: Sort by team number
- Status: Group by print status
- STL Count: Sort by number of files
- Request Name: Alphabetical sorting

STATUS DEFINITIONS:
- waiting: New request, not yet started printing
- printing: Currently being printed
- completed: All STL files have been printed
- deleted: Folder was removed from Google Drive

TEAM FOLDER NAMING:
Team folders must be named exactly: "team 1", "team 2", ..., "team 14"
(lowercase "team" followed by space and number)

================================================================================
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import threading

class PrintQueueManager:
    def __init__(self, base_directory):
        self.base_directory = Path(base_directory)
        
        # Get the directory where the script is located
        script_directory = Path(__file__).parent
        self.queue_file = script_directory / "print_queue_state.json"
        
        self.print_requests = {}
        self.load_queue_state()
        
    def load_queue_state(self):
        """Load previous queue state from file"""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r') as f:
                    self.print_requests = json.load(f)
                print(f"Loaded {len(self.print_requests)} previous requests from {self.queue_file}")
            except Exception as e:
                print(f"Error loading queue state: {e}")
                self.print_requests = {}
        else:
            self.print_requests = {}
    
    def save_queue_state(self):
        """Save current queue state to file"""
        try:
            with open(self.queue_file, 'w') as f:
                json.dump(self.print_requests, f, indent=2)
            print(f"Queue state saved to {self.queue_file}")
        except Exception as e:
            print(f"Error saving queue state: {e}")
    
    def scan_for_requests(self):
        """Scan directory structure for new print requests"""
        if not self.base_directory.exists():
            print(f"Base directory not found: {self.base_directory}")
            return
        
        new_requests = 0
        
        # Scan teams 1-14
        for team_num in range(1, 15):
            team_folder = self.base_directory / f"team {team_num}"
            if not team_folder.exists():
                continue
                
            # Look for folders containing .stl files
            for request_folder in team_folder.iterdir():
                if not request_folder.is_dir():
                    continue
                
                # Check if folder contains .stl files
                stl_files = list(request_folder.glob("*.stl"))
                if not stl_files:
                    continue
                
                # Create unique request ID
                request_id = f"team_{team_num}_{request_folder.name}"
                
                # If this is a new request, add it
                if request_id not in self.print_requests:
                    creation_time = request_folder.stat().st_mtime
                    
                    # Initialize STL file tracking
                    stl_file_status = {}
                    for stl_file in stl_files:
                        stl_file_status[stl_file.name] = {
                            "printed": False,
                            "print_date": None
                        }
                    
                    self.print_requests[request_id] = {
                        "team": team_num,
                        "folder_name": request_folder.name,
                        "folder_path": str(request_folder),
                        "stl_files": [f.name for f in stl_files],
                        "stl_file_status": stl_file_status,  # NEW: Track individual file status
                        "creation_time": creation_time,
                        "creation_date": datetime.fromtimestamp(creation_time).strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "waiting",
                        "added_to_queue": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    new_requests += 1
                    print(f"New request found: Team {team_num} - {request_folder.name}")
                else:
                    # Update existing request if new STL files are added
                    existing_files = set(self.print_requests[request_id]["stl_files"])
                    current_files = set(f.name for f in stl_files)
                    
                    if current_files != existing_files:
                        # Update file lists
                        self.print_requests[request_id]["stl_files"] = list(current_files)
                        
                        # Add new files to status tracking
                        if "stl_file_status" not in self.print_requests[request_id]:
                            self.print_requests[request_id]["stl_file_status"] = {}
                        
                        for file_name in current_files:
                            if file_name not in self.print_requests[request_id]["stl_file_status"]:
                                self.print_requests[request_id]["stl_file_status"][file_name] = {
                                    "printed": False,
                                    "print_date": None
                            }
                        
                        # Remove files that no longer exist
                        files_to_remove = existing_files - current_files
                        for file_name in files_to_remove:
                            if file_name in self.print_requests[request_id]["stl_file_status"]:
                                del self.print_requests[request_id]["stl_file_status"][file_name]
    
        if new_requests > 0:
            self.save_queue_state()
            print(f"Added {new_requests} new requests to queue")
        
        return new_requests
    
    def get_sorted_queue(self, sort_by="creation_time", reverse=False):
        """Get print requests sorted by specified criteria
        
        **DEFAULT: creation_time (oldest first) - ensures fair first-come-first-served ordering**
        """
        if sort_by == "creation_time":
            # **DEFAULT SORTING: By creation time (oldest first)**
            return sorted(
                self.print_requests.items(),
                key=lambda x: x[1]["creation_time"],
                reverse=reverse
            )
        elif sort_by == "team":
            # Sort by team number, then by creation time
            return sorted(
                self.print_requests.items(),
                key=lambda x: (x[1]["team"], x[1]["creation_time"]),
                reverse=reverse
            )
        elif sort_by == "status":
            # Sort by status priority, then by creation time
            status_priority = {"waiting": 1, "printing": 2, "completed": 3, "deleted": 4}
            return sorted(
                self.print_requests.items(),
                key=lambda x: (status_priority.get(x[1]["status"], 5), x[1]["creation_time"]),
                reverse=reverse
            )
        elif sort_by == "stl_count":
            # Sort by number of STL files, then by creation time
            return sorted(
                self.print_requests.items(),
                key=lambda x: (len(x[1]["stl_files"]), x[1]["creation_time"]),
                reverse=reverse
            )
        elif sort_by == "folder_name":
            # Sort alphabetically by folder name
            return sorted(
                self.print_requests.items(),
                key=lambda x: x[1]["folder_name"].lower(),
                reverse=reverse
            )
        else:
            # **FALLBACK TO DEFAULT: creation_time (oldest first)**
            return sorted(
                self.print_requests.items(),
                key=lambda x: x[1]["creation_time"],
                reverse=False
            )
    
    def update_status(self, request_id, new_status):
        """Update the status of a print request"""
        if request_id in self.print_requests:
            old_status = self.print_requests[request_id]["status"]
            self.print_requests[request_id]["status"] = new_status
            self.print_requests[request_id]["status_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_queue_state()
            print(f"Updated {request_id}: {old_status} -> {new_status}")
            return True
        return False

    def check_for_deleted_requests(self):
        """Check if any requests have been deleted from Google Drive"""
        deleted_requests = []
        
        for request_id, data in self.print_requests.items():
            folder_path = Path(data["folder_path"])
            if not folder_path.exists():
                # Mark as deleted
                self.print_requests[request_id]["status"] = "deleted"
                self.print_requests[request_id]["deleted_detected"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                deleted_requests.append(request_id)
        
        if deleted_requests:
            self.save_queue_state()
            print(f"Detected {len(deleted_requests)} deleted requests")
        
        return len(deleted_requests)

    def remove_request_from_memory(self, request_id):
        """Remove a request from memory/queue"""
        if request_id in self.print_requests:
            del self.print_requests[request_id]
            self.save_queue_state()
            print(f"Removed {request_id} from queue")
            return True
        return False

    def delete_request_folder(self, request_id):
        """Delete the folder from Google Drive"""
        if request_id in self.print_requests:
            folder_path = Path(self.print_requests[request_id]["folder_path"])
            try:
                if folder_path.exists():
                    import shutil
                    shutil.rmtree(folder_path)
                    print(f"Deleted folder: {folder_path}")
                    return True
                else:
                    print(f"Folder already deleted: {folder_path}")
                    return True
            except Exception as e:
                print(f"Error deleting folder: {e}")
                return False
        return False

    def update_stl_file_status(self, request_id, file_name, printed_status):
        """Update the printed status of a specific STL file"""
        if request_id in self.print_requests:
            if "stl_file_status" not in self.print_requests[request_id]:
                # Initialize if not exists (for backward compatibility)
                self.print_requests[request_id]["stl_file_status"] = {}
                for stl_file in self.print_requests[request_id]["stl_files"]:
                    self.print_requests[request_id]["stl_file_status"][stl_file] = {
                        "printed": False,
                        "print_date": None
                    }
            
            if file_name in self.print_requests[request_id]["stl_file_status"]:
                self.print_requests[request_id]["stl_file_status"][file_name]["printed"] = printed_status
                if printed_status:
                    self.print_requests[request_id]["stl_file_status"][file_name]["print_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    self.print_requests[request_id]["stl_file_status"][file_name]["print_date"] = None
                
                self.save_queue_state()
                print(f"Updated {request_id} - {file_name}: printed = {printed_status}")
                return True
        return False

    def get_stl_completion_status(self, request_id):
        """Get completion status for STL files in a request"""
        if request_id not in self.print_requests:
            return 0, 0
        
        request_data = self.print_requests[request_id]
        
        # Initialize status tracking if not exists (backward compatibility)
        if "stl_file_status" not in request_data:
            request_data["stl_file_status"] = {}
            for stl_file in request_data["stl_files"]:
                request_data["stl_file_status"][stl_file] = {
                    "printed": False,
                    "print_date": None
                }
            self.save_queue_state()
        
        total_files = len(request_data["stl_files"])
        printed_files = sum(1 for status in request_data["stl_file_status"].values() if status["printed"])
        
        return printed_files, total_files

class PrintQueueGUI:
    def __init__(self, queue_manager):
        self.queue_manager = queue_manager
        self.root = tk.Tk()
        self.root.title("Bytes and Bolts Print Queue Manager")
        self.root.geometry("1200x700")  # Slightly larger for better visibility
        
        # Auto-refresh enabled by default
        self.auto_refresh = tk.BooleanVar(value=True)
        self.refresh_interval = 30  # seconds
        
        # **DEFAULT SORTING STATE**
        self.current_sort = "creation_time"  # **DEFAULT: creation_time**
        self.sort_reverse = False
        
        self.setup_gui()
        self.refresh_queue()
        self.start_auto_refresh()
    
    def setup_gui(self):
        # Configure style for better contrast
        style = ttk.Style()
        
        # Set a light theme as the base
        style.theme_use('clam')  # Use clam theme as base for better control
        
        # Configure main window
        self.root.configure(bg="white")
        
        # Configure Treeview for maximum contrast
        style.configure("Treeview", 
                       background="white", 
                       foreground="black", 
                       fieldbackground="white",
                       borderwidth=2,
                       relief="solid")
        
        style.configure("Treeview.Heading", 
                       background="#2c3e50", 
                       foreground="white", 
                       font=("Arial", 11, "bold"),
                       relief="raised",
                       borderwidth=2)
        
        # Configure frames and labels with white background
        style.configure("TFrame", 
                       background="white",
                       relief="flat")
        
        style.configure("TLabelFrame", 
                       background="white", 
                       foreground="black",
                       borderwidth=2,
                       relief="groove")
        
        style.configure("TLabelFrame.Label", 
                       background="white", 
                       foreground="black", 
                       font=("Arial", 11, "bold"))
        
        style.configure("TLabel", 
                       background="white", 
                       foreground="black", 
                       font=("Arial", 10))
        
        style.configure("TButton", 
                       font=("Arial", 10, "bold"),
                       background="#e9ecef",
                       foreground="black")
        
        style.configure("TCheckbutton",
                       background="white",
                       foreground="black",
                       font=("Arial", 10))
        
        style.configure("TCombobox",
                       background="white",
                       foreground="black",
                       fieldbackground="white",
                       borderwidth=1)
        
        # Main frame with white background
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        self.title_label = tk.Label(main_frame, 
                              text="🖨️ Print Queue Manager", 
                              font=("Arial", 20, "bold"), 
                              fg="black",
                              bg="white")
        self.title_label.grid(row=0, column=0, columnspan=5, pady=(0, 15))
        
        # Control buttons frame (with sort status on the same row)
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=5, pady=(0, 15), sticky="ew")
        
        # Left side buttons
        scan_btn = ttk.Button(button_frame, text="🔄 Scan for New Requests", command=self.scan_requests)
        scan_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        open_btn = ttk.Button(button_frame, text="📁 Open Folder", command=self.open_selected_folder)
        open_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Reset sort button
        reset_sort_btn = ttk.Button(button_frame, text="🔄 Reset to Default Sort", command=self.reset_sort)
        reset_sort_btn.pack(side=tk.LEFT, padx=(0, 15))
        
        # Sort status label (positioned to the right of reset button)
        self.sort_status_label = tk.Label(button_frame, 
                                     text="", 
                                     font=("Arial", 11, "bold"), 
                                     fg="green",  # Default to green
                                     bg="white")
        self.sort_status_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Auto-refresh checkbox (far right)
        auto_refresh_cb = ttk.Checkbutton(button_frame, text="Auto-refresh (30s)", variable=self.auto_refresh)
        auto_refresh_cb.pack(side=tk.RIGHT)
    
        # Status filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.grid(row=2, column=0, columnspan=5, pady=(0, 15), sticky="ew")
        
        # Filter label and combobox
        filter_label = tk.Label(filter_frame, 
                           text="Filter by status:", 
                           font=("Arial", 11, "bold"), 
                           fg="black",
                           bg="white")
        filter_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.status_filter = ttk.Combobox(filter_frame, 
                                     values=["All", "waiting", "printing", "completed", "deleted"], 
                                     state="readonly", 
                                     font=("Arial", 10),
                                     width=12)
        self.status_filter.set("All")
        self.status_filter.pack(side=tk.LEFT, padx=(0, 15))
        self.status_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_queue())
        
        # Instructions label
        instructions_label = tk.Label(filter_frame, 
                                 text="💡 Click column headers to sort | Double-click row to manage STL files", 
                                 font=("Arial", 10, "italic"), 
                                 fg="gray",
                                 bg="white")
        instructions_label.pack(side=tk.RIGHT)
    
        # Queue display with clickable headers (updated columns)
        columns = ("Team", "Request", "STL Files", "STL Progress", "Created", "Status", "Queue Position")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=22)
        
        # Configure tree with high contrast colors
        self.tree.tag_configure('waiting', 
                           background='#fff3cd', 
                           foreground='#856404')
        self.tree.tag_configure('printing', 
                           background='#cce7ff', 
                           foreground='#004085')
        self.tree.tag_configure('completed', 
                           background='#d4edda', 
                           foreground='#155724')
        self.tree.tag_configure('deleted', 
                           background='#f8d7da', 
                           foreground='#721c24')
    
        # Define column headings and widths with sorting functionality (updated)
        column_widths = {
            "Team": 80, 
            "Request": 200, 
            "STL Files": 80, 
            "STL Progress": 100,
            "Created": 160, 
            "Status": 120, 
            "Queue Position": 100
        }
        sort_mapping = {
            "Team": "team",
            "Request": "folder_name", 
            "STL Files": "stl_count",
            "Created": "creation_time",
            "Status": "status"
        }
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=column_widths.get(col, 100), anchor="center")
            
            # Add click binding for sortable columns
            if col in sort_mapping:
                self.tree.heading(col, command=lambda c=col: self.sort_by_column(sort_mapping[c]))
    
        # Add double-click binding to open STL file manager
        self.tree.bind("<Double-1>", self.on_item_double_click)
    
        self.tree.grid(row=3, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=3, column=4, sticky=(tk.N, tk.S), pady=(0, 10))
        
        # Status control frame (positioned to the right of the tree)
        status_frame = ttk.LabelFrame(main_frame, text="Update Status", padding="15")
        status_frame.grid(row=3, column=5, padx=(15, 0), sticky=(tk.N, tk.W))
        
        # Status buttons
        printing_btn = ttk.Button(status_frame, text="🖨️ Mark as Printing", 
                             command=lambda: self.update_selected_status("printing"),
                             width=20)
        printing_btn.pack(pady=3, fill=tk.X)
        
        completed_btn = ttk.Button(status_frame, text="✅ Mark as Completed", 
                              command=lambda: self.update_selected_status("completed"),
                              width=20)
        completed_btn.pack(pady=3, fill=tk.X)
        
        waiting_btn = ttk.Button(status_frame, text="⏳ Mark as Waiting", 
                            command=lambda: self.update_selected_status("waiting"),
                            width=20)
        waiting_btn.pack(pady=3, fill=tk.X)
        
        # Separator
        separator = ttk.Separator(status_frame, orient='horizontal')
        separator.pack(pady=8, fill=tk.X)
        
        # Delete options
        delete_from_memory_btn = ttk.Button(status_frame, text="🗑️ Remove from Queue", 
                                       command=self.remove_from_memory,
                                       width=20)
        delete_from_memory_btn.pack(pady=3, fill=tk.X)
        
        delete_folder_btn = ttk.Button(status_frame, text="💀 Delete Folder & Remove", 
                                  command=self.delete_folder_and_remove,
                                  width=20)
        delete_folder_btn.pack(pady=3, fill=tk.X)
        
        # Check deleted button
        check_deleted_btn = ttk.Button(status_frame, text="🔍 Check for Deleted", 
                                  command=self.check_deleted,
                                  width=20)
        check_deleted_btn.pack(pady=8, fill=tk.X)
        
        # Stats frame (bottom of the interface)
        stats_frame = ttk.LabelFrame(main_frame, text="Queue Statistics", padding="15")
        stats_frame.grid(row=4, column=0, columnspan=6, pady=(15, 0), sticky="ew")
        
        # Stats label
        self.stats_label = tk.Label(stats_frame, 
                               text="", 
                               font=("Arial", 12, "bold"), 
                               fg="black",
                               bg="white")
        self.stats_label.pack()
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(3, weight=1)  # Updated to column 3 (tree column)
        main_frame.rowconfigure(3, weight=1)     # Tree row
    
    def scan_requests(self):
        """Scan for new print requests and check for deleted ones"""
        new_count = self.queue_manager.scan_for_requests()
        deleted_count = self.queue_manager.check_for_deleted_requests()
        
        message = []
        if new_count > 0:
            message.append(f"Found {new_count} new requests")
        if deleted_count > 0:
            message.append(f"Detected {deleted_count} deleted requests")
        
        if message:
            messagebox.showinfo("Scan Complete", " | ".join(message))
        else:
            messagebox.showinfo("Scan Complete", "No changes detected.")
        
        self.refresh_queue()
    
    def refresh_queue(self):
        """Refresh the queue display with current sort settings"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get sorted queue using current sort settings
        sorted_queue = self.queue_manager.get_sorted_queue(sort_by=self.current_sort, reverse=self.sort_reverse)
        
        # Apply status filter
        status_filter = self.status_filter.get()
        if status_filter != "All":
            sorted_queue = [(req_id, data) for req_id, data in sorted_queue if data["status"] == status_filter]
        
        # Insert items with colored tags
        waiting_position = 1
        for request_id, data in sorted_queue:
            # Status emoji
            status_emoji = {
                "waiting": "⏳", 
                "printing": "🖨️", 
                "completed": "✅",
                "deleted": "❌"
            }.get(data["status"], "❓")
            
            # Get STL progress
            printed_count, total_count = self.queue_manager.get_stl_completion_status(request_id)
            stl_progress = f"{printed_count}/{total_count}"
            
            # Add progress color
            if printed_count == total_count and total_count > 0:
                stl_progress += " ✅"
            elif printed_count > 0:
                stl_progress += " 🔄"
            
            # Determine row tag based on status
            row_tag = data["status"]
            
            # Queue position (only for waiting items and only when using default sort)
            if data["status"] == "waiting" and self.current_sort == "creation_time" and not self.sort_reverse:
                queue_pos = waiting_position
                waiting_position += 1
            elif data["status"] == "waiting":
                queue_pos = "W"  # Show "W" for waiting when not using fair queue order
            else:
                queue_pos = "-"
            
            self.tree.insert("", tk.END, iid=request_id, 
                            tags=(row_tag,),
                            values=(
                                f"Team {data['team']}",
                                data["folder_name"],
                                len(data["stl_files"]),
                                stl_progress,  # NEW: STL progress column
                                data["creation_date"],
                                f"{status_emoji} {data['status']}",
                                queue_pos
                            ))

        # Update stats and sort indicators
        self.update_stats()
        self.update_sort_indicators()
    
    def update_stats(self):
        """Update queue statistics (updated with deleted count)"""
        total = len(self.queue_manager.print_requests)
        waiting = sum(1 for data in self.queue_manager.print_requests.values() if data["status"] == "waiting")
        printing = sum(1 for data in self.queue_manager.print_requests.values() if data["status"] == "printing")
        completed = sum(1 for data in self.queue_manager.print_requests.values() if data["status"] == "completed")
        deleted = sum(1 for data in self.queue_manager.print_requests.values() if data["status"] == "deleted")
        
        stats_text = f"Total: {total} | ⏳ Waiting: {waiting} | 🖨️ Printing: {printing} | ✅ Completed: {completed} | ❌ Deleted: {deleted}"
        self.stats_label.config(text=stats_text)

    def update_selected_status(self, new_status):
        """Update status of selected items (multiple selection support)"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select one or more requests to update.")
            return
        
        # Handle multiple selections
        if len(selected) == 1:
            request_data = self.queue_manager.print_requests[selected[0]]
            confirm_message = f"Update '{request_data['folder_name']}' from Team {request_data['team']} to '{new_status}'?"
        else:
            confirm_message = f"Update {len(selected)} selected requests to '{new_status}'?\n\nSelected requests:\n"
            for request_id in selected[:5]:  # Show first 5 items
                request_data = self.queue_manager.print_requests[request_id]
                confirm_message += f"• Team {request_data['team']}: {request_data['folder_name']}\n"
            if len(selected) > 5:
                confirm_message += f"... and {len(selected) - 5} more"
        
        # Confirm update
        result = messagebox.askyesno("Confirm Status Update", confirm_message)
        if not result:
            return
        
        # Update all selected items
        updated_count = 0
        failed_count = 0
        
        for request_id in selected:
            if self.queue_manager.update_status(request_id, new_status):
                updated_count += 1
            else:
                failed_count += 1
        
        # Refresh display
        self.refresh_queue()
        
        # Show result
        if failed_count == 0:
            messagebox.showinfo("Update Complete", f"Successfully updated {updated_count} request(s) to '{new_status}'")
        else:
            messagebox.showwarning("Update Partial", f"Updated {updated_count} request(s), failed to update {failed_count}")

    def check_deleted(self):
        """Check for deleted requests"""
        deleted_count = self.queue_manager.check_for_deleted_requests()
        if deleted_count > 0:
            messagebox.showinfo("Check Complete", f"Found {deleted_count} deleted requests!")
        else:
            messagebox.showinfo("Check Complete", "No deleted requests found.")
        self.refresh_queue()

    def remove_from_memory(self):
        """Remove selected requests from memory/queue (multiple selection support)"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select one or more requests to remove.")
            return
        
        # Handle multiple selections
        if len(selected) == 1:
            request_data = self.queue_manager.print_requests[selected[0]]
            confirm_message = f"Remove '{request_data['folder_name']}' from Team {request_data['team']} from the queue?\n\nThis will only remove it from the program memory, not delete the actual folder."
        else:
            confirm_message = f"Remove {len(selected)} selected requests from the queue?\n\nThis will only remove them from the program memory, not delete the actual folders.\n\nSelected requests:\n"
            for request_id in selected[:5]:  # Show first 5 items
                request_data = self.queue_manager.print_requests[request_id]
                confirm_message += f"• Team {request_data['team']}: {request_data['folder_name']}\n"
            if len(selected) > 5:
                confirm_message += f"... and {len(selected) - 5} more"
        
        # Confirm removal
        result = messagebox.askyesno("Confirm Removal", confirm_message)
        if not result:
            return
        
        # Remove all selected items
        removed_count = 0
        failed_count = 0
        
        for request_id in selected:
            if self.queue_manager.remove_request_from_memory(request_id):
                removed_count += 1
            else:
                failed_count += 1
        
        # Refresh display
        self.refresh_queue()
        
        # Show result
        if failed_count == 0:
            messagebox.showinfo("Removal Complete", f"Successfully removed {removed_count} request(s) from queue")
        else:
            messagebox.showwarning("Removal Partial", f"Removed {removed_count} request(s), failed to remove {failed_count}")

    def delete_folder_and_remove(self):
        """Delete folders from Google Drive and remove from memory (multiple selection support)"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select one or more requests to delete.")
            return
        
        # Handle multiple selections
        if len(selected) == 1:
            request_data = self.queue_manager.print_requests[selected[0]]
            confirm_message = f"⚠️ PERMANENTLY DELETE '{request_data['folder_name']}' from Team {request_data['team']}?\n\nThis will:\n• Delete the folder from Google Drive\n• Remove it from the queue\n• This action CANNOT be undone!"
        else:
            confirm_message = f"⚠️ PERMANENTLY DELETE {len(selected)} selected folders?\n\nThis will:\n• Delete ALL selected folders from Google Drive\n• Remove them from the queue\n• This action CANNOT be undone!\n\nSelected requests:\n"
            for request_id in selected[:5]:  # Show first 5 items
                request_data = self.queue_manager.print_requests[request_id]
                confirm_message += f"• Team {request_data['team']}: {request_data['folder_name']}\n"
            if len(selected) > 5:
                confirm_message += f"... and {len(selected) - 5} more"
        
        # Double confirmation for deletion
        result = messagebox.askyesno("⚠️ CONFIRM PERMANENT DELETION", confirm_message, icon="warning")
        if not result:
            return
        
        # Second confirmation for multiple deletions
        if len(selected) > 1:
            final_confirm = messagebox.askyesno("⚠️ FINAL CONFIRMATION", 
                                          f"Are you ABSOLUTELY SURE you want to permanently delete {len(selected)} folders?\n\nThis action cannot be undone!", 
                                          icon="warning")
            if not final_confirm:
                return
        
        # Delete all selected items
        deleted_count = 0
        failed_count = 0
        
        for request_id in selected:
            # Try to delete folder first
            if self.queue_manager.delete_request_folder(request_id):
                # If successful, remove from memory
                if self.queue_manager.remove_request_from_memory(request_id):
                    deleted_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
        
        # Refresh display
        self.refresh_queue()
        
        # Show result
        if failed_count == 0:
            messagebox.showinfo("Deletion Complete", f"Successfully deleted {deleted_count} folder(s) and removed from queue")
        else:
            messagebox.showwarning("Deletion Partial", f"Deleted {deleted_count} folder(s), failed with {failed_count}")

    def open_selected_folder(self):
        """Open the folders for the selected requests (multiple selection support)"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select one or more requests to open their folders.")
            return
        
        # Limit number of folders that can be opened at once (to prevent system overload)
        max_folders = 10
        if len(selected) > max_folders:
            result = messagebox.askyesno("Too Many Folders", 
                                   f"You selected {len(selected)} folders. Opening too many folders at once may slow down your system.\n\n"
                                   f"Do you want to open only the first {max_folders} folders?")
            if result:
                selected = selected[:max_folders]
            else:
                return
        
        opened_count = 0
        failed_count = 0
        
        for request_id in selected:
            folder_path = self.queue_manager.print_requests[request_id]["folder_path"]
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(folder_path)
                elif os.name == 'posix':  # macOS/Linux
                    os.system(f'open "{folder_path}"')
                opened_count += 1
            except Exception as e:
                failed_count += 1
                print(f"Error opening folder {folder_path}: {e}")
        
        # Show result
        if failed_count == 0:
            messagebox.showinfo("Folders Opened", f"Successfully opened {opened_count} folder(s)")
        else:
            messagebox.showwarning("Some Folders Failed", f"Opened {opened_count} folder(s), failed to open {failed_count}")
    
    def start_auto_refresh(self):
        """Start auto-refresh in background thread (updated to check for deleted)"""
        def auto_refresh_worker():
            while True:
                time.sleep(self.refresh_interval)
                if self.auto_refresh.get():
                    # Check for new requests and deleted requests, then refresh
                    self.queue_manager.scan_for_requests()
                    self.queue_manager.check_for_deleted_requests()
                    self.root.after(0, self.refresh_queue)  # Update GUI in main thread
        
        refresh_thread = threading.Thread(target=auto_refresh_worker, daemon=True)
        refresh_thread.start()
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()

    def sort_by_column(self, column):
        """Sort by the specified column"""
        # If clicking the same column, reverse the order
        if self.current_sort == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.current_sort = column
            self.sort_reverse = False
        
        self.update_sort_indicators()
        self.refresh_queue()

    def reset_sort(self):
        """Reset to default sorting (creation_time, oldest first)"""
        self.current_sort = "creation_time"  # **RESET TO DEFAULT**
        self.sort_reverse = False
        self.update_sort_indicators()
        self.refresh_queue()

    def update_sort_indicators(self):
        """Update the UI to show current sort status"""
        # Update column headers with sort indicators
        column_mapping = {
            "team": "Team",
            "folder_name": "Request", 
            "stl_count": "STL Files",
            "creation_time": "Created",
            "status": "Status"
        }
        
        # Reset all column headers
        for col in ["Team", "Request", "STL Files", "Created", "Status", "Queue Position"]:
            if col in column_mapping.values():
                base_text = col
                if col == column_mapping.get(self.current_sort):
                    # Add sort indicator to current sort column
                    arrow = " ▼" if not self.sort_reverse else " ▲"
                    self.tree.heading(col, text=base_text + arrow)
                else:
                    self.tree.heading(col, text=base_text)
    
        # Update sort status label with appropriate colors
        if self.current_sort != "creation_time":
            # **RED WARNING when not using default sort**
            sort_name = {
                "team": "Team Number",
                "folder_name": "Request Name", 
                "stl_count": "File Count",
                "status": "Status Priority"
            }.get(self.current_sort, self.current_sort)
            
            direction = "Descending" if self.sort_reverse else "Ascending"
            self.sort_status_label.config(
                text=f"⚠️ NOT DEFAULT SORT\nSorted by: {sort_name} ({direction})",
                fg="red"
            )
        else:
            if self.sort_reverse:
                # **RED WARNING if creation time is reversed (newest first)**
                self.sort_status_label.config(
                    text="⚠️ SORT REVERSED\nNewest First - Not Fair!",
                    fg="red"
                )
            else:
                # **GREEN when using default fair queue sorting**
                self.sort_status_label.config(
                    text="✅ Default Fair Queue\nOldest First",
                    fg="green"
                )

    def on_item_double_click(self, event):
        """Handle double-click on tree item to open STL file manager"""
        selected = self.tree.selection()
        if selected:
            self.open_stl_manager(selected[0])

    def open_stl_manager(self, request_id):
        """Open STL file management window"""
        if request_id not in self.queue_manager.print_requests:
            return
        
        request_data = self.queue_manager.print_requests[request_id]
        
        # Create new window
        stl_window = tk.Toplevel(self.root)
        stl_window.title(f"STL Files - Team {request_data['team']} - {request_data['folder_name']}")
        stl_window.geometry("500x400")
        stl_window.configure(bg="white")
        
        # Make window modal
        stl_window.transient(self.root)
        stl_window.grab_set()
        
        # Header
        header_label = tk.Label(stl_window, 
                           text=f"🖨️ STL Files for Team {request_data['team']}\n{request_data['folder_name']}", 
                           font=("Arial", 14, "bold"), 
                           fg="black", bg="white")
        header_label.pack(pady=10)
        
        # Progress info
        printed_count, total_count = self.queue_manager.get_stl_completion_status(request_id)
        progress_label = tk.Label(stl_window, 
                             text=f"Progress: {printed_count}/{total_count} files printed", 
                             font=("Arial", 12), 
                             fg="blue", bg="white")
        progress_label.pack(pady=5)
        
        # Create frame for file list
        list_frame = ttk.Frame(stl_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # File list with checkboxes
        canvas = tk.Canvas(list_frame, bg="white")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Store checkboxes for updates
        checkboxes = {}
        
        # Initialize status if not exists
        if "stl_file_status" not in request_data:
            request_data["stl_file_status"] = {}
            for stl_file in request_data["stl_files"]:
                request_data["stl_file_status"][stl_file] = {
                    "printed": False,
                    "print_date": None
                }
    
        # Create checkbox for each STL file
        for i, file_name in enumerate(sorted(request_data["stl_files"])):
            file_frame = ttk.Frame(scrollable_frame)
            file_frame.pack(fill=tk.X, pady=2)
            
            # Get current status
            file_status = request_data["stl_file_status"].get(file_name, {"printed": False, "print_date": None})
            
            # Checkbox variable
            var = tk.BooleanVar(value=file_status["printed"])
            checkboxes[file_name] = var
            
            # Checkbox
            checkbox = ttk.Checkbutton(file_frame, 
                                  variable=var,
                                  command=lambda fn=file_name, v=var: self.update_stl_status(request_id, fn, v.get(), progress_label, stl_window))
            checkbox.pack(side=tk.LEFT)
            
            # File name
            file_label = tk.Label(file_frame, 
                             text=file_name, 
                             font=("Arial", 10), 
                             fg="black", bg="white")
            file_label.pack(side=tk.LEFT, padx=(5, 0))
            
            # Print date if available
            if file_status["printed"] and file_status["print_date"]:
                date_label = tk.Label(file_frame, 
                                 text=f"(Printed: {file_status['print_date']})", 
                                 font=("Arial", 8), 
                                 fg="green", bg="white")
                date_label.pack(side=tk.RIGHT)
    
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
        # Buttons frame
        button_frame = ttk.Frame(stl_window)
        button_frame.pack(pady=10)
    
        # Mark All / Clear All buttons
        mark_all_btn = ttk.Button(button_frame, text="✅ Mark All Printed", 
                             command=lambda: self.mark_all_stl_files(request_id, True, checkboxes, progress_label, stl_window))
        mark_all_btn.pack(side=tk.LEFT, padx=5)
        
        clear_all_btn = ttk.Button(button_frame, text="❌ Clear All", 
                              command=lambda: self.mark_all_stl_files(request_id, False, checkboxes, progress_label, stl_window))
        clear_all_btn.pack(side=tk.LEFT, padx=5)
        
        # Close button
        close_btn = ttk.Button(button_frame, text="Close", command=stl_window.destroy)
        close_btn.pack(side=tk.LEFT, padx=15)
        
        # Center the window
        stl_window.update_idletasks()
        x = (stl_window.winfo_screenwidth() // 2) - (stl_window.winfo_width() // 2)
        y = (stl_window.winfo_screenheight() // 2) - (stl_window.winfo_height() // 2)
        stl_window.geometry(f"+{x}+{y}")

    def update_stl_status(self, request_id, file_name, printed_status, progress_label, window):
        """Update STL file status and refresh display"""
        self.queue_manager.update_stl_file_status(request_id, file_name, printed_status)
        
        # Update progress label
        printed_count, total_count = self.queue_manager.get_stl_completion_status(request_id)
        progress_label.config(text=f"Progress: {printed_count}/{total_count} files printed")
        
        # Refresh main window
        self.refresh_queue()

    def mark_all_stl_files(self, request_id, printed_status, checkboxes, progress_label, window):
        """Mark all STL files as printed or not printed"""
        for file_name, var in checkboxes.items():
            var.set(printed_status)
            self.queue_manager.update_stl_file_status(request_id, file_name, printed_status)
        
        # Update progress label
        printed_count, total_count = self.queue_manager.get_stl_completion_status(request_id)
        progress_label.config(text=f"Progress: {printed_count}/{total_count} files printed")
        
        # Refresh main window
        self.refresh_queue()
        
        # Close and reopen window to show updated dates
        window.destroy()
        self.open_stl_manager(request_id)

def main():
    # Hardcoded path - no user input needed
    base_directory = "/Users/gulliverwright/Library/CloudStorage/GoogleDrive-vicepresident@biomed.activateuts.com.au/My Drive/Bytes and Bolts Print Submissions"
    
    if not os.path.exists(base_directory):
        print(f"❌ Directory not found: {base_directory}")
        print("Please check the path and try again.")
        return
    
    print(f"✅ Using directory: {base_directory}")
    
    # Initialize queue manager
    queue_manager = PrintQueueManager(base_directory)
    
    # Initial scan
    print("🔍 Scanning for existing print requests...")
    queue_manager.scan_for_requests()
    
    # Start GUI
    print("🚀 Starting Print Queue Manager...")
    gui = PrintQueueGUI(queue_manager)
    gui.run()

if __name__ == "__main__":
    main()
================================================================================
3D PRINT QUEUE MANAGER - USER MANUAL
Bytes and Bolts Biomedical Engineering Society
================================================================================

TABLE OF CONTENTS:
1. Overview
2. Setup Instructions
3. File Structure Requirements
4. How to Use the Interface
5. Managing Print Requests
6. Troubleshooting
7. Technical Notes

================================================================================
1. OVERVIEW
================================================================================

The 3D Print Queue Manager is a Python application that helps manage printing
requests from multiple teams. It automatically scans a Google Drive folder for
STL files and maintains a fair first-come-first-served printing queue.

Key Features:
• Automatic detection of new print requests
• Fair queue ordering (oldest requests first)
• Individual STL file tracking within each request
• Batch operations for efficiency
• Persistent state storage
• Auto-refresh capabilities

================================================================================
2. SETUP INSTRUCTIONS
================================================================================

PREREQUISITES:
• Python 3.6 or newer installed
• Google Drive desktop app installed and synced
• Access to the "Bytes and Bolts Print Submissions" folder

INSTALLATION:
1. Download the print-queue.py script
2. Place it in a convenient location on your computer
3. Ensure you have read/write permissions in that directory
4. Verify the Google Drive folder path in the script matches your system

FIRST RUN:
1. Open Terminal (Mac/Linux) or Command Prompt (Windows)
2. Navigate to the script location: cd /path/to/script/
3. Run: python print-queue.py
4. The GUI will open and scan for existing requests

================================================================================
3. FILE STRUCTURE REQUIREMENTS
================================================================================

The script expects this exact Google Drive folder structure:

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
...
└── 📁 team 14/

IMPORTANT NAMING CONVENTIONS:
• Team folders MUST be named: "team 1", "team 2", ..., "team 14"
• Use lowercase "team" followed by space and number
• Project folders can have any name
• Only .stl files are recognized as print requests

WHAT CREATES A PRINT REQUEST:
• Any folder inside a team folder that contains .stl files
• The folder creation time determines queue position
• Each .stl file within the folder is tracked individually

================================================================================
4. HOW TO USE THE INTERFACE
================================================================================

MAIN WINDOW LAYOUT:
┌─────────────────────────────────────────────────────────────────┐
│ 🖨️ Print Queue Manager                                          │
│                                                                 │
│ [🔄 Scan] [📁 Open] [🔄 Reset Sort]  ✅ Default Fair Queue    │
│                                                                 │
│ Filter: [All ▼]   💡 Click headers to sort | Double-click rows │
│                                                                 │
│ ┌─────────────────────────────────────────┐ ┌─────────────────┐ │
│ │ Team │ Request │ Files │ Progress │ ... │ │ Update Status   │ │
│ │  1   │ Part A  │   3   │  2/3 🔄  │ ... │ │ [🖨️ Printing]   │ │
│ │  2   │ Robot   │   5   │  0/5     │ ... │ │ [✅ Completed]  │ │
│ │  3   │ Sensor  │   1   │  1/1 ✅  │ ... │ │ [⏳ Waiting]    │ │
│ └─────────────────────────────────────────┘ │ [🗑️ Remove]     │ │
│                                             │ [💀 Delete]     │ │
│ Stats: Total: 15 | ⏳ Waiting: 8 | 🖨️ ...   │ [🔍 Check Del]  │ │
└─────────────────────────────────────────────┴─────────────────┘

MAIN BUTTONS:
• 🔄 Scan for New Requests: Manually check for new folders
• 📁 Open Folder: Open selected request folders in file explorer
• 🔄 Reset to Default Sort: Return to fair queue ordering
• Auto-refresh checkbox: Enable/disable automatic scanning (30s)

QUEUE COLUMNS:
• Team: Team number (1-14)
• Request: Project folder name
• STL Files: Number of .stl files in the request
• STL Progress: How many files have been printed (e.g., "2/3 🔄")
• Created: When the folder was created
• Status: Current print status with emoji
• Queue Position: Position in fair queue (only for waiting items)

STATUS MEANINGS:
⏳ waiting   - New request, not started
🖨️ printing  - Currently being printed
✅ completed - All files printed successfully
❌ deleted   - Folder removed from Google Drive

================================================================================
5. MANAGING PRINT REQUESTS
================================================================================

VIEWING REQUESTS:
• The table shows all requests sorted by creation time (oldest first)
• Use the filter dropdown to show only specific statuses
• Click column headers to sort by different criteria
• The sort status indicator shows if you're using fair queue ordering

SELECTING REQUESTS:
• Click once to select a single request
• Hold Ctrl (Windows/Linux) or Cmd (Mac) and click to select multiple
• Use Shift+click to select a range of requests

UPDATING STATUS:
1. Select one or more requests in the table
2. Click the appropriate status button on the right:
   • 🖨️ Mark as Printing: When you start printing
   • ✅ Mark as Completed: When printing is finished
   • ⏳ Mark as Waiting: To reset status back to waiting

MANAGING STL FILES:
1. Double-click any request row to open the STL File Manager
2. Check/uncheck individual files as they are printed
3. Use "Mark All Printed" or "Clear All" for batch operations
4. Print dates are automatically recorded when files are marked as printed

OPENING FOLDERS:
1. Select one or more requests
2. Click "📁 Open Folder" to open them in your file explorer
3. Maximum 10 folders can be opened at once (to prevent system slowdown)

REMOVING REQUESTS:
• 🗑️ Remove from Queue: Removes from the program memory only
• 💀 Delete Folder & Remove: Permanently deletes the folder from Google Drive
• Use with caution - deletions cannot be undone!

CHECKING FOR CHANGES:
• 🔍 Check for Deleted: Manually scan for folders that were removed
• Auto-refresh (if enabled) does this automatically every 30 seconds

================================================================================
6. TROUBLESHOOTING
================================================================================

COMMON ISSUES:

"Directory not found" error:
• Check that Google Drive is synced and the folder exists
• Verify the path in the script matches your Google Drive location
• Ensure you have access permissions to the folder

No requests showing up:
• Make sure team folders are named correctly ("team 1", "team 2", etc.)
• Verify .stl files exist in project subfolders
• Try clicking "🔄 Scan for New Requests"

GUI appears blank or freezes:
• Close and restart the application
• Check that no other instance is running
• Ensure you have sufficient system memory

Sort indicator shows red warning:
• Click "🔄 Reset to Default Sort" to return to fair queue ordering
• Red warnings indicate you're not using first-come-first-served ordering

Files not opening:
• Check that file explorer is working on your system
• Verify the folder paths are valid
• Try opening folders manually to test permissions

STATE FILE ISSUES:
• If the program behaves strangely, you can delete "print_queue_state.json"
• This will reset all status tracking but preserve the folder structure
• The file is automatically recreated when you restart the program

================================================================================
7. TECHNICAL NOTES
================================================================================

DATA STORAGE:
• Queue state is saved in "print_queue_state.json" in the script directory
• This file contains all request history and print tracking
• The file is human-readable and can be edited manually if needed

QUEUE ORDERING:
• Default sort uses folder creation time (oldest first)
• This ensures fair first-come-first-served processing
• Other sorting options are available but may not be fair

PERFORMANCE:
• Auto-refresh scans the entire folder structure every 30 seconds
• For large numbers of requests, consider disabling auto-refresh
• Manual scanning is always available via the scan button

PLATFORM COMPATIBILITY:
• Tested on Windows, macOS, and Linux
• Folder opening uses platform-specific commands
• File paths are handled automatically for cross-platform compatibility

BACKUP RECOMMENDATIONS:
• Regularly backup the "print_queue_state.json" file
• Consider keeping a copy of printed request folders
• Google Drive provides automatic version history

CUSTOMIZATION:
• Modify the base_directory path in main() for different locations
• Adjust refresh_interval for different auto-refresh speeds
• Team count can be modified by changing the range(1, 15) in scan_for_requests()

================================================================================
For technical support or feature requests, contact the Bytes and Bolts 
Biomedical Engineering Society technical team.

Last updated: June 2025
================================================================================
# Servo Control System - Data Flow Diagrams

## 1. General Servo Movement from Individual Controls

```mermaid
graph TD
    A[User moves slider/enters value] --> B[ServoControlWidget validation]
    B --> C{Valid input?}
    C -->|No| D[Show error message]
    C -->|Yes| E[Update GUI variable]
    E --> F[Call _send_servo_command]
    F --> G[Get servo index from config]
    G --> H[SerialConnection.send_command]
    H --> I{Connected?}
    I -->|No| J[Log not connected]
    I -->|Yes| K[Send SP:index:pulse to ESP32]
    K --> L[ESP32 -> PCA9685 -> Servo]
    F --> M[State.update_servo_position]
    M --> N[Publish COMPONENT_POSITION_CHANGED]
    N --> O[All subscribed widgets update]
```

**Notes:**
- Slider throttling (50ms) prevents command flooding
- Range validation happens at GUI level before sending
- State updates occur regardless of connection status for GUI consistency, but none of the signals will be sent
- Event system ensures all widgets showing same component stay synchronised

---

## 2. Configuring Individual Attributes (Name Changes, etc...)

```mermaid
graph TD
    A[User modifies component attribute] --> B{Attribute type}
    B -->|Name| C[_on_rename_entry]
    B -->|Range| D[_on_range_entry]
    B -->|Default| E[_on_default_entry]
    B -->|Index| F[_on_index_entry]
    
    C --> G[State.rename_component]
    G --> H[Update servo_configurations dict]
    H --> I[Update component_groups lists]
    I --> J[Publish COMPONENT_SETTING_CHANGED]
    J --> K[Trigger widget recreation]
    
    D --> L[State.update_component_pulse_range]
    L --> M[Validate min < max]
    M --> N[Update config + clamp positions]
    N --> O[Publish COMPONENT_RANGE_CHANGED]
    
    F --> P{Index occupied?}
    P -->|Yes| Q[State.swap_component_indices]
    P -->|No| R[Direct assignment]
    Q --> S[Publish COMPONENT_INDEX_SWAPPED]
    R --> T[Publish COMPONENT_SETTING_CHANGED]
```

**Notes:**
- Component groups remain fixed for order authority, only names change
- Index swapping is automatic when target index is occupied


---

## 3. Sequence Recording

```mermaid
graph TD
    A[User clicks 'Record Step'] --> B[Get delay value from GUI]
    B --> C[SequenceManager.record_keyframe]
    C --> D[State.get_current_component_positions]
    D --> E[Calculate absolute time]
    E --> F[Validate timing constraints]
    F --> G{Valid?}
    G -->|No| H[Return error message]
    G -->|Yes| I[Validate component positions]
    I --> J{Positions valid?}
    J -->|No| K[Return validation error]
    J -->|Yes| L[Create keyframe object]
    L --> M[Add to sequence_data.keyframes]
    M --> N[Update metadata counters]
    N --> O[Publish SEQUENCE_KEYFRAME_ADDED]
    O --> P[Update timeline visualisation]
    P --> Q[Refresh step tree display]
```

**Notes:**
- Time is cumulative - each keyframe has absolute time from sequence start
- Validation ensures sequence doesn't exceed 120-second, but you can easily extend or shorten this in `validation.py` from the variable `MAX_SEQUENCE_DURATION`

---

## 4. Sequence Playing

```mermaid
graph TD
    A[User clicks 'Play Sequence'] --> B{Connection check}
    B -->|Not connected| C[Show error message]
    B -->|Connected| D[PlaybackManager.start_playback]
    D --> E[Spawn background thread]
    E --> F[Record playback start time]
    F --> G[Move to first keyframe immediately]
    G --> H[Main playback loop]
    H --> I[Calculate elapsed time]
    I --> J[Find current keyframe by time]
    J --> K{New keyframe?}
    K -->|No| L[Sleep 10ms, continue loop]
    K -->|Yes| M[Resolve component positions to commands]
    M --> N[SerialConnection.send_batch_commands]
    N --> O[5ms delay between commands]
    O --> P{More keyframes?}
    P -->|Yes| L
    P -->|No| Q[Playback complete]
    Q --> R[Cleanup thread state]
```

**Notes:**
- Precise timing using absolute timestamps, not cumulative delays
- Commands sent in batches with 5ms intervals to prevent ESP32 overflow
- Timeline animation plays to show progress

---

## 5. Camera Sweeping to Display

```mermaid
graph TD
    A[User selects camera] --> B[_on_camera_changed]
    B --> C[Stop any existing camera]
    C --> D[CameraManager.get_camera_index_from_selection]
    D --> E{Valid camera?}
    E -->|No| F[Show fallback image]
    E -->|Yes| G[Create ThreadedCameraCapture]
    G --> H[Initialise cv2.VideoCapture]
    H --> I{Camera opens?}
    I -->|No| J[Show error, fallback image]
    I -->|Yes| K[Start background capture thread]
    K --> L[Configure capture properties]
    L --> M[Continuous frame grabbing loop]
    M --> N[Put frames in queue - max 2]
    N --> O[Main GUI timer _update_display]
    O --> P[Get latest frame from queue]
    P --> Q{Frame available?}
    Q -->|No| R[Continue timer loop]
    Q -->|Yes| S[Process through facial tracker]
    S --> T[Resize and convert frame]
    T --> U[Update canvas display]
```

**Notes:**
- Camera enumeration limited to indices 0-2 for performance (hardware limitation)
- Background thread prevents GUI freezing during camera operations
- Camera initialisation can take 2-6 seconds during swwep, it depends on the hardware of the camera and how many cameras are connected to ur device

---

## 6. Start to Stop Facial Tracking with Servo Movement

```mermaid
graph TD
    A[User clicks 'Start Tracking'] --> B{Camera active?}
    B -->|No| C[Show error message]
    B -->|Yes| D[FacialTracker.start_tracking]
    D --> E[Initialise MediaPipe face detection]
    E --> F[Get eye component names from head group]
    F --> G[Start blink animation thread]
    G --> H[Set confidence threshold 85%]
    H --> I[Main tracking loop in process_frame]
    I --> J[Convert frame BGR->RGB]
    J --> K[MediaPipe face detection]
    K --> L{Faces detected?}
    L -->|No| M[Start no-face timer]
    M --> N{Timer expired?}
    N -->|Yes| O[Return to default positions incrementally]
    N -->|No| I
    L -->|Yes| P[Filter by confidence threshold]
    P --> Q[Calculate face center coordinates]
    Q --> R[Check movement threshold]
    R --> S{Significant movement?}
    S -->|No| I
    S -->|Yes| T[Calculate incremental servo adjustments]
    T --> U[Apply smoothing and limits]
    U --> V[Send servo commands]
    V --> W[Update state positions]
    W --> I
    
    X[User clicks 'Stop Tracking'] --> Y[Stop background threads]
    Y --> Z[Return servos to defaults]
    Z --> AA[Reset tracking state]
```

**Notes:**
- Face detection requires 85% confidence to prevent false positives but the actual camera quality is shit... 
- Incremental position adjustment (not absolute) for smooth movement
- Multiple face switching every 8-16 seconds randomly
- Automatic return to default after 4-6 seconds of no faces
- Blink animation runs independently every 6-13 seconds

---

## 7. Loading and Saving Configs and Sequences as JSON

```mermaid
graph TD
    A[User clicks Save/Load] --> B{Save or Load?}
    
    B -->|Save Config| C[State.save_config_to_file]
    C --> D[filedialog.asksaveasfilename]
    D --> E[Create config_data structure]
    E --> F[Include component_groups for order]
    F --> G[Include servo_configurations]
    G --> H[json.dump to file]
    H --> I[Show success message]
    
    B -->|Load Config| J[ConfigDialog.show_dialog]
    J --> K[filedialog.askopenfilename]
    K --> L[json.load from file]
    L --> M[Validate structure]
    M --> N{Valid format?}
    N -->|No| O[Show error message]
    N -->|Yes| P[Create ServoState with config]
    P --> Q[Update GUI with new config]
    
    B -->|Save Sequence| R[SequenceManager.save_sequence]
    R --> S[Include metadata + keyframes]
    S --> T[Include servo_configurations for reference]
    T --> U[json.dump to file]
    
    B -->|Load Sequence| V[SequenceManager.load_sequence]
    V --> W[Validate keyframe structure]
    W --> X[Update sequence_data]
    X --> Y[Recalculate timing consistency]
    Y --> Z[Publish SEQUENCE_LOADED]
    Z --> AA[Update timeline and displays]
```

**Notes:**
- Config files include component groups to preserve display order
- Sequence files include servo configurations for validation reference
- Loading validates JSON structure before applying changes
- Timing recalculation ensures sequence consistency after loading
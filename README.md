# biomed_soc_proj_2025
 Contains all code for robotics system in the biomedical society 2025 project

 `v1-servo-control-gui`: Uses smoothing factor with no velocity editing, contains the corresponding esp_listening_code needed by the esp to work with this GUI

 `v2-servo-control-gui`: Uses velocity graph and no smoothing factor, contains corresponding esp_listening_code needed by esp to work with this GUI

 `v3-servo-control-gui`: Has no velocity or smoothing factor (for now), GUI now uses raw pulse width values, allows cuonfiguration of pulse ranges, default values and dynamic pin assignment; allows basic sequence recording with updated visual display; has a command terminal for alterantive interactive interface; includes a video/camera display of robot eyes; To run, execute `main.py`


- Make sure to have the `Markdown Preview Merma` extension in vs code to see the `.md` files
- Use the 'v3-servo-control-GUI' and run 'main.py'; ensure all the libraries in the requirements.txt is installed first; do it via `pip install -r requirements.txt` 

- Don't press 'start tacking' for the camera until you have configured the min max ranges and default value of the eye components AND have connected to the serial port (this is just for safety cos i cant anticipate the bugs that might occur, but it will work regardless)

- Don't press 'refresh cameras' unless you absolutely need to (i.e connecting a new camera device while the GUI is opened), because it may cause the GUI to freeze as it sweeps for all connected camera devices. If you press it and it looks like the GUI is frozen, click the camera source again and reselect the camera device, or select 'no-camera' then your camera device.

- eye_horizontal and eye_vertical are the slider controls that have been mapped to the facial tracking, so even tho you can change their names to be something else, changing the name of another component like "head_3" to "eye_horizontal" will not map the facial tracking to that control, so you have to stick with the first slider and second slider, but that's why you have the dynamic pin assignment, you just name the component

- Youcan sequence record while the camera is active/facial tracking


 **For Biomed/Software Team:** 
 - Refer to to `files > 2025 > software_files > python_env.docx` on teams channel for current python version and libraries needed to run this project; Any new libraries used need to be recorded in `python_env.docx`
 - Use `github desktop` or `git` to clone this main branch for up to date servo gui control
 - Any modifications made to the code must be committed into the `origin/Staging-area---MERGE-TO-ME---DONT-DELETE` branch, do not commit any changes to `main` 
 - Ensure `esp_code` is uploaded to esp before running corresponding GUI



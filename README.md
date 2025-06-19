# biomed_soc_proj_2025
 Contains all code for robotics system in the biomedical society 2025 project

 `v1-servo-control-gui`: Uses smoothing factor with no velocity editing, contains the corresponding esp_listening_code needed by the esp to work with this GUI

 `v2-servo-control-gui`: Uses velocity graph and no smoothing factor, contains corresponding esp_listening_code needed by esp to work with this GUI

 `v3-servo-control-gui`: Has no velocity or smoothing factor (for now), GUI now uses raw pulse width values, allows cuonfiguration of pulse ranges, default values and dynamic pin assignment; allows basic sequence recording with updated visual display; has a command terminal for alterantive interactive interface; includes a video/camera display of robot eyes (no tracking implemented yet); ensure to upload this esp code before using the GUI. To run, execute `main.py`

 **For Biomed/Software Team:** 
 - Refer to to `files > 2025 > software_files > python_env.docx` on teams channel for current python version and libraries needed to run this project; Any new libraries used need to be recorded in `python_env.docx`
 - Use `github desktop` or `git` to clone this main branch for up to date servo gui control
 - Any modifications made to the code must be committed into the `origin/Staging-area---MERGE-TO-ME---DONT-DELETE` branch, do not commit any changes to `main` 
 - Ensure `esp_code` is uploaded to esp before running corresponding GUI



#TO ADD
- tqdm for loading bar for gui i.e when searching for available cameras connected to device
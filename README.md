# biomed_soc_proj_2025
 Contains all code for robotics system in the biomedical society 2025 project

 `v1-servo-control-gui`: Uses smoothing factor with no velocity editing, contains the corresponding esp_listening_code needed by the esp to work with this GUI

 `v2-servo-control-gui`: Uses velocity graph and no smoothing factor, contains corresponding esp_listening_code needed by esp to work with this GUI

 **For Biomed/Software Team:** 
 - Refer to to `files > 2025 > software_files > python_env.docx` on teams channel for current python version and libraries needed to run this project; Any new libraries used need to be recorded in `python_env.docx`
 - Use `github desktop` or `git` to clone this main branch for up to date servo gui control
 - Any modifications made to the code must be committed into the `origin/Staging-area---MERGE-TO-ME---DONT-DELETE` branch, do not commit any changes to `main` 
 - Ensure `esp_code` is uploaded to esp before running corresponding GUI


 **Future changes needed:**
 - Need to modify individual controls display: the scroll bar to individuall control n number of servos doesn't work so you can only individually control the servos you see; the current work around is to use the velocity editor and `add keyframes` to the current sequence or use the master control; potentially use a fixced 5 x 6 grid space since max servos allowed is 30 (can be changed in code but please note this down somewhere so we know)
- Add dynamic servo updating where we can update the number of servos to control/initialise while the gui is opened; will need to clear refresh any current information in the GUI for house keeping purposes

**TO DO (adri):**
- Upadte `flow_diagrams_for_bap`
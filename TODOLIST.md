# Project TODO List

This list outlines the development tasks for the Wood Sorting System.

## Phase 1: Project Setup & Organization

- [ ] Create a `requirements.txt` file to manage Python dependencies.
- [ ] Move Python scripts (`TopPanel.py`, `stitching.py`, `inspectura.py`) into the `Python_Files` directory.
- [ ] Update import paths in `inspectura.py` to reflect the new file structure.
- [ ] Refactor hardcoded model paths in `TopPanel.py` to use relative paths.

## Phase 2: Core Software Development (June 2025, Week 2–3)

### A. `toppanel.py` (Defect Detection)

- [ ] Add multi-class classification visualization (e.g., different color boxes for different defects).
- [ ] Implement robust failure handling (e.g., for camera connection loss or bad frames).
- [ ] Improve frame annotation with more detailed information (defect type, confidence).
- [ ] Enhance data export to save grading results in a structured format (JSON or logs).

### B. `stitching.py` (Image Stitching)

- [ ] Automate the image capture trigger instead of relying on a key press.
- [ ] Optimize stitching reliability and handle cases where stitching fails.
- [ ] Apply OpenCV preprocessing (denoising, contrast adjustment) to images before stitching to improve quality.
- [ ] Save intermediate (pre-stitched) and final stitched images for debugging purposes.

### C. `inspectura.py` (Control Panel)

- [ ] Add comprehensive logging with timestamps and decisions made.
- [ ] Implement CSV logging for all grading decisions to track performance over time.
- [ ] (Optional) Explore adding a simple GUI or remote control interface.

## Phase 3: Hardware Integration (June 2025, Week 3)

### A. `stepper.ino` & `servopulse.ino`

- [ ] Verify that serial commands ('1', '2', '3') correctly trigger the servo movements for each grade:
    - [ ] **G2-0:** Command '1' -> Servo moves to 45°.
    - [ ] **G2-1 to G2-3:** Command '2' -> Servo moves to 135°.
    - [ ] **G2-4:** Command '3' -> Servo moves to 90° (reset/default).
- [ ] Implement a feedback mechanism from the Arduino to the Python script (e.g., send an "ACK" message after a command is executed).
- [ ] Test the integration of the continuous stepper motor movement with the servo-based sorting gates.

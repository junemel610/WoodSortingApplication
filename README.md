# Automated Wood Sorting System

This document provides a comprehensive overview of the Automated Wood Sorting System, designed for developers and operators. The system automates the process of sorting wood pieces by analyzing surface defects, measuring length, and grading them into predefined categories.

## 1. Features

-   **Dual-Camera Vision System:** Captures images of both the top and bottom surfaces of wood pieces for comprehensive inspection.
-   **AI-Powered Defect Detection:** Utilizes two YOLO (You Only Look Once) models:
    1.  A primary model to detect the presence of a wood piece.
    2.  A secondary model to identify and classify defects (`Dead_Knot`, `Knot_missing`, `Live_Knot`).
-   **Automated Grading & Sorting:** Classifies wood into three grades based on defect count and actuates one of three servo-controlled gates to sort the piece.
-   **Conveyor Control System:** A Tkinter GUI provides controls for the conveyor motor with three modes:
    -   **Continuous Mode:** The conveyor runs continuously.
    -   **Trigger Mode:** The conveyor runs only when a wood piece is detected by the IR sensor.
    -   **Stop:** Halts the conveyor.
-   **Length Measurement:** An IR break beam sensor measures the time a wood piece obstructs its path, which is used to calculate the piece's length based on the conveyor speed.
-   **Graphical User Interface (GUI):** A user-friendly interface built with Tkinter that displays:
    -   Live feeds from both cameras.
    -   Captured images with annotated defects.
    -   System status, defect details, and length measurements.
    -   Controls for the conveyor and email reporting.
-   **Automated Inactivity Reporting:** If the system remains idle for 30 seconds, it automatically generates a summary report in both `.txt` and `.pdf` formats.
-   **Email Functionality:** Allows the user to send the last generated PDF report to a specified email address via SMTP, with a GUI button that is enabled only when an internet connection is available.

## 2. System Architecture

The system integrates a Python application for high-level control and vision processing with an Arduino for low-level hardware management. Communication between them is handled via a serial connection.

```mermaid
graph TD
    subgraph Computer
        A[Python GUI Application (gui_app.py)]
        B[YOLO Models (.pt)]
        C[Configuration (config.json)]
    end

    subgraph Conveyor System
        D[Arduino (master_controller.ino)]
        E[Stepper Motor]
        F[IR Break Beam Sensor]
        G[Servo Gates]
    end

    subgraph External
        H[USB Cameras]
        I[SMTP Email Server]
    end

    A -- Loads --> B
    A -- Reads --> C
    H -- Video Stream --> A
    A -- Serial Commands --> D
    D -- Serial Data --> A
    D -- Controls --> E
    F -- Trigger Signal --> D
    D -- Controls --> G
    A -- Sends Email --> I
```

### Components

-   **Python GUI Application (`gui_app.py`):** The system's brain. It manages the GUI, captures and processes video feeds, runs the YOLO models for detection, calculates grades, and sends commands to the Arduino.
-   **Arduino Controller (`master_controller.ino`):** The hardware controller. It operates the stepper motor, reads the IR sensor, and controls the servo gates based on commands received from the Python application.
-   **YOLO Models:** Pre-trained models for object and defect detection.
-   **Configuration (`config.json`):** A file to securely store email credentials, keeping them separate from the source code.

## 3. Hardware & Software Requirements

### Hardware
-   A computer capable of running Python and computer vision tasks.
-   2 x USB webcams.
-   Arduino board (e.g., Arduino Uno).
-   Stepper motor and a compatible driver.
-   3 x Servo motors.
-   IR break beam sensor module.
-   Power supplies and wiring for all components.

### Software
-   Python 3.7+
-   Arduino IDE
-   Python libraries as listed in `requirements.txt`:
    -   `opencv-python`
    -   `Pillow`
    -   `pyserial`
    -   `ultralytics`
    -   `reportlab`

## 4. Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd WoodSortingApplication
    ```

2.  **Set Up Python Environment:**
    It is highly recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install Dependencies:**
    Create a `requirements.txt` file with the content from the Software section above and run:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Email:**
    Create a `config.json` file in the root directory. This file will store the credentials for the email account that sends the reports. **This file is included in `.gitignore` and should not be committed to version control.**

    *`config.json` template:*
    ```json
    {
        "email_user": "your_email@example.com",
        "email_pass": "your_app_password"
    }
    ```

5.  **Set Up Arduino:**
    -   Connect the stepper motor, servo motors, and IR sensor to your Arduino board according to the pin definitions in the sketch.
    -   Open `Arduino_Files/master_controller.ino` in the Arduino IDE.
    -   Upload the sketch to your Arduino board.
    -   Ensure the Arduino is connected to your computer via USB.

## 5. Operational Workflow

1.  **Launch:** Run the main application from the `Python_Files` directory:
    ```bash
    python Python_Files/gui_app.py
    ```
2.  **Initialization:** The GUI starts, loads the YOLO models, initializes the camera feeds, and establishes a serial connection with the Arduino.
3.  **Operation:** The user selects a conveyor mode (`Continuous` or `Trigger`).
4.  **Detection:** In `Trigger` mode, when a wood piece passes the IR sensor, the Arduino sends a trigger signal (`B`) to the Python app.
5.  **Analysis:** The Python app captures images from both cameras and runs them through the YOLO models to identify and count defects.
6.  **Grading:** The system assigns a grade (1, 2, or 3) based on the total number of defects found.
7.  **Sorting:** The grade is sent as a command to the Arduino, which activates the corresponding servo gate to sort the wood piece.
8.  **Length Measurement:** The Arduino measures the duration the IR beam was broken, sends it to the Python app (`L:<duration_ms>`), and the app calculates and displays the length.
9.  **Reporting:** If no activity (GUI interaction or Arduino message) occurs for 30 seconds, a PDF and TXT report is automatically generated.
10. **Emailing:** The user can enter a recipient's email and click "Send Last Report". The button is only active if a report exists and an internet connection is detected.

## 6. Project File Structure

```
WoodSortingApplication/
├── Arduino_Files/
│   └── master_controller.ino   # Main sketch for all hardware control
├── Machine-Learning/
│   ├── best.pt                 # YOLO model for wood piece detection
│   └── last.pt                 # YOLO model for defect classification
├── Python_Files/
│   └── gui_app.py              # The main Tkinter GUI application
├── .gitignore                  # Specifies files to ignore for Git
├── config.json                 # (To be created by user) Stores email credentials
├── README.md                   # This documentation file
└── requirements.txt            # (To be created by user) Python dependencies
```

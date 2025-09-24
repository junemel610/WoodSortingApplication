import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import serial
import threading
import time
import queue
from ultralytics import YOLO
import json
import os
import socket
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wood Sorting Application")
        self.geometry("1400x900")  # Increased size to accommodate more information

        # Load email config FIRST, before creating UI elements that depend on it
        self.email_config = self.load_email_config()

        # Create message queue for thread communication
        self.message_queue = queue.Queue()

        # --- Model and Camera Initialization ---
        self.model = YOLO("Machine-Learning/best.pt", task="detect")
        self.defect_model = YOLO("Machine-Learning/last.pt", task="detect")
        self.cap_top = cv2.VideoCapture(0)
        self.cap_bottom = cv2.VideoCapture(2)

        # Live detection tracking
        self.live_detections = {"top": {}, "bottom": {}}
        self.live_grades = {"top": "No wood detected", "bottom": "No wood detected"}
        
        # Store captured analysis results
        self.captured_detections = {"top": {}, "bottom": {}}

        # Main layout
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        # --- Camera Sections ---
        self.top_live_feed, self.top_captured_image, self.top_details = self.create_section(main_frame, "Top Camera View", 0)
        self.bottom_live_feed, self.bottom_captured_image, self.bottom_details = self.create_section(main_frame, "Bottom Camera View", 1)

        # --- Status and Controls ---
        status_and_controls_frame = ttk.Frame(main_frame)
        status_and_controls_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        status_and_controls_frame.grid_columnconfigure(0, weight=1)
        status_and_controls_frame.grid_columnconfigure(1, weight=1)

        status_frame = ttk.LabelFrame(status_and_controls_frame, text="System Status", padding="10")
        status_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.pack_propagate(False)
        status_frame.config(height=60)
        self.status_label = ttk.Label(status_frame, text="Status: Initializing...", font=("Helvetica", 12), anchor="center")
        self.status_label.pack(expand=True, fill=tk.BOTH)

        control_frame = ttk.LabelFrame(status_and_controls_frame, text="Conveyor Control", padding="10")
        control_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        control_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_columnconfigure(1, weight=1)
        control_frame.grid_columnconfigure(2, weight=1)
        control_frame.grid_columnconfigure(3, weight=1) # Configure column for toggle

        ttk.Button(control_frame, text="Continuous Mode", command=lambda: self.send_arduino_command('C')).grid(row=0, column=0, sticky="ew", padx=2, ipady=5)
        ttk.Button(control_frame, text="Trigger Mode", command=lambda: self.send_arduino_command('T')).grid(row=0, column=1, sticky="ew", padx=2, ipady=5)
        ttk.Button(control_frame, text="Stop Conveyor", command=lambda: self.send_arduino_command('X')).grid(row=0, column=2, sticky="ew", padx=2, ipady=5)

        # Live detection toggle
        self.live_detection_var = tk.BooleanVar(value=False)
        live_detection_toggle = ttk.Checkbutton(control_frame, text="Live Detection", 
                                                variable=self.live_detection_var)
        live_detection_toggle.grid(row=0, column=3, sticky="ew", padx=5)

        # --- Conveyor Speed Setting ---
        speed_frame = ttk.LabelFrame(status_and_controls_frame, text="Conveyor Speed (cm/s)", padding="10")
        speed_frame.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        self.speed_var = tk.StringVar(value="10.0") # Default speed
        speed_entry = ttk.Entry(speed_frame, textvariable=self.speed_var, width=10)
        speed_entry.pack(pady=5)

        # --- Network & Email Frame ---
        email_frame = ttk.LabelFrame(status_and_controls_frame, text="Email Report", padding="10")
        email_frame.grid(row=0, column=3, sticky="nsew", padx=5, pady=5)
        email_frame.grid_columnconfigure(1, weight=1)

        self.internet_status_label = ttk.Label(email_frame, text="Status: Checking...", foreground="orange")
        self.internet_status_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        ttk.Label(email_frame, text="Recipient Email:").grid(row=1, column=0, sticky="w")
        # Now self.email_config is properly initialized
        recipient_default = self.email_config.get('recipient', '') if self.email_config else ''
        self.recipient_email_var = tk.StringVar(value=recipient_default)
        ttk.Entry(email_frame, textvariable=self.recipient_email_var, width=30).grid(row=1, column=1, sticky="ew", padx=5)

        self.last_report_label = ttk.Label(email_frame, text="Last Report: None")
        self.last_report_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=2)

        self.send_email_button = ttk.Button(email_frame, text="Send Last Report", command=self.send_report_email, state="disabled")
        self.send_email_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5,0))

        self.show_report_notification = tk.BooleanVar(value=True)
        self.notification_toggle = ttk.Checkbutton(email_frame, text="Show Report Notifications", 
                                                 variable=self.show_report_notification)
        self.notification_toggle.grid(row=4, column=0, columnspan=2, sticky="w", pady=(5,0))

        # --- Live Grading Display ---
        live_grading_frame = ttk.LabelFrame(main_frame, text="Live Grading Results", padding="10")
        live_grading_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        live_grading_frame.grid_columnconfigure(0, weight=1)
        live_grading_frame.grid_columnconfigure(1, weight=1)

        # Top camera live grade
        top_grade_frame = ttk.Frame(live_grading_frame)
        top_grade_frame.grid(row=0, column=0, sticky="ew", padx=5)
        ttk.Label(top_grade_frame, text="Top Camera Grade:", font=("Helvetica", 10, "bold")).pack(anchor="w")
        self.top_grade_label = ttk.Label(top_grade_frame, text="No wood detected", foreground="gray")
        self.top_grade_label.pack(anchor="w")
        
        # Bottom camera live grade
        bottom_grade_frame = ttk.Frame(live_grading_frame)
        bottom_grade_frame.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(bottom_grade_frame, text="Bottom Camera Grade:", font=("Helvetica", 10, "bold")).pack(anchor="w")
        self.bottom_grade_label = ttk.Label(bottom_grade_frame, text="No wood detected", foreground="gray")
        self.bottom_grade_label.pack(anchor="w")

        # Combined live grade
        combined_grade_frame = ttk.Frame(live_grading_frame)
        combined_grade_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(10,0))
        ttk.Label(combined_grade_frame, text="Combined Grade:", font=("Helvetica", 12, "bold")).pack(anchor="w")
        self.combined_grade_label = ttk.Label(combined_grade_frame, text="No wood detected", font=("Helvetica", 11), foreground="gray")
        self.combined_grade_label.pack(anchor="w")

        # --- Live Statistics ---
        stats_frame = ttk.LabelFrame(main_frame, text="Live Detection Statistics", padding="10")
        stats_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        stats_frame.grid_columnconfigure(0, weight=1)
        stats_frame.grid_columnconfigure(1, weight=1)
        stats_frame.grid_columnconfigure(2, weight=1)

        self.live_stats_labels = {}
        for i, (grade, text) in enumerate([("grade1", "Grade G2-0 (Good)"), ("grade2", "Grade G2-1/2/3 (Fair)"), ("grade3", "Grade G2-4 (Poor)")]):
            frame = ttk.Frame(stats_frame)
            frame.grid(row=0, column=i, sticky="ew", padx=5)
            ttk.Label(frame, text=text, font=("Helvetica", 9, "bold")).pack(anchor="w")
            self.live_stats_labels[grade] = ttk.Label(frame, text="Count: 0", foreground="blue")
            self.live_stats_labels[grade].pack(anchor="w")

        # Initialize live statistics
        self.live_stats = {"grade1": 0, "grade2": 0, "grade3": 0}

        # --- Arduino Communication ---
        self.setup_arduino()

        # Start the video feed update loop
        self.update_feeds()
        
        # Start processing messages from background threads
        self.process_message_queue()

        # --- Inactivity and Reporting --- 
        self.last_activity_time = time.time()
        self.total_pieces_processed = 0
        self.grade_counts = {1: 0, 2: 0, 3: 0}
        self.report_generated = False
        self.last_report_path = None
        self.is_online = False # Initialize is_online
        self.check_inactivity()
        self.check_internet_connection()

        # Set the action for when the window is closed
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_section(self, parent, title, col):
        section_frame = ttk.LabelFrame(parent, text=title, padding="10")
        section_frame.grid(row=0, column=col, sticky="nsew", padx=5, pady=5)
        section_frame.grid_rowconfigure(0, weight=1)
        section_frame.grid_columnconfigure(0, weight=1)

        live_feed_label = ttk.Label(section_frame, background="black")
        live_feed_label.pack(expand=True, fill=tk.BOTH, pady=5)

        captured_image_label = ttk.Label(section_frame, text="Captured Image", background="grey")
        captured_image_label.pack(expand=True, fill=tk.BOTH, pady=5)

        details_label = ttk.Label(section_frame, text="Defect Details:")
        details_label.pack(fill=tk.X)

        return live_feed_label, captured_image_label, details_label

    def update_feeds(self):
        self.update_single_feed(self.cap_top, self.top_live_feed, "top")
        self.update_single_feed(self.cap_bottom, self.bottom_live_feed, "bottom")
        self.after(15, self.update_feeds) # Update at ~66 FPS

    def update_single_feed(self, cap, label, camera_name):
        ret, frame = cap.read()
        if ret:
            # If live detection is on, analyze the frame for wood pieces and defects
            if hasattr(self, 'live_detection_var') and self.live_detection_var.get():
                annotated_frame, defect_dict = self.analyze_frame(frame, run_defect_model=True)
                
                # Store the detection results
                self.live_detections[camera_name] = defect_dict
                
                # Calculate grade for this camera
                grade_info = self.calculate_grade(defect_dict)
                self.live_grades[camera_name] = grade_info
                
                # Update the live grading display
                self.update_live_grading_display()
                
                cv2image = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            else:
                # Reset detections when live detection is off
                self.live_detections[camera_name] = {}
                self.live_grades[camera_name] = "No wood detected"
                self.update_live_grading_display()
                
                # Otherwise, just show the raw feed
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            img = Image.fromarray(cv2image)
            imgtk = ImageTk.PhotoImage(image=img)
            label.imgtk = imgtk
            label.configure(image=imgtk)

    def calculate_grade(self, defect_dict):
        """Calculate grade based on defect dictionary and return grade info"""
        total_defects = sum(defect_dict.values()) if defect_dict else 0
        
        if total_defects == 0:
            return {
                'grade': 1,
                'text': 'Grade G2-0 (Good)',
                'total_defects': 0,
                'color': 'green'
            }
        elif total_defects <= 2:
            return {
                'grade': 1,
                'text': f'Grade G2-0 (Good) - {total_defects} defects',
                'total_defects': total_defects,
                'color': 'green'
            }
        elif total_defects <= 6:
            return {
                'grade': 2,
                'text': f'Grade G2-1/2/3 (Fair) - {total_defects} defects',
                'total_defects': total_defects,
                'color': 'orange'
            }
        else:
            return {
                'grade': 3,
                'text': f'Grade G2-4 (Poor) - {total_defects} defects',
                'total_defects': total_defects,
                'color': 'red'
            }

    def update_live_grading_display(self):
        """Update the live grading display with current detection results"""
        # Update individual camera grades
        top_grade = self.live_grades["top"]
        bottom_grade = self.live_grades["bottom"]
        
        if isinstance(top_grade, dict):
            self.top_grade_label.config(text=top_grade['text'], foreground=top_grade['color'])
        else:
            self.top_grade_label.config(text=top_grade, foreground="gray")
        
        if isinstance(bottom_grade, dict):
            self.bottom_grade_label.config(text=bottom_grade['text'], foreground=bottom_grade['color'])
        else:
            self.bottom_grade_label.config(text=bottom_grade, foreground="gray")
        
        # Calculate combined grade
        combined_defects = {}
        wood_detected = False
        
        for camera_name in ["top", "bottom"]:
            if self.live_detections[camera_name]:
                wood_detected = True
                for defect, count in self.live_detections[camera_name].items():
                    combined_defects[defect] = combined_defects.get(defect, 0) + count
        
        if wood_detected:
            combined_grade = self.calculate_grade(combined_defects)
            self.combined_grade_label.config(text=combined_grade['text'], foreground=combined_grade['color'])
        else:
            self.combined_grade_label.config(text="No wood detected", foreground="gray")

    def setup_arduino(self):
        try:
            self.ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
            time.sleep(2)
            self.arduino_thread = threading.Thread(target=self.listen_for_arduino, daemon=True)
            self.arduino_thread.start()
            self.status_label.config(text="Status: Arduino connected. Waiting for trigger...")
        except serial.SerialException:
            self.ser = None
            self.status_label.config(text="Status: Arduino not found. Running in manual mode.")

    def process_message_queue(self):
        """Process messages from background threads safely in the main thread"""
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()
                
                if msg_type == "arduino_message":
                    message = data
                    if message == "B":
                        self.trigger_capture_and_analysis()
                    elif message.startswith("L:"):
                        try:
                            duration_ms = int(message.split(':')[1])
                            self.calculate_and_display_length(duration_ms)
                        except (ValueError, IndexError):
                            print(f"Could not parse length message: {message}")
                    else:
                        self.status_label.config(text=f"Status: {message}")
                        
                elif msg_type == "status_update":
                    self.status_label.config(text=f"Status: {data}")
                    
        except queue.Empty:
            pass
        
        # Schedule next check
        self.after(50, self.process_message_queue)

    def listen_for_arduino(self):
        while True:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    message = self.ser.readline().decode('utf-8').strip()
                    if not message:
                        continue

                    self.reset_inactivity_timer()
                    print(f"Arduino Message: {message}")

                    # Put message in queue for main thread to process
                    self.message_queue.put(("arduino_message", message))
                    
                time.sleep(0.1)
            except (serial.SerialException, OSError) as e:
                print(f"Arduino communication error: {e}")
                self.message_queue.put(("status_update", "Arduino connection lost"))
                break

    def send_arduino_command(self, command):
        self.reset_inactivity_timer()
        try:
            if self.ser:
                self.ser.write(command.encode('utf-8'))
                print(f"Sent command to Arduino: '{command}'")
            else:
                print("Cannot send command: Arduino not connected.")
                self.status_label.config(text="Status: Arduino not connected.")
        except (serial.SerialException, OSError) as e:
            print(f"Error sending Arduino command: {e}")
            self.status_label.config(text="Status: Arduino communication error")

    def trigger_capture_and_analysis(self):
        self.status_label.config(text="Status: IR beam triggered! Capturing and analyzing...")

        # Process top camera with full defect detection
        top_ret, top_frame = self.cap_top.read()
        top_defects = {}
        if top_ret:
            top_defects = self.run_detection(top_frame, self.top_captured_image, self.top_details, "Top")
        
        # Process bottom camera with full defect detection  
        bottom_ret, bottom_frame = self.cap_bottom.read()
        bottom_defects = {}
        if bottom_ret:
            bottom_defects = self.run_detection(bottom_frame, self.bottom_captured_image, self.bottom_details, "Bottom")

        # Store captured results
        self.captured_detections["top"] = top_defects
        self.captured_detections["bottom"] = bottom_defects

        # Combine results and grade
        combined_defects = top_defects.copy()
        for defect, count in bottom_defects.items():
            combined_defects[defect] = combined_defects.get(defect, 0) + count
        
        # Update captured grading display
        self.update_captured_grading_display(combined_defects)
        
        self.grading_and_arduino(combined_defects)

        self.status_label.config(text="Status: Analysis complete. Waiting for trigger...")

    def run_detection(self, frame, captured_image_label, details_label, camera_name):
        """Run detection and update the captured image display, return defect dictionary"""
        annotated_frame, defect_dict = self.analyze_frame(frame, run_defect_model=True)
        
        # Update captured image display
        img = Image.fromarray(cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB))
        imgtk = ImageTk.PhotoImage(image=img)
        captured_image_label.imgtk = imgtk
        captured_image_label.configure(image=imgtk)
        
        # Update details display
        details_list = [f"- {name.replace('_', ' ').title()}: {count}" for name, count in defect_dict.items()]
        if not details_list:
            details_text = f"{camera_name} Defects:\nNo defects detected."
        else:
            details_text = f"{camera_name} Defects:\n" + "\n".join(details_list)
        details_label.config(text=details_text)
        
        # Store defect dict in the label for later access
        details_label.defect_dict = defect_dict
        
        return defect_dict

    def update_captured_grading_display(self, combined_defects):
        """Update grading display after capture analysis"""
        if combined_defects:
            # Calculate combined grade from captured results
            combined_grade = self.calculate_grade(combined_defects)
            
            # Update individual camera displays based on captured results
            top_grade = self.calculate_grade(self.captured_detections.get("top", {}))
            bottom_grade = self.calculate_grade(self.captured_detections.get("bottom", {}))
            
            # Update labels temporarily to show captured results
            original_live_state = self.live_detection_var.get()
            
            # Show captured results
            self.top_grade_label.config(text=f"CAPTURED: {top_grade['text']}", foreground=top_grade['color'])
            self.bottom_grade_label.config(text=f"CAPTURED: {bottom_grade['text']}", foreground=bottom_grade['color'])
            self.combined_grade_label.config(text=f"CAPTURED: {combined_grade['text']}", foreground=combined_grade['color'])
            
            # Restore live detection display after 5 seconds if live detection is on
            if original_live_state:
                self.after(5000, self.update_live_grading_display)

    def analyze_frame(self, frame, run_defect_model=True):
        initial_confidence = 0.40
        defect_confidence = 0.20
        results = self.model(frame, imgsz=640, conf=initial_confidence)
        annotated_frame = frame.copy()
        final_defect_dict = {}

        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            
            # Always draw a bounding box for the detected wood piece
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 0, 0), 2) # Blue for wood
            
            # If not in full analysis mode, skip defect detection
            if not run_defect_model:
                continue

            # --- Defect Detection on Cropped Region ---
            cropped_frame = frame[y1:y2, x1:x2]
            if cropped_frame.size == 0:
                continue

            defect_results = self.defect_model(cropped_frame, imgsz=640, conf=defect_confidence)
            
            for defect_box in defect_results[0].boxes:
                class_id = int(defect_box.cls[0])
                class_name = self.defect_model.names[class_id]
                
                if class_name in final_defect_dict:
                    final_defect_dict[class_name] += 1
                else:
                    final_defect_dict[class_name] = 1

                # Draw bounding box for the defect relative to the original frame
                dx1, dy1, dx2, dy2 = map(int, defect_box.xyxy[0].tolist())
                abs_x1, abs_y1 = x1 + dx1, y1 + dy1
                abs_x2, abs_y2 = x1 + dx2, y1 + dy2
                cv2.rectangle(annotated_frame, (abs_x1, abs_y1), (abs_x2, abs_y2), (0, 255, 0), 2) # Green for defects
                cv2.putText(annotated_frame, class_name, (abs_x1, abs_y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        return annotated_frame, final_defect_dict

    def grading_and_arduino(self, defect_dict):
        if not self.ser:
            print("Cannot send grade to Arduino: not connected")
            return

        # Calculate total defects from all detected defect types
        total_defects = sum(defect_dict.values()) if defect_dict else 0
        grade_text = f"Total Defects: {total_defects} -> "
        command_sent = 0
        
        if total_defects <= 2:
            command_sent = 1
            grade_text += "Grade G2-0. Sent '1' to Arduino."
        elif total_defects <= 6:
            command_sent = 2
            grade_text += "Grade G2-1/2-2/2-3. Sent '2' to Arduino."
        else:
            command_sent = 3
            grade_text += "Grade G2-4. Sent '3' to Arduino."

        if command_sent > 0:
            try:
                self.ser.write(str(command_sent).encode('utf-8'))
                self.total_pieces_processed += 1
                self.grade_counts[command_sent] += 1
                
                # Update live statistics display
                self.live_stats[f"grade{command_sent}"] += 1
                self.update_live_stats_display()
                
                print(grade_text)
                self.status_label.config(text=f"Status: {grade_text}")
            except (serial.SerialException, OSError) as e:
                print(f"Error sending grade to Arduino: {e}")
                self.status_label.config(text="Status: Arduino communication error")

    def update_live_stats_display(self):
        """Update the live statistics display"""
        for grade_key, count in self.live_stats.items():
            self.live_stats_labels[grade_key].config(text=f"Count: {count}")

    def calculate_and_display_length(self, duration_ms):
        try:
            speed_cm_s = float(self.speed_var.get())
            length_cm = (duration_ms / 1000.0) * speed_cm_s
            length_text = f"\nEstimated Length: {length_cm:.2f} cm"
            print(length_text)

            for details_label in [self.top_details, self.bottom_details]:
                if hasattr(details_label, 'defect_dict'):
                    defect_items = [f"- {name.replace('_', ' ').title()}: {count}" 
                                  for name, count in details_label.defect_dict.items()]
                    if not defect_items:
                        current_text = "Defects:\nNo defects detected."
                    else:
                        current_text = "Defects:\n" + "\n".join(defect_items)
                    details_label.config(text=current_text + length_text)

        except ValueError:
            self.status_label.config(text="Status: Invalid speed value!")

    def on_closing(self):
        print("Releasing resources...")
        self.cap_top.release()
        self.cap_bottom.release()
        if self.ser:
            self.ser.close()
        self.destroy()

    def reset_inactivity_timer(self):
        self.last_activity_time = time.time()
        self.report_generated = False

    def check_inactivity(self):
        if not self.report_generated and (time.time() - self.last_activity_time > 30):
            self.generate_report()
            self.report_generated = True
        self.after(1000, self.check_inactivity)

    def generate_report(self):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base_filename = f"report_{timestamp}"
        txt_filename = f"{base_filename}.txt"
        pdf_filename = f"{base_filename}.pdf"
        
        content = f"--- Inactivity Report ---\n"
        content += f"Generated at: {timestamp}\n"
        content += f"Total Pieces Processed: {self.total_pieces_processed}\n"
        content += f"Grade G2-0 (Gate 1): {self.grade_counts[1]}\n"
        content += f"Grade G2-1/2/3 (Gate 2): {self.grade_counts[2]}\n"
        content += f"Grade G2-4 (Gate 3): {self.grade_counts[3]}\n"

        try:
            with open(txt_filename, 'w') as f:
                f.write(content)
            print(f"Inactivity report generated: {txt_filename}")
        except Exception as e:
            print(f"Error generating TXT report: {e}")
            messagebox.showerror("Report Error", f"Could not save TXT report: {e}")
            return

        try:
            c = canvas.Canvas(pdf_filename, pagesize=letter)
            width, height = letter
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(width / 2.0, height - 1*inch, "Wood Sorting System - Inactivity Report")
            c.setFont("Helvetica", 12)
            text = c.beginText(1*inch, height - 2*inch)
            text.textLine(f"Generated at: {timestamp}")
            text.textLine("")
            text.textLine(f"Total Pieces Processed: {self.total_pieces_processed}")
            text.textLine(f"Grade G2-0 (Gate 1): {self.grade_counts[1]}")
            text.textLine(f"Grade G2-1/2/3 (Gate 2): {self.grade_counts[2]}")
            text.textLine(f"Grade G2-4 (Gate 3): {self.grade_counts[3]}")
            c.drawText(text)
            c.save()
            print(f"PDF report generated: {pdf_filename}")
            
            self.last_report_path = pdf_filename
            self.last_report_label.config(text=f"Last Report: {os.path.basename(self.last_report_path)}")
            self.update_send_email_button_state()
            
            # Show notification only if toggle is enabled
            if self.show_report_notification.get():
                messagebox.showinfo("Inactivity Report", f"Reports saved as {txt_filename} and {pdf_filename}")

        except Exception as e:
            print(f"Error generating PDF report: {e}")
            messagebox.showerror("Report Error", f"Could not save PDF report: {e}")

    def load_email_config(self):
        try:
            with open('config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print("config.json not found. Email functionality will be limited.")
            return {}
        except json.JSONDecodeError:
            print("Error decoding config.json. Email functionality will be limited.")
            return {}

    def check_internet_connection(self):
        def check():
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=5)
                self.after(0, self.update_online_status, True)
            except OSError:
                self.after(0, self.update_online_status, False)
        threading.Thread(target=check, daemon=True).start()
        self.after(15000, self.check_internet_connection)

    def update_online_status(self, is_online):
        self.is_online = is_online
        if self.is_online:
            self.internet_status_label.config(text="Status: Online", foreground="green")
        else:
            self.internet_status_label.config(text="Status: Offline", foreground="red")
        self.update_send_email_button_state()

    def update_send_email_button_state(self):
        if self.is_online and self.last_report_path:
            self.send_email_button.config(state="normal")
        else:
            self.send_email_button.config(state="disabled")

    def send_report_email(self):
        if not self.last_report_path or not os.path.exists(self.last_report_path):
            messagebox.showwarning("No Report", "Please generate a report first.")
            return

        recipient = self.recipient_email_var.get()
        if "@" not in recipient or "." not in recipient:
            messagebox.showwarning("Input Error", "Please enter a valid recipient email address.")
            return

        def send_in_thread():
            try:
                self.after(0, lambda: self.status_label.config(text="Status: Preparing to send email..."))
                with open('config.json') as f:
                    config = json.load(f).get('email', {})
                
                if not all(k in config for k in ['sender', 'password', 'smtp_server', 'smtp_port']):
                    self.after(0, lambda: messagebox.showerror("Config Error", "Email config is incomplete in config.json."))
                    self.after(0, lambda: self.status_label.config(text="Status: Email config error."))
                    return

                msg = MIMEMultipart()
                msg['From'] = config['sender']
                msg['To'] = recipient
                msg['Subject'] = f"Wood Sorting System Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                msg.attach(MIMEText("Please find the attached report.", 'plain'))

                with open(self.last_report_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f"attachment; filename={os.path.basename(self.last_report_path)}")
                    msg.attach(part)

                self.after(0, lambda: self.status_label.config(text="Status: Sending email..."))
                server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
                server.starttls()
                server.login(config['sender'], config['password'])
                server.sendmail(config['sender'], recipient, msg.as_string())
                server.quit()

                self.after(0, lambda: messagebox.showinfo("Email Sent", f"Report successfully sent to {recipient}"))
                self.after(0, lambda: self.status_label.config(text="Status: Email sent successfully."))

            except FileNotFoundError:
                self.after(0, lambda: messagebox.showerror("Config Error", "'config.json' not found."))
                self.after(0, lambda: self.status_label.config(text="Status: config.json not found."))
            except smtplib.SMTPAuthenticationError:
                self.after(0, lambda: messagebox.showerror("Email Error", "Authentication failed. Check credentials."))
                self.after(0, lambda: self.status_label.config(text="Status: Email auth failed."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Email Error", f"Failed to send email: {e}"))
                self.after(0, lambda: self.status_label.config(text=f"Status: Email failed: {e}"))

        threading.Thread(target=send_in_thread, daemon=True).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import serial
import threading
import time
import queue
import degirum as dg
import degirum_tools
import json
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wood Sorting Application")
        
        # Get screen dimensions for dynamic sizing
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Calculate window size (90% of screen size for windowed mode)
        window_width = int(screen_width * 0.9)
        window_height = int(screen_height * 0.9)
        
        # Center the window on screen
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Set geometry with calculated dimensions
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Make window resizable
        self.resizable(True, True)
        
        # Set minimum size to prevent too small windows
        self.minsize(800, 600)
        
        # For Raspberry Pi - detect if running in fullscreen environment
        self.is_fullscreen = False
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)
        
        # Auto-fullscreen for Raspberry Pi (you can enable this)
        # Uncomment the next line if you want automatic fullscreen on startup
        # self.after(100, self.auto_fullscreen_rpi)
        
        # Calculate responsive font sizes based on screen size
        base_font_size = max(8, min(12, int(screen_height / 80)))  # Reduced base size for better fit
        self.font_small = ("Helvetica", base_font_size - 1)
        self.font_normal = ("Helvetica", base_font_size)
        self.font_large = ("Helvetica", base_font_size + 2, "bold")
        self.font_button = ("Helvetica", base_font_size, "bold")  # Button font

        # Create message queue for thread communication
        self.message_queue = queue.Queue()

        # Initialize variables that might be accessed early by message processing
        self.total_pieces_processed = 0
        self.grade_counts = {1: 0, 2: 0, 3: 0}
        self.report_generated = False
        self.last_report_path = None
        self.last_activity_time = time.time()
        self.live_stats = {"grade1": 0, "grade2": 0, "grade3": 0}
        self._shutting_down = False  # Flag to indicate shutdown in progress

        # --- DeGirum Model and Camera Initialization ---
        # DeGirum Configuration
        self.inference_host_address = "@local"
        self.zoo_url = "/home/inspectura/Desktop/meljune_exponent--640x640_quant_hailort_hailo8_1"
        self.model_name = "meljune_exponent--640x640_quant_hailort_hailo8_1"
        
        # Load DeGirum model
        try:
            self.model = dg.load_model(
                model_name=self.model_name,
                inference_host_address=self.inference_host_address,
                zoo_url=self.zoo_url
            )
            print("DeGirum model loaded successfully.")
        except Exception as e:
            print(f"Error loading DeGirum model: {e}")
            messagebox.showerror("Model Error", f"Failed to load DeGirum model: {e}")
            self.model = None
        
        # Initialize cameras with specific resolution
        self.cap_top = cv2.VideoCapture(0)
        self.cap_bottom = cv2.VideoCapture(2)
        
        # Set camera resolution (you can adjust these values)
        camera_width = 1280  # Desired width
        camera_height = 720  # Desired height
        
        # Configure top camera
        self.cap_top.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
        self.cap_top.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
        self.cap_top.set(cv2.CAP_PROP_FPS, 30)  # Set FPS
        
        # Configure bottom camera
        self.cap_bottom.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
        self.cap_bottom.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
        self.cap_bottom.set(cv2.CAP_PROP_FPS, 30)  # Set FPS
        
        # Store camera resolution for display scaling
        self.camera_width = camera_width
        self.camera_height = camera_height
        
        # Verify camera settings
        actual_top_width = self.cap_top.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_top_height = self.cap_top.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_bottom_width = self.cap_bottom.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_bottom_height = self.cap_bottom.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        print(f"Top camera resolution: {actual_top_width}x{actual_top_height}")
        print(f"Bottom camera resolution: {actual_bottom_width}x{actual_bottom_height}")

        # Live detection tracking
        self.live_detections = {"top": {}, "bottom": {}}
        self.live_grades = {"top": "No wood detected", "bottom": "No wood detected"}

        # Main layout
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)
        main_frame.grid_columnconfigure(0, weight=1)  # Equal weight for both columns
        main_frame.grid_columnconfigure(1, weight=1)  # Equal weight for both columns
        main_frame.grid_rowconfigure(0, weight=4)  # Camera sections get even more space
        main_frame.grid_rowconfigure(1, weight=0)  # Controls stay compact
        main_frame.grid_rowconfigure(2, weight=0)  # Live grading compact
        main_frame.grid_rowconfigure(3, weight=0)  # Statistics compact

        # --- Camera Sections ---
        self.top_live_feed, _, self.top_details = self.create_section(main_frame, "Top Camera View", 0)
        self.bottom_live_feed, _, self.bottom_details = self.create_section(main_frame, "Bottom Camera View", 1)

        # --- Status and Controls ---
        status_and_controls_frame = ttk.Frame(main_frame)
        status_and_controls_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        status_and_controls_frame.grid_columnconfigure(0, weight=2)  # Status gets more space
        status_and_controls_frame.grid_columnconfigure(1, weight=2)  # Controls get more space
        status_and_controls_frame.grid_columnconfigure(2, weight=1)  # Speed compact
        status_and_controls_frame.grid_columnconfigure(3, weight=2)  # Email section

        status_frame = ttk.LabelFrame(status_and_controls_frame, text="System Status", padding="10")
        status_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_rowconfigure(0, weight=1)
        # Use larger font for better readability
        self.status_label = ttk.Label(status_frame, text="Status: Initializing...", 
                                     font=self.font_normal, anchor="center", 
                                     wraplength=250, justify="center")
        self.status_label.pack(expand=True, fill=tk.BOTH)

        control_frame = ttk.LabelFrame(status_and_controls_frame, text="Conveyor Control", padding="10")
        control_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        control_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_columnconfigure(1, weight=1)
        control_frame.grid_columnconfigure(2, weight=1)
        control_frame.grid_columnconfigure(3, weight=1) # Configure column for toggle

        ttk.Button(control_frame, text="Continuous\nMode", 
                  command=lambda: self.send_arduino_command('C')).grid(
                  row=0, column=0, sticky="ew", padx=2, ipady=8)
        ttk.Button(control_frame, text="Trigger\nMode", 
                  command=lambda: self.send_arduino_command('T')).grid(
                  row=0, column=1, sticky="ew", padx=2, ipady=8)
        ttk.Button(control_frame, text="Stop\nConveyor", 
                  command=lambda: self.send_arduino_command('X')).grid(
                  row=0, column=2, sticky="ew", padx=2, ipady=8)

        # Live detection toggle with better text styling
        self.live_detection_var = tk.BooleanVar(value=False)
        live_detection_toggle = ttk.Checkbutton(control_frame, text="Live\nDetection", 
                                                variable=self.live_detection_var)
        live_detection_toggle.grid(row=0, column=3, sticky="ew", padx=5)

        # Second row for grading controls
        ttk.Button(control_frame, text="Send Grade\nNow", 
                  command=self.manual_grade_trigger).grid(
                  row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(5,0), ipady=8)
        
        # Auto-grade toggle
        self.auto_grade_var = tk.BooleanVar(value=False)
        auto_grade_toggle = ttk.Checkbutton(control_frame, text="Auto Grade\nLive Detection", 
                                           variable=self.auto_grade_var)
        auto_grade_toggle.grid(row=1, column=2, columnspan=2, sticky="ew", padx=5, pady=(5,0))

        # --- Conveyor Speed Setting ---
        speed_frame = ttk.LabelFrame(status_and_controls_frame, text="Speed\n(cm/s)", padding="10")
        speed_frame.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        speed_frame.grid_columnconfigure(0, weight=1)
        speed_frame.grid_rowconfigure(0, weight=1)
        
        self.speed_var = tk.StringVar(value="10.0") # Default speed
        speed_entry = ttk.Entry(speed_frame, textvariable=self.speed_var, 
                               width=8, font=self.font_normal, justify="center")
        speed_entry.pack(expand=True, pady=5)

        # --- Network & Log Frame ---
        log_frame = ttk.LabelFrame(status_and_controls_frame, text="Activity Log", padding="10")
        log_frame.grid(row=0, column=3, sticky="nsew", padx=5, pady=5)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

        self.log_status_label = ttk.Label(log_frame, text="Log: Ready", 
                                         foreground="green", font=self.font_small)
        self.log_status_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        self.last_report_label = ttk.Label(log_frame, text="Last Report: None", 
                                          font=self.font_small, wraplength=200)
        self.last_report_label.grid(row=1, column=0, sticky="ew", pady=2)

        ttk.Button(log_frame, text="Generate Report", 
                  command=self.manual_generate_report).grid(row=2, column=0, sticky="ew", pady=(5,0))

        self.show_report_notification = tk.BooleanVar(value=True)
        self.notification_toggle = ttk.Checkbutton(log_frame, text="Show Notifications", 
                                                 variable=self.show_report_notification)
        self.notification_toggle.grid(row=3, column=0, sticky="w", pady=(5,0))

        # --- Live Grading Display ---
        live_grading_frame = ttk.LabelFrame(main_frame, text="Live Grading Results", padding="10")
        live_grading_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        live_grading_frame.grid_columnconfigure(0, weight=1)
        live_grading_frame.grid_columnconfigure(1, weight=1)

        # Top camera live grade
        top_grade_frame = ttk.Frame(live_grading_frame)
        top_grade_frame.grid(row=0, column=0, sticky="ew", padx=5)
        ttk.Label(top_grade_frame, text="Top Camera Grade:", font=self.font_normal).pack(anchor="w")
        self.top_grade_label = ttk.Label(top_grade_frame, text="No wood detected", foreground="gray", font=self.font_small)
        self.top_grade_label.pack(anchor="w")
        
        # Bottom camera live grade
        bottom_grade_frame = ttk.Frame(live_grading_frame)
        bottom_grade_frame.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(bottom_grade_frame, text="Bottom Camera Grade:", font=self.font_normal).pack(anchor="w")
        self.bottom_grade_label = ttk.Label(bottom_grade_frame, text="No wood detected", foreground="gray", font=self.font_small)
        self.bottom_grade_label.pack(anchor="w")

        # Combined live grade
        combined_grade_frame = ttk.Frame(live_grading_frame)
        combined_grade_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(10,0))
        ttk.Label(combined_grade_frame, text="Combined Grade:", font=self.font_large).pack(anchor="w")
        self.combined_grade_label = ttk.Label(combined_grade_frame, text="No wood detected", font=self.font_normal, foreground="gray")
        self.combined_grade_label.pack(anchor="w")

        # --- Live Statistics ---
        stats_frame = ttk.LabelFrame(main_frame, text="Live Detection Statistics", padding="10")
        stats_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        stats_frame.grid_columnconfigure(0, weight=1)
        stats_frame.grid_columnconfigure(1, weight=1)
        stats_frame.grid_columnconfigure(2, weight=1)

        # Initialize live stats labels dictionary
        self.live_stats_labels = {}
        for i, (grade, text) in enumerate([("grade1", "Grade G2-0 (Good)"), ("grade2", "Grade G2-1/2/3 (Fair)"), ("grade3", "Grade G2-4 (Poor)")]):
            frame = ttk.Frame(stats_frame)
            frame.grid(row=0, column=i, sticky="ew", padx=5)
            ttk.Label(frame, text=text, font=self.font_small).pack(anchor="w")
            self.live_stats_labels[grade] = ttk.Label(frame, text="Count: 0", foreground="blue", font=self.font_small)
            self.live_stats_labels[grade].pack(anchor="w")

        # Initialize live statistics display
        self.update_live_stats_display()

        # --- Arduino Communication ---
        self.setup_arduino()

        # Start the video feed update loop
        self.update_feeds()
        
        # Start processing messages from background threads
        self.process_message_queue()

        # --- Inactivity and Reporting --- 
        self.check_inactivity()

        # Set the action for when the window is closed
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_section(self, parent, title, col):
        section_frame = ttk.LabelFrame(parent, text=title, padding="10")
        section_frame.grid(row=0, column=col, sticky="nsew", padx=5, pady=5)
        section_frame.grid_rowconfigure(0, weight=4)  # Live feed gets most space
        section_frame.grid_rowconfigure(1, weight=0)  # Details stay compact but visible
        section_frame.grid_columnconfigure(0, weight=1)

        # Live feed area - now takes up most of the space
        live_feed_label = ttk.Label(section_frame, background="black", text="Live Feed")
        live_feed_label.grid(row=0, column=0, sticky="nsew", pady=(0, 5))

        # Details area with proper wrapping and formatting
        details_label = ttk.Label(section_frame, text="Live Detection Details:\n─────────────────────────\nWaiting for live detection...", 
                                 anchor="nw", justify="left", wraplength=350, 
                                 font=self.font_small, relief="sunken", padding="5")
        details_label.grid(row=1, column=0, sticky="ew", pady=(5, 0), ipady=10)

        return live_feed_label, None, details_label

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
                
                # Update the detection details display for this camera
                self.update_detection_details(camera_name, defect_dict)
                
                # Update the live grading display
                self.update_live_grading_display()
                
                cv2image = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            else:
                # Reset detections when live detection is off
                self.live_detections[camera_name] = {}
                self.live_grades[camera_name] = "No wood detected"
                self.update_detection_details(camera_name, {})
                self.update_live_grading_display()
                
                # Otherwise, just show the raw feed
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image and ensure consistent scaling
            img = Image.fromarray(cv2image)
            
            # Get label size for scaling
            label.update_idletasks()  # Make sure label size is updated
            label_width = label.winfo_width()
            label_height = label.winfo_height()
            
            # Only resize if label has valid dimensions
            if label_width > 1 and label_height > 1:
                # Force consistent display size for both cameras (720p aspect ratio)
                target_aspect_ratio = 16 / 9  # 1280x720 = 16:9
                
                # Use minimal margin
                margin = 3
                available_width = label_width - (2 * margin)
                available_height = label_height - (2 * margin)
                
                # Calculate standardized size based on available space and 16:9 ratio
                if available_width / available_height > target_aspect_ratio:
                    # Available space is wider than 16:9, constrain by height
                    display_height = available_height
                    display_width = int(display_height * target_aspect_ratio)
                else:
                    # Available space is taller than 16:9, constrain by width
                    display_width = available_width
                    display_height = int(display_width / target_aspect_ratio)
                
                # Ensure dimensions don't exceed available space
                display_width = min(display_width, available_width)
                display_height = min(display_height, available_height)
                
                # Resize the camera image to exactly these dimensions (stretch if needed)
                img = img.resize((display_width, display_height), Image.Resampling.LANCZOS)
                
                # Create a black background of the full label size
                final_img = Image.new('RGB', (label_width, label_height), 'black')
                
                # Center the standardized image
                x_offset = (label_width - display_width) // 2
                y_offset = (label_height - display_height) // 2
                
                # Paste the resized image
                final_img.paste(img, (x_offset, y_offset))
                img = final_img
            
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
            
            # Auto-grade functionality - send grade automatically if enabled
            if hasattr(self, 'auto_grade_var') and self.auto_grade_var.get():
                # Add a small delay and check if wood is still detected to avoid rapid firing
                if not hasattr(self, '_last_auto_grade_time'):
                    self._last_auto_grade_time = 0
                
                current_time = time.time()
                if current_time - self._last_auto_grade_time > 2.0:  # Only send grade every 2 seconds
                    print(f"Auto-grade triggered - Combined defects: {combined_defects}")
                    self.grading_and_arduino(combined_defects)
                    self._last_auto_grade_time = current_time
        else:
            self.combined_grade_label.config(text="No wood detected", foreground="gray")

    def update_detection_details(self, camera_name, defect_dict):
        """Update the detection details display for a specific camera"""
        # Determine which details label to update
        if camera_name == "top":
            details_label = self.top_details
        elif camera_name == "bottom":
            details_label = self.bottom_details
        else:
            return
        
        # Format the detection details
        if defect_dict:
            # Create a formatted string showing each defect type and count
            details_text = "Live Detection Details:\n"
            total_defects = sum(defect_dict.values())
            details_text += f"Total Defects: {total_defects}\n"
            details_text += "─" * 25 + "\n"
            
            # Sort defects by count (highest first) for better visibility
            sorted_defects = sorted(defect_dict.items(), key=lambda x: x[1], reverse=True)
            
            for defect_type, count in sorted_defects:
                # Format defect name (replace underscores, capitalize)
                formatted_name = defect_type.replace('_', ' ').title()
                details_text += f"• {formatted_name}: {count}\n"
            
            # Add confidence or additional info if needed
            details_text += "─" * 25 + "\n"
            details_text += f"Status: {len(defect_dict)} defect type(s) detected"
            
            # Set color based on defect severity
            if total_defects <= 2:
                text_color = "dark green"
            elif total_defects <= 6:
                text_color = "dark orange"
            else:
                text_color = "dark red"
                
        else:
            details_text = "Live Detection Details:\n"
            details_text += "─" * 25 + "\n"
            details_text += "No wood or defects detected\n"
            details_text += "─" * 25 + "\n"
            details_text += "Status: Waiting for detection..."
            text_color = "gray"
        
        # Update the label with the formatted text and color
        details_label.config(text=details_text, foreground=text_color)

    def setup_arduino(self):
        # Don't attempt to setup Arduino if shutting down
        if hasattr(self, '_shutting_down') and self._shutting_down:
            return
            
        try:
            # Close existing connection if any
            if hasattr(self, 'ser') and self.ser:
                try:
                    self.ser.close()
                except:
                    pass
            
            # Try multiple common serial ports for Arduino
            ports_to_try = ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyAMA0', '/dev/ttyAMA1', '/dev/ttyAMA10', 'COM3', 'COM4', 'COM5']
            
            for port in ports_to_try:
                try:
                    print(f"Trying to connect to Arduino on {port}...")
                    self.ser = serial.Serial(port, 9600, timeout=1)
                    time.sleep(2)  # Give Arduino time to reset
                    
                    # Test the connection
                    self.ser.write(b'X')  # Send stop command as test
                    self.ser.flush()
                    
                    print(f"Arduino connected successfully on {port}")
                    break
                except (serial.SerialException, OSError):
                    continue
            else:
                # No port worked
                raise serial.SerialException("No Arduino found on any port")
            
            # Start Arduino listener thread if not already running and not shutting down
            if not (hasattr(self, '_shutting_down') and self._shutting_down):
                if not hasattr(self, 'arduino_thread') or not self.arduino_thread.is_alive():
                    self.arduino_thread = threading.Thread(target=self.listen_for_arduino, daemon=True)
                    self.arduino_thread.start()
            
            if hasattr(self, 'status_label'):
                self.status_label.config(text="Status: Arduino connected. Ready for operation.")
            
        except serial.SerialException as e:
            self.ser = None
            print(f"Arduino connection failed: {e}")
            if hasattr(self, 'status_label'):
                self.status_label.config(text="Status: Arduino not found. Running in manual mode.")

    def process_message_queue(self):
        """Process messages from background threads safely in the main thread"""
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()
                
                if msg_type == "arduino_message":
                    message = data
                    if message.startswith("L:"):
                        try:
                            duration_ms = int(message.split(':')[1])
                            self.calculate_and_display_length(duration_ms)
                        except (ValueError, IndexError):
                            print(f"Could not parse length message: {message}")
                    elif message == "B":
                        # IR beam broken - trigger inference and grading
                        try:
                            self.trigger_inference_and_grading()
                        except Exception as e:
                            print(f"Error in trigger_inference_and_grading: {e}")
                    else:
                        self.status_label.config(text=f"Status: {message}")
                        
                elif msg_type == "status_update":
                    self.status_label.config(text=f"Status: {data}")
                    
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in process_message_queue: {e}")
        
        # Schedule next check
        self.after(50, self.process_message_queue)

    def listen_for_arduino(self):
        while True:
            try:
                # Check if serial connection exists and is open before accessing properties
                if self.ser and hasattr(self.ser, 'is_open') and self.ser.is_open and self.ser.in_waiting > 0:
                    message = self.ser.readline().decode('utf-8').strip()
                    if not message:
                        continue

                    self.reset_inactivity_timer()
                    print(f"Arduino Message: {message}")

                    # Put message in queue for main thread to process
                    self.message_queue.put(("arduino_message", message))
                elif not self.ser or (hasattr(self.ser, 'is_open') and not self.ser.is_open):
                    # Serial connection is closed or doesn't exist, exit thread
                    print("Arduino listener thread: Serial connection closed, exiting thread")
                    break
                    
                time.sleep(0.1)
            except (serial.SerialException, OSError, TypeError) as e:
                print(f"Arduino communication error: {e}")
                # Check if this is due to application shutdown
                if not hasattr(self, 'ser') or not self.ser:
                    print("Arduino listener thread: Application shutting down, exiting thread")
                    break
                self.message_queue.put(("status_update", "Arduino connection lost"))
                break
            except Exception as e:
                print(f"Unexpected error in Arduino listener: {e}")
                break

    def send_arduino_command(self, command):
        # Don't send commands if shutting down
        if hasattr(self, '_shutting_down') and self._shutting_down:
            return
            
        self.reset_inactivity_timer()
        try:
            if self.ser:
                # Check if serial connection is still valid
                if not hasattr(self.ser, 'is_open') or not self.ser.is_open:
                    print("Serial connection is closed, attempting to reconnect...")
                    self.setup_arduino()
                    if not self.ser:
                        return
                
                self.ser.write(command.encode('utf-8'))
                self.ser.flush()  # Ensure data is sent immediately
                print(f"Sent command to Arduino: '{command}'")
            else:
                print("Cannot send command: Arduino not connected.")
                if hasattr(self, 'status_label'):
                    self.status_label.config(text="Status: Arduino not connected.")
        except (serial.SerialException, OSError, TypeError) as e:
            print(f"Error sending Arduino command: {e}")
            if hasattr(self, 'status_label'):
                self.status_label.config(text="Status: Arduino communication error - attempting reconnect...")
            # Try to reconnect only if not shutting down
            if not (hasattr(self, '_shutting_down') and self._shutting_down):
                self.ser = None
                self.setup_arduino()

    def trigger_inference_and_grading(self):
        """Triggered when Arduino IR sensor detects wood piece - run inference and send grade"""
        print("IR sensor triggered - running inference for grading...")
        
        # Capture current frames from both cameras
        combined_defects = {}
        cameras_with_wood = 0
        
        # Analyze top camera
        ret_top, frame_top = self.cap_top.read()
        if ret_top:
            annotated_frame_top, defects_top = self.analyze_frame(frame_top, run_defect_model=True)
            if defects_top:  # If wood detected
                cameras_with_wood += 1
                for defect, count in defects_top.items():
                    combined_defects[defect] = combined_defects.get(defect, 0) + count
                # Update detection details for top camera
                self.update_detection_details("top", defects_top)
            else:
                # Clear top camera details if no detection
                self.update_detection_details("top", {})
        
        # Analyze bottom camera  
        ret_bottom, frame_bottom = self.cap_bottom.read()
        if ret_bottom:
            annotated_frame_bottom, defects_bottom = self.analyze_frame(frame_bottom, run_defect_model=True)
            if defects_bottom:  # If wood detected
                cameras_with_wood += 1
                for defect, count in defects_bottom.items():
                    combined_defects[defect] = combined_defects.get(defect, 0) + count
                # Update detection details for bottom camera
                self.update_detection_details("bottom", defects_bottom)
            else:
                # Clear bottom camera details if no detection
                self.update_detection_details("bottom", {})
        
        # Only send grading command if wood was detected in at least one camera
        if cameras_with_wood > 0:
            print(f"Wood detected in {cameras_with_wood} camera(s). Combined defects: {combined_defects}")
            self.grading_and_arduino(combined_defects)
        else:
            print("No wood detected in either camera - no grading command sent")
            self.status_label.config(text="Status: IR triggered but no wood detected")

    def manual_grade_trigger(self):
        """Manually trigger grading based on current live detection results"""
        if not hasattr(self, 'live_detection_var') or not self.live_detection_var.get():
            print("Live detection is not enabled - enabling it first...")
            self.live_detection_var.set(True)
            self.status_label.config(text="Status: Enabled live detection and triggering grade...")
            # Wait a moment for detection to update
            self.after(100, self._execute_manual_grade)
        else:
            self._execute_manual_grade()

    def _execute_manual_grade(self):
        """Execute the manual grading based on current detections"""
        # Use current live detection results
        combined_defects = {}
        cameras_with_wood = 0
        
        for camera_name in ["top", "bottom"]:
            if self.live_detections[camera_name]:
                cameras_with_wood += 1
                for defect, count in self.live_detections[camera_name].items():
                    combined_defects[defect] = combined_defects.get(defect, 0) + count
        
        if cameras_with_wood > 0:
            print(f"Manual grade trigger - Wood detected in {cameras_with_wood} camera(s). Combined defects: {combined_defects}")
            self.grading_and_arduino(combined_defects)
        else:
            print("Manual grade trigger - No wood currently detected")
            self.status_label.config(text="Status: Manual grade - no wood detected")

    def analyze_frame(self, frame, run_defect_model=True):
        """Analyze frame using DeGirum model for defect detection"""
        if self.model is None:
            return frame, {}
        
        try:
            # Run inference using DeGirum
            inference_result = self.model(frame)
            
            # Get annotated frame
            annotated_frame = inference_result.image_overlay
            
            # Process detections to count defects
            final_defect_dict = {}
            detections = inference_result.results
            
            for det in detections:
                label = det['label']
                
                # Count defects by label
                if label in final_defect_dict:
                    final_defect_dict[label] += 1
                else:
                    final_defect_dict[label] = 1
            
            return annotated_frame, final_defect_dict
            
        except Exception as e:
            print(f"Error during DeGirum inference: {e}")
            return frame, {}

    def grading_and_arduino(self, defect_dict):
        # Don't send grading commands if shutting down
        if hasattr(self, '_shutting_down') and self._shutting_down:
            return
            
        if not self.ser:
            print("Cannot send grade to Arduino: not connected")
            if hasattr(self, 'status_label'):
                self.status_label.config(text="Status: Arduino not connected")
            return

        # Ensure required attributes exist (safety check)
        if not hasattr(self, 'total_pieces_processed'):
            self.total_pieces_processed = 0
        if not hasattr(self, 'grade_counts'):
            self.grade_counts = {1: 0, 2: 0, 3: 0}
        if not hasattr(self, 'live_stats'):
            self.live_stats = {"grade1": 0, "grade2": 0, "grade3": 0}

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
                # Check if serial connection is still valid
                if not hasattr(self.ser, 'is_open') or not self.ser.is_open:
                    print("Serial connection is closed, attempting to reconnect...")
                    self.setup_arduino()
                    if not self.ser:
                        return
                
                self.ser.write(str(command_sent).encode('utf-8'))
                self.ser.flush()  # Ensure data is sent immediately
                self.total_pieces_processed += 1
                self.grade_counts[command_sent] += 1
                
                # Update live statistics display
                self.live_stats[f"grade{command_sent}"] += 1
                self.update_live_stats_display()
                
                print(grade_text)
                if hasattr(self, 'status_label'):
                    self.status_label.config(text=f"Status: {grade_text}")
            except (serial.SerialException, OSError, TypeError) as e:
                print(f"Error sending grade to Arduino: {e}")
                if hasattr(self, 'status_label'):
                    self.status_label.config(text="Status: Arduino communication error - attempting reconnect...")
                # Try to reconnect only if not shutting down
                if not (hasattr(self, '_shutting_down') and self._shutting_down):
                    self.ser = None
                    self.setup_arduino()

    def update_live_stats_display(self):
        """Update the live statistics display"""
        # Safety check to ensure all required attributes exist
        if not hasattr(self, 'live_stats'):
            self.live_stats = {"grade1": 0, "grade2": 0, "grade3": 0}
        if not hasattr(self, 'live_stats_labels'):
            return  # Skip update if labels aren't initialized yet
            
        for grade_key, count in self.live_stats.items():
            if grade_key in self.live_stats_labels:
                self.live_stats_labels[grade_key].config(text=f"Count: {count}")

    def calculate_and_display_length(self, duration_ms):
        try:
            speed_cm_s = float(self.speed_var.get())
            length_cm = (duration_ms / 1000.0) * speed_cm_s
            length_text = f"\nEstimated Length: {length_cm:.2f} cm"
            print(f"Wood piece length calculated: {length_cm:.2f} cm")

            # Update both camera detail displays with length information
            for camera_name, details_label in [("top", self.top_details), ("bottom", self.bottom_details)]:
                current_text = details_label.cget("text")
                
                # If there's already detection info, append length
                if "Live Detection Details:" in current_text:
                    # Remove any existing length info first
                    lines = current_text.split('\n')
                    filtered_lines = [line for line in lines if not line.startswith("Estimated Length:")]
                    updated_text = '\n'.join(filtered_lines) + length_text
                    details_label.config(text=updated_text)
                else:
                    # If no detection info, just show length
                    basic_text = "Live Detection Details:\n"
                    basic_text += "─" * 25 + "\n"
                    basic_text += "No defects detected" + length_text
                    details_label.config(text=basic_text)

        except ValueError:
            self.status_label.config(text="Status: Invalid speed value!")

    def on_closing(self):
        print("Releasing resources...")
        
        # Set a flag to indicate shutdown is in progress
        self._shutting_down = True
        
        # Close Arduino connection first to stop the listener thread
        if hasattr(self, 'ser') and self.ser:
            try:
                print("Closing Arduino connection...")
                self.ser.close()
                self.ser = None
            except Exception as e:
                print(f"Error closing Arduino connection: {e}")
        
        # Wait a moment for the Arduino thread to exit gracefully
        if hasattr(self, 'arduino_thread') and self.arduino_thread.is_alive():
            print("Waiting for Arduino thread to close...")
            self.arduino_thread.join(timeout=2.0)  # Wait up to 2 seconds
        
        # Release camera resources
        try:
            print("Releasing camera resources...")
            if hasattr(self, 'cap_top'):
                self.cap_top.release()
            if hasattr(self, 'cap_bottom'):
                self.cap_bottom.release()
        except Exception as e:
            print(f"Error releasing cameras: {e}")
        
        # Close the application
        try:
            self.destroy()
        except Exception as e:
            print(f"Error during application shutdown: {e}")

    def reset_inactivity_timer(self):
        self.last_activity_time = time.time()
        if hasattr(self, 'report_generated'):
            self.report_generated = False

    def check_inactivity(self):
        # Generate report after 30 seconds of inactivity (auto-log feature)
        if not self.report_generated and (time.time() - self.last_activity_time > 30):
            self.generate_report()
            self.report_generated = True
        self.after(1000, self.check_inactivity)

    def generate_report(self):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base_filename = f"report_{timestamp}"
        txt_filename = f"{base_filename}.txt"
        pdf_filename = f"{base_filename}.pdf"
        log_filename = "wood_sorting_log.txt"
        
        content = f"--- Activity Report ---\n"
        content += f"Generated at: {timestamp}\n"
        content += f"Total Pieces Processed: {self.total_pieces_processed}\n"
        content += f"Grade G2-0 (Gate 1): {self.grade_counts[1]}\n"
        content += f"Grade G2-1/2/3 (Gate 2): {self.grade_counts[2]}\n"
        content += f"Grade G2-4 (Gate 3): {self.grade_counts[3]}\n"

        # Save individual report files
        try:
            with open(txt_filename, 'w') as f:
                f.write(content)
            print(f"Activity report generated: {txt_filename}")
        except Exception as e:
            print(f"Error generating TXT report: {e}")
            messagebox.showerror("Report Error", f"Could not save TXT report: {e}")
            return

        # Append to log file
        try:
            log_entry = f"{timestamp} | Pieces: {self.total_pieces_processed} | G1: {self.grade_counts[1]} | G2: {self.grade_counts[2]} | G3: {self.grade_counts[3]}\n"
            with open(log_filename, 'a') as f:
                f.write(log_entry)
            print(f"Entry added to log file: {log_filename}")
            self.log_status_label.config(text="Log: Updated", foreground="blue")
        except Exception as e:
            print(f"Error updating log file: {e}")
            self.log_status_label.config(text="Log: Error", foreground="red")

        try:
            c = canvas.Canvas(pdf_filename, pagesize=letter)
            width, height = letter
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(width / 2.0, height - 1*inch, "Wood Sorting System - Activity Report")
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
            
            # Show notification only if toggle is enabled
            if self.show_report_notification.get():
                messagebox.showinfo("Activity Report", f"Reports saved as {txt_filename} and {pdf_filename}\nLog updated: {log_filename}")

        except Exception as e:
            print(f"Error generating PDF report: {e}")
            messagebox.showerror("Report Error", f"Could not save PDF report: {e}")

    def manual_generate_report(self):
        """Manually generate a report"""
        self.generate_report()
        self.log_status_label.config(text="Log: Manual report generated", foreground="green")

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode (F11 key)"""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        return "break"

    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode (Escape key)"""
        self.is_fullscreen = False
        self.attributes("-fullscreen", False)
        return "break"

    def auto_fullscreen_rpi(self):
        """Automatically enable fullscreen for Raspberry Pi deployment"""
        try:
            # Check if running on Raspberry Pi
            with open('/proc/cpuinfo', 'r') as f:
                if 'Raspberry Pi' in f.read():
                    print("Raspberry Pi detected - enabling fullscreen mode")
                    self.is_fullscreen = True
                    self.attributes("-fullscreen", True)
        except FileNotFoundError:
            # Not running on Raspberry Pi, continue normally
            pass
        except Exception as e:
            print(f"Error checking system: {e}")

if __name__ == "__main__":
    app = App()
    app.mainloop()

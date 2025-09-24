import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import threading
import time
import queue
import degirum as dg
import degirum_tools
import os

# --- DeGirum Configuration ---
inference_host_address = "@local"
zoo_url = "/home/inspectura/Desktop/testing/ControlledDefect--640x640_quant_hailort_hailo8_1"
model_name = "ControlledDefect--640x640_quant_hailort_hailo8_1"

class CameraHandler:
    def __init__(self):
        self.top_camera = None
        self.bottom_camera = None
        self.top_camera_index = 0  # Cam0
        self.bottom_camera_index = 2  # Cam2
        
        # Camera settings based on your Cam0 and Cam2 settings
        self.top_camera_settings = {
            'brightness': 0,
            'contrast': 32,
            'saturation': 64,
            'hue': 0,
            'exposure': -6,  # Auto exposure off, manual value
            'white_balance': 4520,
            'gain': 0
        }
        
        self.bottom_camera_settings = {
            'brightness': 135,
            'contrast': 75,
            'saturation': 155,
            'hue': 0,
            'exposure': -6,  # Auto exposure off, manual value
            'white_balance': 5400,
            'gain': 0
        }

    def initialize_cameras(self):
        """Initialize both cameras with specific settings"""
        try:
            # Initialize top camera (Cam0)
            self.top_camera = cv2.VideoCapture(self.top_camera_index)
            if not self.top_camera.isOpened():
                raise RuntimeError(f"Could not open top camera (Cam0 - index {self.top_camera_index})")
            
            # Initialize bottom camera (Cam2)
            self.bottom_camera = cv2.VideoCapture(self.bottom_camera_index)
            if not self.bottom_camera.isOpened():
                self.top_camera.release()
                raise RuntimeError(f"Could not open bottom camera (Cam2 - index {self.bottom_camera_index})")
            
            # Set resolution to 720p for both cameras
            self.top_camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.top_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.bottom_camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.bottom_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
            # Apply camera settings
            self._apply_camera_settings(self.top_camera, self.top_camera_settings)
            self._apply_camera_settings(self.bottom_camera, self.bottom_camera_settings)
            
            print("Cameras initialized successfully at 720p (1280x720)")
            
        except Exception as e:
            self.release_cameras()
            raise RuntimeError(f"Failed to initialize cameras: {str(e)}")

    def _apply_camera_settings(self, camera, settings):
        """Apply settings to a camera"""
        try:
            camera.set(cv2.CAP_PROP_BRIGHTNESS, settings['brightness'])
            camera.set(cv2.CAP_PROP_CONTRAST, settings['contrast'])
            camera.set(cv2.CAP_PROP_SATURATION, settings['saturation'])
            camera.set(cv2.CAP_PROP_HUE, settings['hue'])
            camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual exposure
            camera.set(cv2.CAP_PROP_EXPOSURE, settings['exposure'])
            camera.set(cv2.CAP_PROP_AUTO_WB, 0)  # Manual white balance
            camera.set(cv2.CAP_PROP_WB_TEMPERATURE, settings['white_balance'])
            camera.set(cv2.CAP_PROP_GAIN, settings['gain'])
        except Exception as e:
            print(f"Warning: Some camera settings may not be supported: {e}")

    def release_cameras(self):
        """Release camera resources"""
        if self.top_camera:
            self.top_camera.release()
            self.top_camera = None
        if self.bottom_camera:
            self.bottom_camera.release()
            self.bottom_camera = None
        print("Cameras released")

    def capture_images(self):
        """Capture images from both cameras"""
        if not self.top_camera or not self.bottom_camera:
            raise RuntimeError("Cameras not initialized")
        
        ret_top, frame_top = self.top_camera.read()
        ret_bottom, frame_bottom = self.bottom_camera.read()
        
        if not ret_top:
            raise RuntimeError("Failed to read from top camera (Cam0)")
        if not ret_bottom:
            raise RuntimeError("Failed to read from bottom camera (Cam2)")
        
        frame_bottom = cv2.flip(frame_bottom, 1)
        return frame_top, frame_bottom


class VideoStreamApp:
    def __init__(self, master):
        self.master = master
        master.title("Live Inference on Dual Cameras")

        # Create GUI elements
        self.camera1_label = ttk.Label(master)
        self.camera1_label.grid(row=0, column=0, padx=5, pady=5)
        self.camera1_fps_label = ttk.Label(master, text="Camera 1 FPS: 0.00")
        self.camera1_fps_label.grid(row=1, column=0, padx=5, pady=5)

        self.camera2_label = ttk.Label(master)
        self.camera2_label.grid(row=0, column=1, padx=5, pady=5)
        self.camera2_fps_label = ttk.Label(master, text="Camera 2 FPS: 0.00")
        self.camera2_fps_label.grid(row=1, column=1, padx=5, pady=5)

        # Create queues and stop event
        self.camera1_queue = queue.Queue(maxsize=1)
        self.camera2_queue = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()

        # Initialize CameraHandler
        self.camera_handler = CameraHandler()
        self.camera_handler.initialize_cameras()

        # Create and start threads for each camera
        self.thread1 = threading.Thread(target=self.run_inference_stream, args=(self.camera_handler.top_camera, self.camera1_queue))
        self.thread2 = threading.Thread(target=self.run_inference_stream, args=(self.camera_handler.bottom_camera, self.camera2_queue))
        self.thread1.start()
        self.thread2.start()

        # Start the GUI update loop
        self.master.after(10, self.update_gui)

        # Handle window close event
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    def run_inference_stream(self, camera, frame_queue):
        """Function to run inference on a single camera and put frames into a queue."""
        print(f"Starting inference on camera...")
        start_time = time.time()
        frame_count = 0

        while not self.stop_event.is_set():
            # Get frames from camera
            frame = camera.read()[1]
            if frame is None:
                print("Failed to read from camera")
                break

            # FPS Calculation
            frame_count += 1
            if time.time() - start_time >= 1.0:
                fps = frame_count / (time.time() - start_time)
                start_time = time.time()
                frame_count = 0
            else:
                fps = None

            # Put the frame and FPS in the queue
            if not frame_queue.full():
                frame_queue.put((frame, fps))

    def update_gui(self):
        """Periodically update the GUI with new frames from the queues."""
        display_size = (320, 320)  # <-- Adjust this size to your preference
        
        if not self.camera1_queue.empty():
            frame1, fps1 = self.camera1_queue.get()
            # Resize frame for display
            resized_frame1 = cv2.resize(frame1, display_size, interpolation=cv2.INTER_AREA)
            img1 = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(resized_frame1, cv2.COLOR_BGR2RGB)))
            self.camera1_label.imgtk = img1
            self.camera1_label.config(image=img1)
            if fps1 is not None:
                self.camera1_fps_label.config(text=f"Camera 1 FPS: {fps1:.2f}")

        if not self.camera2_queue.empty():
            frame2, fps2 = self.camera2_queue.get()
            # Resize frame for display
            resized_frame2 = cv2.resize(frame2, display_size, interpolation=cv2.INTER_AREA)
            img2 = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(resized_frame2, cv2.COLOR_BGR2RGB)))
            self.camera2_label.imgtk = img2
            self.camera2_label.config(image=img2)
            if fps2 is not None:
                self.camera2_fps_label.config(text=f"Camera 2 FPS: {fps2:.2f}")

        if not self.stop_event.is_set():
            self.master.after(10, self.update_gui)
        else:
            self.on_close_cleanup()

    def on_close(self):
        """Handle the window close event."""
        print("Closing the application.")
        self.stop_event.set()
        self.camera_handler.release_cameras()  # Release cameras
        self.master.destroy()

    def on_close_cleanup(self):
        """Cleanup after the main loop and threads have stopped."""
        self.thread1.join()
        self.thread2.join()
        print("Threads have been joined. Program exiting.")
        os._exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoStreamApp(root)
    root.mainloop()

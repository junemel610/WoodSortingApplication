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
zoo_url = "/home/inspectura/Desktop/WoodSortingApplication/models/V2DefectCombined--640x640_quant_hailort_hailo8_1"
model_name = "V2DefectCombined--640x640_quant_hailort_hailo8_1"

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

        # Define camera sources
        self.camera1_index = 0
        self.camera2_index = 2

        # Set a confidence threshold for detections
        self.confidence_threshold = 0.5  # Adjust this value as needed

        # Create and start threads for each camera
        self.thread1 = threading.Thread(target=self.run_inference_stream, args=(self.camera1_index, self.camera1_queue))
        self.thread2 = threading.Thread(target=self.run_inference_stream, args=(self.camera2_index, self.camera2_queue))
        self.thread1.start()
        self.thread2.start()

        # Start the GUI update loop
        self.master.after(10, self.update_gui)

        # Handle window close event
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    def run_inference_stream(self, camera_index, frame_queue):
        """Function to run inference on a single camera and put frames into a queue."""
        print(f"Loading model for camera {camera_index}...")
        try:
            model = dg.load_model(
                model_name=model_name,
                inference_host_address=inference_host_address,
                zoo_url=zoo_url
            )
            print(f"Model loaded successfully for camera {camera_index}.")

            print(f"Starting inference on video source: {camera_index}...")
            start_time = time.time()
            frame_count = 0

            for inference_result in degirum_tools.predict_stream(model, camera_index):
                if self.stop_event.is_set():
                    break

                # FPS Calculation
                frame_count += 1
                if time.time() - start_time >= 1.0:
                    fps = frame_count / (time.time() - start_time)
                    start_time = time.time()
                    frame_count = 0
                else:
                    fps = None

                # Access detections
                detections = inference_result.results
                for det in detections:
                    confidence = det.get('confidence', 0)  # Get confidence score
                    if confidence >= self.confidence_threshold:  # Check against threshold
                        label = det['label']
                        if label == "unsound_knot":
                            print(f"Camera {camera_index}: Unsound knot detected with confidence {confidence:.2f}")

                # Get annotated frame
                frame = inference_result.image_overlay

                # Put the frame and FPS in the queue
                if not frame_queue.full():
                    frame_queue.put((frame, fps))
        
        except Exception as e:
            print(f"An error occurred on camera {camera_index}: {e}")
        finally:
            print(f"Stopping inference for camera {camera_index}.")

    def update_gui(self):
        """Periodically update the GUI with new frames from the queues."""
        display_size = (720, 480)  # <-- Adjust this size to your preference
        
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

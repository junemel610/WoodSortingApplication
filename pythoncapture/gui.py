import sys
import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import os
from file_handler import FileHandler

class WoodCaptureGUI:
    def __init__(self, camera_handler, file_handler):
        self.root = tk.Tk()
        self.camera_handler = camera_handler
        self.file_handler = file_handler
        self.output_dir = None
        self.preview_active = False
        self.closing = False
        # Fixed preview size for consistent lighting representation
        self.preview_width = 720
        self.preview_height = 480
        self.init_ui()

    def init_ui(self):
        self.root.title('Dual-Camera Wood Panel Capture')
        self.root.geometry('1400x950')
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Directory selection
        dir_frame = ttk.LabelFrame(main_frame, text="Output Directory", padding="5")
        dir_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        dir_frame.columnconfigure(0, weight=1)
        
        self.dir_label = ttk.Label(dir_frame, text='Output Directory: Not selected')
        self.dir_label.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.select_dir_btn = ttk.Button(dir_frame, text='Select Directory', command=self.select_directory)
        self.select_dir_btn.grid(row=0, column=1)

        # Camera previews - Fixed size containers
        preview_frame = ttk.LabelFrame(main_frame, text="Camera Previews", padding="5")
        preview_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.columnconfigure(1, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        
        # Top camera preview
        top_frame = ttk.Frame(preview_frame)
        top_frame.grid(row=0, column=0, padx=(0, 5), sticky=(tk.N, tk.S))
        top_frame.grid_propagate(False)  # Prevent frame from shrinking
        
        ttk.Label(top_frame, text="Top Camera (Cam0)", font=('Arial', 12, 'bold')).pack(pady=(0, 5))
        
        # Fixed size preview with exact dimensions
        self.top_preview = tk.Label(
            top_frame, 
            width=self.preview_width, 
            height=self.preview_height,
            bg='gray', 
            text='Top Camera Preview\nCam0\nClick "Start Capture" to begin'
        )
        self.top_preview.pack()
        
        # Top camera individual capture button
        self.capture_top_btn = ttk.Button(
            top_frame, 
            text='Capture Top Only', 
            command=self.capture_top_only, 
            state='disabled'
        )
        self.capture_top_btn.pack(pady=(5, 0))
        
        # Bottom camera preview - identical size
        bottom_frame = ttk.Frame(preview_frame)
        bottom_frame.grid(row=0, column=1, padx=(5, 0), sticky=(tk.N, tk.S))
        bottom_frame.grid_propagate(False)  # Prevent frame from shrinking
        
        ttk.Label(bottom_frame, text="Bottom Camera (Cam2)", font=('Arial', 12, 'bold')).pack(pady=(0, 5))
        
        # Fixed size preview with exact same dimensions as top
        self.bottom_preview = tk.Label(
            bottom_frame, 
            width=self.preview_width, 
            height=self.preview_height,
            bg='gray', 
            text='Bottom Camera Preview\nCam2\nClick "Start Capture" to begin'
        )
        self.bottom_preview.pack()
        
        # Bottom camera individual capture button
        self.capture_bottom_btn = ttk.Button(
            bottom_frame, 
            text='Capture Bottom Only', 
            command=self.capture_bottom_only, 
            state='disabled'
        )
        self.capture_bottom_btn.pack(pady=(5, 0))

        # Control buttons
        btn_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        btn_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Main control buttons
        main_controls = ttk.Frame(btn_frame)
        main_controls.pack(fill=tk.X, pady=(0, 10))
        
        self.start_btn = ttk.Button(main_controls, text='Start Capture', command=self.start_capture)
        self.start_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_btn = ttk.Button(main_controls, text='Stop', command=self.stop_capture, state='disabled')
        self.stop_btn.grid(row=0, column=1, padx=10)
        
        self.reset_btn = ttk.Button(main_controls, text='Reset Session', command=self.reset_session)
        self.reset_btn.grid(row=0, column=2, padx=(10, 0))
        
        # Capture options
        capture_controls = ttk.LabelFrame(btn_frame, text="Capture Options", padding="5")
        capture_controls.pack(fill=tk.X)
        
        self.capture_both_btn = ttk.Button(
            capture_controls, 
            text='Capture Both Cameras', 
            command=self.capture_images, 
            state='disabled'
        )
        self.capture_both_btn.grid(row=0, column=0, padx=(0, 10))
        
        ttk.Label(capture_controls, text="OR", font=('Arial', 10)).grid(row=0, column=1, padx=10)
        
        ttk.Label(capture_controls, text="Use individual buttons below each camera preview").grid(row=0, column=2, padx=(10, 0), sticky=tk.W)

        # Resolution info
        info_frame = ttk.LabelFrame(main_frame, text="Camera Information", padding="5")
        info_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.resolution_var = tk.StringVar()
        self.resolution_var.set(f'Capture Resolution: 1280x720 (720p) | Preview: {self.preview_width}x{self.preview_height}')
        ttk.Label(info_frame, textvariable=self.resolution_var).pack()

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set('Ready - Please select an output directory')
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(1, weight=1)
        
        ttk.Label(status_frame, text="Status:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.grid(row=0, column=1, sticky=(tk.W, tk.E))

    def select_directory(self):
        dir_path = filedialog.askdirectory(title='Select Output Directory')
        if dir_path:
            self.output_dir = dir_path
            self.dir_label.config(text=f'Output Directory: {dir_path}')
            self.file_handler.set_output_directory(dir_path)
            self.status_var.set('Output directory selected - Ready to start capture')

    def start_capture(self):
        if not self.output_dir:
            self.status_var.set('Please select an output directory first.')
            messagebox.showwarning("Warning", "Please select an output directory first.")
            return
        
        try:
            self.camera_handler.initialize_cameras()
            self.preview_active = True
            self.start_preview_thread()
            
            self.start_btn.config(state='disabled')
            self.capture_both_btn.config(state='normal')
            self.capture_top_btn.config(state='normal')
            self.capture_bottom_btn.config(state='normal')
            self.stop_btn.config(state='normal')
            self.status_var.set('Cameras initialized. Choose capture option.')
        except RuntimeError as e:
            self.status_var.set(str(e))
            messagebox.showerror("Error", str(e))

    def start_preview_thread(self):
        def preview_loop():
            while self.preview_active and not self.closing:
                try:
                    frame_top, frame_bottom = self.camera_handler.capture_images()
                    if frame_top is not None and not self.closing:
                        self.root.after(0, lambda f=frame_top: self.display_frame(self.top_preview, f))
                    if frame_bottom is not None and not self.closing:
                        self.root.after(0, lambda f=frame_bottom: self.display_frame(self.bottom_preview, f))
                except Exception as e:
                    if not self.closing:
                        print(f"Preview error: {e}")
                    break
                threading.Event().wait(0.03)  # 30ms delay
        
        thread = threading.Thread(target=preview_loop, daemon=True)
        thread.start()

    def display_frame(self, label, frame):
        if self.closing:
            return
            
        try:
            # Always resize to exact same dimensions for both cameras
            # This ensures identical lighting representation
            resized_frame = cv2.resize(frame, (self.preview_width, self.preview_height))
            
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image and then to ImageTk
            pil_image = Image.fromarray(rgb_image)
            photo = ImageTk.PhotoImage(image=pil_image)
            
            # Update label
            label.config(image=photo, text='')
            label.image = photo  # Keep a reference to prevent garbage collection
        except Exception as e:
            if not self.closing:
                print(f"Error displaying frame: {e}")

    def capture_images(self):
        """Capture from both cameras"""
        try:
            frame_top, frame_bottom = self.camera_handler.capture_images()
            top_path, bottom_path = self.file_handler.get_both_save_paths()
            cv2.imwrite(top_path, frame_top)
            cv2.imwrite(bottom_path, frame_bottom)
            top_filename = os.path.basename(top_path)
            bottom_filename = os.path.basename(bottom_path)
            self.status_var.set(f'Both cameras saved: {top_filename}, {bottom_filename}')
        except RuntimeError as e:
            self.status_var.set(str(e))
            messagebox.showerror("Error", str(e))

    def capture_top_only(self):
        """Capture from top camera only"""
        try:
            frame_top, _ = self.camera_handler.capture_images()
            top_path = self.file_handler.get_top_save_path()
            cv2.imwrite(top_path, frame_top)
            top_filename = os.path.basename(top_path)
            self.status_var.set(f'Top camera only saved: {top_filename}')
        except RuntimeError as e:
            self.status_var.set(str(e))
            messagebox.showerror("Error", str(e))

    def capture_bottom_only(self):
        """Capture from bottom camera only"""
        try:
            _, frame_bottom = self.camera_handler.capture_images()
            bottom_path = self.file_handler.get_bottom_save_path()
            cv2.imwrite(bottom_path, frame_bottom)
            bottom_filename = os.path.basename(bottom_path)
            self.status_var.set(f'Bottom camera only saved: {bottom_filename}')
        except RuntimeError as e:
            self.status_var.set(str(e))
            messagebox.showerror("Error", str(e))

    def stop_capture(self):
        self.preview_active = False
        self.camera_handler.release_cameras()
        
        # Clear preview images
        self.top_preview.config(image='', text='Top Camera Preview\nCam0\nClick "Start Capture" to begin')
        self.bottom_preview.config(image='', text='Bottom Camera Preview\nCam2\nClick "Start Capture" to begin')
        
        self.start_btn.config(state='normal')
        self.capture_both_btn.config(state='disabled')
        self.capture_top_btn.config(state='disabled')
        self.capture_bottom_btn.config(state='disabled')
        self.stop_btn.config(state='disabled')
        self.status_var.set('Capture stopped.')

    def reset_session(self):
        self.file_handler.counter = 0
        self.status_var.set('Session reset - Counter set to 0')

    def on_closing(self):
        self.closing = True
        self.preview_active = False
        if hasattr(self.camera_handler, 'release_cameras'):
            self.camera_handler.release_cameras()
        self.root.quit()

    def run(self):
        self.root.mainloop()

    def close(self):
        if not self.closing:
            self.on_closing()
import sys
from camera import CameraHandler
from file_handler import FileHandler
from gui import WoodCaptureGUI

def main():
    camera_handler = CameraHandler()
    file_handler = FileHandler()  # No directory initially
    
    app = WoodCaptureGUI(camera_handler, file_handler)
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("Application interrupted")
    except Exception as e:
        print(f"Application error: {e}")
    finally:
        # Only call close if the app wasn't already closed
        try:
            app.close()
        except:
            pass  # App was already closed

if __name__ == '__main__':
    main()
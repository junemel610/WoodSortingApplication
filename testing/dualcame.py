import cv2
import numpy as np

def add_label(frame, text, position=(10, 40), color=(0, 255, 255)):
    """Overlay text label on the frame."""
    cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, 
                1, color, 2, cv2.LINE_AA)

def main():
    # Open the two USB cameras
    cap1 = cv2.VideoCapture(0)  # Camera 0
    cap2 = cv2.VideoCapture(2)  # Camera 2

    # Force 720p resolution for both cameras
    for cap in (cap1, cap2):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    screen_w, screen_h = 1920, 1080
    half_w = screen_w // 2  # 960

    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        if not ret1 or not ret2:
            print("Error: One of the cameras failed.")
            break

        # Resize each feed to fit left/right half of screen (960x1080)
        frame1_resized = cv2.resize(frame1, (half_w, screen_h))
        frame2_resized = cv2.resize(frame2, (half_w, screen_h))

        # Add camera labels
        add_label(frame1_resized, "CAMERA 0 (TOP)", (20, 50), (0, 255, 255))
        add_label(frame2_resized, "CAMERA 2 (BOTTOM)", (20, 50), (0, 255, 255))

        # Stack them horizontally
        combined = np.hstack((frame1_resized, frame2_resized))

        # Show window (fits exactly on 1080p screen)
        cv2.imshow("Dual Camera Feed", combined)

        # Exit on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap1.release()
    cap2.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

import cv2
import matplotlib.pyplot as plt
import time

def run_stitching(camera_index=2, delay=3, roi_x=140, roi_y=100, roi_width=240, roi_height=300, num_images_to_capture=4,
                  stitching_mode=cv2.Stitcher_SCANS, output_filename="live_panorama.jpg"):
    """
    Captures images from a webcam, extracts a region of interest (ROI),
    stitches them together to create a panorama, and saves the result.
    Loops the process after stitching.

    Args:
        camera_index (int): Index of the camera to use (default: 0).
        delay (int): Seconds between captures (default: 3).
        roi_x (int): X-coordinate of the top-left corner of the ROI (default: 140).
        roi_y (int): Y-coordinate of the top-left corner of the ROI (default: 100).
        roi_width (int): Width of the ROI (default: 240).
        roi_height (int): Height of the ROI (default: 300).
        num_images_to_capture (int): Number of images to capture (default: 5).
        stitching_mode (int): Stitching mode (cv2.Stitcher_SCANS or cv2.Stitcher_PANORAMA) (default: cv2.Stitcher_SCANS).
        output_filename (str): Name of the file to save the stitched panorama (default: "live_panorama.jpg").

    Returns:
        dict: A dictionary containing defect information. Returns None on failure.
    """

    while True:  # Loop the entire process
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            print(f"Failed to open camera with index {camera_index}.")
            return None

        images = []
        automation_started = False
        captured = 0
        start_time = None

        print("Live feed is shown. Press SPACE to start capturing.")
        print("Press 'q' to quit at any time.")

        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read from camera.")
                break

            # Extract the ROI
            roi = frame[roi_y:roi_y + roi_height, roi_x:roi_x + roi_width]

            cv2.imshow("Live Feed (press SPACE to start, 'q' to quit)", frame)
            cv2.imshow("ROI", roi)  # Show the ROI

            key = cv2.waitKey(1) & 0xFF

            if not automation_started:
                if key == ord('q'):
                    cap.release()
                    cv2.destroyAllWindows()
                    return None
                elif key == 32:  # SPACE to start automation
                    print(f"Automation started! Capturing {num_images_to_capture} images automatically from ROI...")
                    automation_started = True
                    captured = 0
                    images = []
                    start_time = time.time()
            else:
                if key == ord('q'):
                    break
                # Capture every 'delay' seconds
                if captured < num_images_to_capture and (time.time() - start_time >= delay):
                    img_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)  # Convert ROI to RGB
                    images.append(img_rgb)
                    print(f"Captured image {captured + 1}/{num_images_to_capture} from ROI")
                    cv2.imshow(f"Captured {captured + 1}", roi)
                    cv2.waitKey(500)  # Show for half a second
                    captured += 1
                    start_time = time.time()  # Reset timer

                if captured == num_images_to_capture:
                    break

        cap.release()
        cv2.destroyAllWindows()

        if len(images) == num_images_to_capture:
            print("Stitching images...")
            stitcher = cv2.Stitcher_create(stitching_mode)  # Use selected mode
            status, result = stitcher.stitch(images)

            if status == 0:
                print("Stitching successful.")
                # Convert the stitched image to BGR for saving
                stitched_image_bgr = cv2.cvtColor(result, cv2.COLOR_RGB2BGR)
                cv2.imwrite(output_filename, stitched_image_bgr)
                print(f"Panorama saved as {output_filename}")

                # Display the stitched image
                cv2.imshow("Stitched Panorama", stitched_image_bgr)
                cv2.waitKey(0)  # Wait indefinitely until a key is pressed
                cv2.destroyAllWindows()

                # Loop again
                continue

            else:
                print("Stitching failed with status code:", status)
                return None
        else:
            print("Not enough images captured for stitching.")
            return None
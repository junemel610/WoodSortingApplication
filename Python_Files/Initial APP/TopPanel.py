import time
import cv2
import os
from ultralytics import YOLO
import json

import serial
import numpy as np

# Load YOLOv8 model for initial detection
initial_confidence = 0.40
model = YOLO("Machine-Learning/best.pt", task="detect")

# Load YOLOv8 model for defect detection
defect_confidence = 0.20
defect_model = YOLO("Machine-Learning/last.pt", task="detect")

capture_interval = 6  # Capture every 6 seconds
last_capture_time = time.time()
output_dir = './captured_images'
os.makedirs(output_dir, exist_ok=True)
image_counter = 0

# --- Arduino Serial Setup ---
try:
    ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
    time.sleep(2)  # Wait for Arduino to reset
    arduino_available = True
except serial.SerialException:
    print("Warning: Could not connect to Arduino. Grading and Arduino communication will be disabled.")
    arduino_available = False
    ser = None

# Define a fixed region of interest (ROI) for initial detection
fixed_bbox = (1, 155, 635, 355)  # (x1, y1, x2, y2)

def grading_and_arduino(defect_dict):
    if not arduino_available:
        print("Arduino communication disabled.")
        return

    if defect_dict is None:
        print("No defects to grade.")
        return

    total_defects = sum(defect_dict.values()) if defect_dict else 0
    if total_defects <= 2:
        ser.write(b'1')
        print("Grade G2-0: Sent command '1' to Arduino.")
    elif total_defects <= 6:
        ser.write(b'2')
        print("Grade G2-1/2-2/2-3: Sent command '2' to Arduino.")
    else:
        ser.write(b'3')
        print("Grade G2-4: Sent command '3' to Arduino.")

def run_top_panel():
    cap = cv2.VideoCapture(0)
    global last_capture_time, image_counter
    final_output_data = None

    # Initialize the combined annotated frame outside the main loop
    defect_detection_frame = None

    while True:  # Removed event dependencies
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        # Draw the fixed ROI on the live feed
        x1, y1, x2, y2 = fixed_bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Display the live camera feed
        cv2.imshow("Live Camera Feed", frame)

        current_time = time.time()
        if current_time - last_capture_time >= capture_interval:
            image_counter += 1
            print(f"Captured image temporarily (processing)...")
            last_capture_time = current_time

            # Crop to fixed ROI for initial detection
            roi_frame = frame[y1:y2, x1:x2]

            # Clone the ROI frame for annotation
            annotated_roi = roi_frame.copy()

            # Run initial YOLO model on the ROI only
            results = model(roi_frame, imgsz=640, conf=initial_confidence)

            # Draw bounding boxes on the cloned ROI
            for box in results[0].boxes:
                rx1, ry1, rx2, ry2 = map(int, box.xyxy[0].tolist())
                cv2.rectangle(annotated_roi, (rx1, ry1), (rx2, ry2), (255, 0, 0), 2)  # Blue boxes

            # Display the initial detection (ROI with bounding boxes)
            cv2.imshow("Initial Detection", annotated_roi)

            # Reset the defect detection frame for each new capture
            defect_detection_frame = None

            # Iterate through the detected objects in the ROI
            for i, box in enumerate(results[0].boxes):
                # Get the bounding box coordinates (relative to ROI)
                rx1, ry1, rx2, ry2 = map(int, box.xyxy[0].tolist())
                # Convert to full-frame coordinates
                fx1, fy1, fx2, fy2 = rx1 + x1, ry1 + y1, rx2 + x1, ry2 + y1
                cropped_frame = frame[fy1:fy2, fx1:fx2]

                if not cropped_frame.size == 0:
                    defect_results = defect_model(cropped_frame, imgsz=640, conf=defect_confidence)
                    input_image_height, input_image_width, _ = cropped_frame.shape
                    input_image_size = input_image_width * input_image_height
                    class_counts = {2: 0, 3: 0, 4: 0}
                    filtered_boxes = []
                    total_detected_area = 0
                    print(f"Defect Detections for Box {i} (ROI):")
                    for j, box in enumerate(defect_results[0].boxes):
                        class_id = int(box.cls[0])
                        confidence = box.conf[0].item()
                        print(f"  Detection {j}: Class ID = {class_id}, Confidence = {confidence:.2f}")
                        if class_id in [2, 3, 4]:
                            filtered_boxes.append(box)
                            class_counts[class_id] += 1
                            x1_defect, y1_defect, x2_defect, y2_defect = box.xyxy[0].tolist()

                    defect_results[0].boxes = filtered_boxes

                    # Annotate the cropped frame and store it
                    annotated_cropped_frame = defect_results[0].plot()

                    # If this is the first defect detected, set it as the defect_detection_frame
                    if defect_detection_frame is None:
                        defect_detection_frame = annotated_cropped_frame
                    else:
                        # For simplicity, just replace the frame with the latest annotated frame
                        defect_detection_frame = annotated_cropped_frame

                    class_names = {2: "Dead_Knot", 3: "Knot_missing", 4: "Live_Knot"}
                    output_data = {class_names[k]: v for k, v in class_counts.items()}
                    json_output = json.dumps(output_data, indent=4)
                    print(json_output)
                    final_output_data = output_data

                    # Grading logic moved inside the loop, after defect counting
                    print("Grading TopPanel result (inside loop).")
                    grading_and_arduino(output_data)

            # Display and save the defect detection frame (if any detections were made)
            if defect_detection_frame is not None:
                cv2.imshow("Defect Detection", defect_detection_frame)
                output_image_path = os.path.join(output_dir, f"defect_detection_{image_counter}_roi.jpg")
                cv2.imwrite(output_image_path, defect_detection_frame)
                print(f"Saved defect detection image: {output_image_path}")
            else:
                # If no defects are detected, show a black screen
                black_image = np.zeros_like(frame)
                cv2.imshow("Defect Detection", black_image)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    return final_output_data
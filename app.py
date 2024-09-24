import streamlit as st
import cv2
import numpy as np
from cvzone.HandTrackingModule import HandDetector
import google.generativeai as genai
from PIL import Image

# Initialize gemini replace with gemini api key
genai.configure(api_key="GENERATIVEAI_API_KEY")
model = genai.GenerativeModel('gemini-1.5-flash')


detector = HandDetector(staticMode=False, maxHands=1, modelComplexity=0, detectionCon=0.75, minTrackCon=0.75)


cap = cv2.VideoCapture(0)

if not cap.isOpened():
    st.error("Error: Could not open webcam.")
    st.stop()

def initialize_canvas(frame):
    return np.zeros_like(frame)

def process_hand(hand):
    lmList = hand["lmList"]  
    bbox = hand["bbox"]  
    center = hand['center']  
    handType = hand["type"] 
    fingers = detector.fingersUp(hand)  
    return lmList, bbox, center, handType, fingers

def weighted_average(current, previous, alpha=0.5):
    return alpha * current + (1 - alpha) * previous

response_text = None

def send_to_ai(model, canvas, fingers):
    global response_text
    if fingers[4] == 1:
        image = Image.fromarray(canvas)
        response = model.generate_content(["solve this math problem", image])
        response_text = response.text if response else None


prev_pos = None
drawing = False
points = []  
smooth_points = None  

# Initialize canvas
_, frame = cap.read()
canvas = initialize_canvas(frame)

st.title("Virtual Calculator")

# Create a placeholder for the video
frame_placeholder = st.empty()

while True:
    # Capture each frame from the webcam
    success, img = cap.read()

    if not success:
        st.error("Failed to capture image")
        break

    # Flip the image horizontally for a later selfie-view display
    img = cv2.flip(img, 1)

    hands, img = detector.findHands(img, draw=True, flipType=True)

    if hands:
        hand = hands[0]
        lmList, bbox, center, handType, fingers = process_hand(hand)

        # Get the positions of the index and middle finger tips
        index_tip = lmList[8]
        thumb_tip = lmList[4]

        # Determine drawing state based on fingers up
        if fingers[1] == 1 and fingers[2] == 0:  # Only index finger is up
            current_pos = np.array([index_tip[0], index_tip[1]])
            if smooth_points is None:
                smooth_points = current_pos
            else:
                smooth_points = weighted_average(current_pos, smooth_points)
            smoothed_pos = tuple(smooth_points.astype(int))

            if drawing:  # Only add to points if already drawing
                points.append(smoothed_pos)
            prev_pos = smoothed_pos
            drawing = True

        elif fingers[1] == 1 and fingers[2] == 1:  # Both index and middle fingers are up
            drawing = False
            prev_pos = None
            points = []  # Clear points to avoid connection
            smooth_points = None

        elif fingers[0] == 1:  # Thumb is up (reset gesture)
            canvas = initialize_canvas(img)
            points = []
            drawing = False
            prev_pos = None
            smooth_points = None

        elif fingers[4] == 1 and all(f == 0 for f in fingers[:4]):  # Pinky finger up only (send to AI gesture/ finish the input)
            send_to_ai(model, canvas, fingers)

    # Draw polyline on the canvas
    if len(points) > 1 and drawing:
        cv2.polylines(canvas, [np.array(points)], isClosed=False, color=(0, 0, 255), thickness=5)

    # Combine the image and canvas
    img = cv2.addWeighted(img, 0.5, canvas, 0.5, 0)

    # Display the frame in Streamlit
    frame_placeholder.image(img, channels="BGR")

    if response_text:
        st.write(f"AI Response: {response_text}")
        response_text = None

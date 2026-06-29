import cv2
import urllib.request
import os
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

model_path = "pose_landmarker_heavy.task"
if not os.path.exists(model_path):
    print("Downloading model...")
    urllib.request.urlretrieve(
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task",
        model_path
    )

base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    min_pose_detection_confidence=0.5,
    min_pose_presence_confidence=0.5,
    min_tracking_confidence=0.5)

cap = cv2.VideoCapture("/home/kero/Downloads/squat.mp4")
with vision.PoseLandmarker.create_from_options(options) as landmarker:
    ret, frame = cap.read()
    if ret:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
        res = landmarker.detect_for_video(mp_image, timestamp_ms)
        print("Success!", len(res.pose_landmarks))
        if len(res.pose_landmarks) > 0:
            print("First landmark x:", res.pose_landmarks[0][0].x)

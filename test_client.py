"""
Minimal example client for the ST-GCN FastAPI service.

Usage:
    python test_client.py /path/to/video.mp4
"""
import sys
import requests

API_URL = "http://localhost:8000/predict"


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_client.py /path/to/video.mp4")
        sys.exit(1)

    video_path = sys.argv[1]

    with open(video_path, "rb") as f:
        files = {"file": (video_path.split("/")[-1], f, "video/mp4")}
        resp = requests.post(API_URL, files=files, params={"top_k": 5})

    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    print(f"\nPredicted: {data['predicted_class']}  (confidence: {data['confidence']:.2%})")
    print("Top-k:")
    for cls, p in zip(data["top_k_classes"], data["top_k_probs"]):
        print(f"  {cls:35s} {p:.2%}")
    print(f"\nFrames used: {data['num_frames_used']} / raw: {data['num_frames_raw']}")
    print(f"Inference time: {data['inference_seconds']}s")


if __name__ == "__main__":
    main()

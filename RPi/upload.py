import requests
import time

# ── Configuration ─────────────────────────────────────────────
API_URL    = "https://mouldlensai.onrender.com/api/upload"
CAMERA_ID  = "camera_01"          # Change to your actual camera ID
#IMAGE_PATH = "images/t4_mould.jpeg"     # Path to your pre-downloaded image
IMAGE_PATH = "images/black_emoty.jpeg"
# ──────────────────────────────────────────────────────────────

# def capture_image() -> bytes:
#     """Capture a JPEG image from the Raspberry Pi camera."""
#     picam2 = Picamera2()
#     config = picam2.create_still_configuration(main={"size": (1920, 1080)})
#     picam2.configure(config)
#     picam2.start()
#     time.sleep(2)  # warm-up so exposure stabilises
#
#     stream = io.BytesIO()
#     picam2.capture_file(stream, format="jpeg")
#     picam2.stop()
#     picam2.close()
#
#     stream.seek(0)
#     return stream.read()


def load_image(path: str) -> bytes:
    """Load a pre-downloaded image from disk."""
    with open(path, "rb") as f:
        return f.read()


def upload_image(image_bytes: bytes, camera_id: str) -> dict:
    """POST the image to /api/upload as multipart/form-data."""
    files = {
        "file": ("capture.jpg", image_bytes, "image/jpeg"),
    }
    data = {
        "camera_id": camera_id,
    }

    response = requests.post(API_URL, files=files, data=data, timeout=60)
    response.raise_for_status()
    return response.json()


def main():
    print(f"[INFO] Camera ID  : {CAMERA_ID}")
    print(f"[INFO] Endpoint   : {API_URL}")
    print(f"[INFO] Image file : {IMAGE_PATH}")

    # Load image from disk instead of capturing
    print("[INFO] Loading image from disk …")
    image_bytes = load_image(IMAGE_PATH)
    print(f"[INFO] Loaded {len(image_bytes):,} bytes")

    print("[INFO] Uploading to MouldLens AI …")
    try:
        result = upload_image(image_bytes, CAMERA_ID)
        print("[SUCCESS] Response from server:")
        print(result)
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP {e.response.status_code}: {e.response.text}")
    except requests.exceptions.ConnectionError:
        print("[ERROR] Could not reach the server. Check your internet connection.")
    except requests.exceptions.Timeout:
        print("[ERROR] Request timed out. Server may be cold-starting (Render free tier).")
    except FileNotFoundError:
        print(f"[ERROR] Image file not found: {IMAGE_PATH}")


if __name__ == "__main__":
    main()
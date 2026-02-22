# MouldLensAI – Cope & Drag Extraction API

MouldLensAI is a production-ready FastAPI backend designed to extract Cope and Drag values from industrial mould images using the Groq Vision API (LLaMA Scout / LLaMA 3.2 Vision).

## Features
- Upload industrial mould images.
- Deterministic structured extraction of Cope and Drag numbers.
- Handles nested/bracket values automatically.
- Strict Pydantic schema validation.

## Prerequisites
- Python 3.10+
- A valid Groq API Key

## Setup & Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure Environment Variables:
   Add your Groq API key to `.env`:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

## Running the API locally

Start the FastAPI application:
```bash
python app.py
```
Or you can use uvicorn directly:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

## Endpoints

### `POST /api/upload`
Upload an image of a mould to get extracted cope & drag values.

Using `curl`:
```bash
curl -X POST "http://localhost:8000/api/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your_image.jpg"
```

```bash
curl http://localhost:8000/health
```

## How the Pipeline Works

To prevent unnecessary API calls and save costs, MouldLensAI uses **OpenCV** to evaluate an image *before* sending it to the Groq LLM. It routes the extracted values into a strict State Machine (`success`, `empty`, `error`) with a unique `camera_id` for tracking.

### Scenario 1: Valid Mould Image
- **Input:** Clear, well-lit picture of the mould digits.
- **Process:** OpenCV detects small digit-like shapes. Image is passed to Groq LLaMA 4 Scout vision model. Results matched to schema and seamlessly logged sequentially exactly as `status="success"`.
- **Output (HTTP 200 OK):**
```json
{
  "status": "success",
  "message": "Mould detected successfully",
  "cope": "81373",
  "drag": {
    "main": "88234",
    "sub": "644"
  },
  "timestamp": "2024-03-24T18:23:43Z",
  "processing_time_ms": 504.6,
  "camera_id": "CAM_01"
}
```

### Scenario 2: Blank or Empty Image (Or Non-Mould/Dog)
- **Input:** A highly blurred surface, empty wall, or an object completely lacking digits (e.g. dog).
- **Process:** OpenCV adaptive thresholding detects zero valid mathematical shapes, or the LLM actively parses and returns an empty read. The system saves API tokens and jumps straight to the `empty` error block without hallucinating.
- **Output (HTTP 200 OK):**
```json
{
  "status": "empty",
  "message": "Nothing detected, mould missing",
  "cope": null,
  "drag": null,
  "timestamp": "2024-03-24T18:24:10Z",
  "processing_time_ms": 5.2,
  "camera_id": "CAM_01"
}
```

## Running the Telemetry Dashboard

Included in the project is a local Streamlit Analytics Dashboard that acts as a real-time monitor reading directly from the `mould_readings` MongoDB collection.

```bash
streamlit run dashboard.py
```
This local server tracks:
- **Red/Green System Alarms:** Flashes a red warning if 3 consecutive cameras send an `empty` signal (detecting a potential blockage or camera fault).
- **Throughput Latency:** Charts milliseconds taken to parse the OCR models.
- **Detection Ratios:** A real-time success vs failure breakdown.

## Logging Architecture

MouldLensAI uses a dual-stream architecture to ensure zero data loss while remaining easily querable:
1. **Primary Stream (MongoDB):** The moment an image is processed (or rejected), the exact state (`status`, `cope`, `drag`, `processing_time_ms`) is injected securely into the remote `mould_readings` MongoDB collection. The Streamlit dashboard reads exclusively from this live remote feed.
2. **Secondary Stream (Flat JSON):** For redundant backup and strict auditing, the `logger.py` module creates a `python-json-logger` flat file at `logs/mouldlens.log`. This file uses a strict `RotatingFileHandler` customized to roll over precisely at 5MB, meaning the host server will never run out of disk space. This file feed is optimized for Datadog, Splunk, or AWS CloudWatch ingestors.

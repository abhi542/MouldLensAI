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

To prevent unnecessary API calls and save costs, MouldLensAI uses **OpenCV** to evaluate an image *before* sending it to the Groq LLM.

### Scenario 1: Valid Mould Image
- **Input:** Clear, well-lit picture of the mould digits.
- **Process:** OpenCV detects small digit-like shapes. Image is passed to Groq LLaMA 4 Scout vision model. Results matched to Pydantic schema and saved to `mould_readings` MongoDB collection.
- **Output (HTTP 200 OK):**
```json
{
  "cope": "81373",
  "drag": {
    "main": "88234",
    "sub": "644"
  },
  "scan_time_ms": 1145.2,
  "timestamp": "2024-03-24T18:23:43Z"
}
```

### Scenario 2: Blank or Empty Image
- **Input:** A highly blurred, pure-white, or empty surface with no text.
- **Process:** OpenCV adaptive thresholding detects zero valid shapes. The system aborts the LLM call early. Error is logged natively to the `mould_readings` MongoDB collection.
- **Output (HTTP 200 OK):**
```json
{
  "cope": null,
  "drag": null,
  "mould_detected": false,
  "scan_time_ms": 11.2,
  "timestamp": "2024-03-24T18:24:10Z"
}
```

### Scenario 3: Photo of a Dog (Non-mould Image)
- **Input:** Photo of an object without digits (like a dog, a car, or an empty room).
- **Process:** OpenCV detects large, irregular contours that do not match the size/aspect ratio of digits. System aborts LLM call to save tokens. Error is logged natively to the `mould_readings` MongoDB collection.
- **Output (HTTP 200 OK):**
```json
{
  "cope": null,
  "drag": null,
  "mould_detected": false,
  "scan_time_ms": 14.5,
  "timestamp": "2024-03-24T18:25:12Z"
}
```

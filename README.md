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

### `GET /health`
Basic health check.
```bash
curl http://localhost:8000/health
```

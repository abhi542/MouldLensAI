from fastapi import FastAPI, UploadFile, File, HTTPException
import uvicorn
import logging
import time
from datetime import datetime
from schema import MouldReading, MouldReadingResponse
from services import extract_mould_values
from utils import db, save_mould_reading, contains_potential_digits

# Setup FastAPI application
app = FastAPI(
    title="MouldLensAI - Cope & Drag Extraction API",
    description="API for extracting Cope and Drag handwritten identifiers from industrial mould images using Groq Vision API.",
    version="1.0.0"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_db_client():
    db.connect()

@app.on_event("shutdown")
async def shutdown_db_client():
    db.disconnect()

@app.post("/api/upload", response_model=MouldReadingResponse)
async def upload_image(file: UploadFile = File(...)):
    """
    Accepts an image upload of an industrial mould and extracts Cope and Drag values.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")
    
    try:
        contents = await file.read()
        start_time = time.time()
        
        # 1. Pre-process Image (Check if empty/dog/not-mould)
        if not contains_potential_digits(contents):
            end_time = time.time()
            scan_time_ms = round((end_time - start_time) * 1000, 2)
            
            # Create a blank reading response with the flag flipped
            response_data = MouldReadingResponse(
                cope=None,
                drag=None,
                mould_detected=False,
                scan_time_ms=scan_time_ms,
                timestamp=datetime.utcnow()
            )
            
            # Save error log properly to the main collection
            if db.db is not None:
                await save_mould_reading(response_data.model_dump())
                
            return response_data

        # 2. Extract values via LLM
        result = extract_mould_values(contents, file.content_type)
        end_time = time.time()
        
        scan_time_ms = round((end_time - start_time) * 1000, 2)
        current_time = datetime.utcnow()
        
        response_data = MouldReadingResponse(
            cope=result.cope,
            drag=result.drag,
            mould_detected=True,
            scan_time_ms=scan_time_ms,
            timestamp=current_time
        )
        
        # Save valid reading to MongoDB
        if db.db is not None:
            await save_mould_reading(response_data.model_dump())
        
        return response_data
    except ValueError as ve:
        logger.error(f"Configuration error: {str(ve)}")
        raise HTTPException(status_code=500, detail=str(ve))
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during LLM processing.")
    finally:
        await file.close()

@app.get("/health")
def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok", "service": "MouldLensAI"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

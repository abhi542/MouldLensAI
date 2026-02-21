from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import uvicorn
import time
from datetime import datetime
from logger import logger
from schema import MouldReading, MouldReadingResponse
from services import extract_mould_values
from utils import db, save_mould_reading, contains_potential_digits

# Setup FastAPI application
app = FastAPI(
    title="MouldLensAI - Cope & Drag Extraction API",
    description="API for extracting Cope and Drag handwritten identifiers from industrial mould images using Groq Vision API.",
    version="1.0.0"
)



@app.on_event("startup")
async def startup_db_client():
    db.connect()

@app.on_event("shutdown")
async def shutdown_db_client():
    db.disconnect()

@app.post("/api/upload", response_model=MouldReadingResponse)
async def upload_image(
    file: UploadFile = File(...),
    camera_id: str = Form("CAM_01")
):
    """
    Accepts an image upload of an industrial mould, extracts Cope/Drag values,
    and logs the specific camera hardware id.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")
    
    try:
        contents = await file.read()
        start_time = time.time()
        
        # 1. Pre-process Image (Check if empty/dog/not-mould)
        if not contains_potential_digits(contents):
            end_time = time.time()
            processing_time_ms = round((end_time - start_time) * 1000, 2)
            
            # Create an empty state response
            response_data = MouldReadingResponse(
                status="empty",
                message="Nothing detected, mould missing",
                cope=None,
                drag=None,
                timestamp=datetime.utcnow(),
                processing_time_ms=processing_time_ms,
                camera_id=camera_id
            )
            
            # Save empty log to the main collection
            if db.db is not None:
                await save_mould_reading(response_data.model_dump())
                
            # Emit structured JSON log
            logger.info("Mould check failed", extra={
                "camera_id": camera_id,
                "status": "empty",
                "mould_message": "Nothing detected, mould missing",
                "processing_time_ms": processing_time_ms
            })
            
            return response_data

        # 2. Extract values via LLM
        result = extract_mould_values(contents, file.content_type)
        end_time = time.time()
        
        processing_time_ms = round((end_time - start_time) * 1000, 2)
        current_time = datetime.utcnow()
        
        # 3. Post-Process LLM Results (if LLM returned empty/null because it couldn't find digits)
        if result.cope is None and result.drag is None:
            response_data = MouldReadingResponse(
                status="empty",
                message="Nothing detected, mould missing",
                cope=None,
                drag=None,
                timestamp=current_time,
                processing_time_ms=processing_time_ms,
                camera_id=camera_id
            )
            
            if db.db is not None:
                await save_mould_reading(response_data.model_dump())
                
            logger.info("Mould check failed via LLM", extra={
                "camera_id": camera_id,
                "status": "empty",
                "mould_message": "LLM returned null, no digits found",
                "processing_time_ms": processing_time_ms
            })
            return response_data
            
        # 4. Success State
        response_data = MouldReadingResponse(
            status="success",
            message="Mould detected successfully",
            cope=result.cope,
            drag=result.drag,
            timestamp=current_time,
            processing_time_ms=processing_time_ms,
            camera_id=camera_id
        )
        
        # Save valid reading to MongoDB
        if db.db is not None:
            await save_mould_reading(response_data.model_dump())
            
        # Emit structured JSON log
        logger.info("Extraction successful", extra={
            "camera_id": camera_id,
            "status": "success",
            "cope": result.cope,
            "drag_main": result.drag.main if result.drag else None,
            "drag_sub": result.drag.sub if result.drag else None,
            "processing_time_ms": processing_time_ms
        })
        
        return response_data
    except Exception as e:
        end_time = time.time()
        processing_time_ms = round((end_time - start_time) * 1000, 2)
        
        # Craft an error state
        error_response = MouldReadingResponse(
            status="error",
            message=f"Extraction failed: {str(e)}",
            cope=None,
            drag=None,
            timestamp=datetime.utcnow(),
            processing_time_ms=processing_time_ms,
            camera_id=camera_id
        )
        # Log the error state normally
        if db.db is not None:
            await save_mould_reading(error_response.model_dump())
            
        # Emit structured JSON log
        logger.error("Extraction failed", extra={
            "camera_id": camera_id,
            "status": "error",
            "mould_message": f"Extraction failed: {str(e)}",
            "processing_time_ms": processing_time_ms
        })
            
        return error_response
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

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time
from datetime import datetime, timedelta
from bson import ObjectId
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

# Allow CORS for local Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
                inserted_id = await save_mould_reading(response_data.model_dump())
                response_data.id = inserted_id
                
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
                inserted_id = await save_mould_reading(response_data.model_dump())
                response_data.id = inserted_id
                
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
            inserted_id = await save_mould_reading(response_data.model_dump())
            response_data.id = inserted_id
            
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
            inserted_id = await save_mould_reading(error_response.model_dump())
            error_response.id = inserted_id
            
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

@app.get("/api/metrics/recent")
async def get_recent_metrics(hours: int = 24, start_date: str = None, end_date: str = None):
    """
    Returns the detection metrics. Defaults to the last X hours, 
    but can be overridden with ISO 8601 start_date and end_date strings.
    """
    if db.db is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
        
    query = {}
    
    if start_date and end_date:
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            # Add 1 day to end_date to include the entire end day
            end = end + timedelta(days=1)
            query["timestamp"] = {"$gte": start, "$lt": end}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DD)")
    else:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query["timestamp"] = {"$gte": cutoff}
        
    cursor = db.db["mould_readings"].find(query).sort("timestamp", -1)
    logs = await cursor.to_list(length=5000)
    
    # Convert MongoDB ObjectId to string for JSON serialization
    for log in logs:
        log["_id"] = str(log["_id"])
        
    return logs

@app.put("/api/metrics/update/{reading_id}")
async def update_mould_reading(reading_id: str, reading: MouldReading):
    """
    Updates the cope and drag values of an existing automated record in the database.
    Used for Human-in-the-Loop frontend validation/override.
    """
    if db.db is None:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
        
    try:
        obj_id = ObjectId(reading_id)
        update_data = {}
        if reading.cope is not None:
            update_data["cope"] = reading.cope
        if reading.drag is not None:
            update_data["drag"] = reading.drag.model_dump()
            
        if not update_data:
            return {"status": "ok", "message": "No changes requested"}
            
        update_data["is_human_corrected"] = True
            
        result = await db.db["mould_readings"].update_one(
            {"_id": obj_id},
            {"$set": update_data}
        )
        if result.modified_count == 1:
            return {"status": "ok", "message": "Record updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Record not found or no changes made")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

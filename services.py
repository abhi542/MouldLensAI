import base64
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from schema import MouldReading, DragValue, LLMExtraction
from prompts import SYSTEM_PROMPT
from config import settings

logger = logging.getLogger(__name__)

def encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode('utf-8')

def extract_mould_values(image_bytes: bytes, mime_type: str) -> MouldReading:
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not configured in .env")

    # Note: Using 'llama-3.2-90b-vision-preview' as the main Groq vision model currently available.
    # Replace this if/when 'llama-4-scout-vision' alias is used.
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        temperature=0.0,
        max_retries=2
    )
    
    structured_llm = llm.with_structured_output(LLMExtraction)
    
    base64_image = encode_image(image_bytes)
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=[
            {"type": "text", "text": "Extract the COPE and DRAG values from this mould image."},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}  
            }
        ])
    ]
    
    try:
        raw_result = structured_llm.invoke(messages)
        
        drag = None
        if raw_result.drag_main:
            drag = DragValue(main=raw_result.drag_main, sub=raw_result.drag_sub)
            
        final_reading = MouldReading(
            cope=raw_result.cope,
            drag=drag
        )
        return final_reading
    except Exception as e:
        logger.error(f"LLM extraction failed: {str(e)}")
        raise e

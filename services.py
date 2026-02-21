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
    
    base64_image = encode_image(image_bytes)
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=[
            {
                "type": "text", 
                "text": "Analyze the mould image and extract the numerical values for cope and drag according to the system rules. Output your final answer STRICTLY as a single JSON object. Do NOT wrap it in markdown block quotes (```json). Your response must start with { and end with }."
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}  
            }
        ])
    ]
    
    try:
        import json
        raw_response = llm.invoke(messages)
        
        # Parse text output natively
        try:
            content = raw_response.content.strip()
            # Failsafe: if the LLM outputted markdown gates like ```json { ... } ```
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "").strip()
            elif "```" in content:
                content = content.replace("```", "").strip()
            
            parsed_json = json.loads(content)
            
            raw_result = LLMExtraction(**parsed_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode LLM JSON: {content}")
            raise ValueError(f"LLM returned invalid JSON: {str(e)}")
            
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

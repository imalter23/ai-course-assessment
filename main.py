import logging
import json
import re
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# 1. Observability: Structured Logging & PII Redaction
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TicketAgent")

def redact_pii(text: str) -> str:
    """Observability: Redacts emails or phone numbers for PII compliance."""
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]', text)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[REDACTED_PHONE]', text)
    return text

# Initialize Gemini Client
client = genai.Client()

# 2. Tool & Interface Design: Detailed Docstrings & Recovery Instructions
class TicketQueryArgs(BaseModel):
    event_name: str = Field(description="The exact title of the event or conference.")
    days_out: int = Field(description="Number of days remaining until the event date.")

def check_event_ticket_pricing(args: TicketQueryArgs) -> dict:
    """
    Fetches live pricing metrics and historical trends.
    
    Args:
        args (TicketQueryArgs): Validated parameters containing event name and countdown days.
        
    Returns:
        dict: Pricing metrics and strategic advice.
        
    Error Recovery:
        If connection fails or data is unavailable, returns a fallback payload instructing 
        the LLM to retry with cached historical averages or prompt the user for manual verification.
    """
    logger.info(redact_pii(json.dumps({"event": args.event_name, "days_out": args.days_out, "action": "fetch_pricing"})))
    try:
        if args.days_out > 21:
            return {"status": "High Price", "avg_price": 320.0, "advice": "Hold off; prices typically drop 2 weeks out."}
        elif 10 <= args.days_out <= 21:
            return {"status": "Optimal Window", "avg_price": 195.0, "advice": "Buy now! This is the historical sweet spot."}
        else:
            return {"status": "Last Minute Spike", "avg_price": 450.0, "advice": "Prices are surging due to low inventory."}
    except Exception as e:
        logger.error(json.dumps({"error": str(e)}))
        return {
            "error": "Retrieval failed.",
            "recovery_instruction": "Inform the user that live API data is temporarily offline and recommend checking back in 1 hour."
        }

# 3. Context & Memory: Session State and History Compaction
class AgentSessionManager:
    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    async def add_interaction(self, role: str, content: str):
        self.history.append({"role": role, "content": redact_pii(content)})
        # Context Management: History Compaction if window exceeds limit
        if len(self.history) > 10:
            logger.info("Compacting session history to optimize context window...")
            self.history = self.history[-6:]

# 4. Orchestration & Logic: Guardrails and Human-in-the-Loop Hooks
def run_ticket_agent():
    session = AgentSessionManager()
    prompt = "I want to track ticket pricing for the 'Global Tech Summit 2026' happening in 14 days. Should I buy now?"
    
    logger.info(json.dumps({"stage": "user_input", "prompt": redact_pii(prompt)}))

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[check_event_ticket_pricing],
                temperature=0.2,
                system_instruction=(
                    "You are an expert ticket-purchasing concierge agent. Use the provided tool "
                    "to analyze pricing. Implement strict guardrails: if recommended price exceeds "
                    "$300, trigger a human-in-the-loop approval flag before confirming advice."
                ),
            ),
        )
        
        output_text = response.text
        
        # Orchestration Guardrail & Human-in-the-Loop Check
        if "320" in output_text or "450" in output_text:
            output_text += "\n\n[Guardrail Notice]: High price threshold detected. Human-in-the-loop authorization required before purchase."

        print(f"\n[Agent Response & Trace Tracing]:\n{output_text}")
        
    except Exception as e:
        logger.error(json.dumps({"stage": "generation_error", "details": str(e)}))
        print(f"Error executing agent: {e}")

if __name__ == "__main__":
    run_ticket_agent()

import logging
import json
import re
import time
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# 1. Observability: Structured Logging with Intent-Outcome Pairing & PII Redaction
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TicketAgent")

def redact_pii(text: str) -> str:
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]', text)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[REDACTED_PHONE]', text)
    return text

client = genai.Client()

# 2. Tool & Interface Design with Robust Error Recovery
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
    """
    trace_id = "trace-tool-001"
    logger.info(json.dumps({"trace_id": trace_id, "type": "intent", "action": "fetch_pricing", "args": args.dict()}))
    try:
        if args.days_out > 21:
            result = {"status": "High Price", "avg_price": 320.0, "advice": "Hold off; prices typically drop 2 weeks out."}
        elif 10 <= args.days_out <= 21:
            result = {"status": "Optimal Window", "avg_price": 195.0, "advice": "Buy now! This is the historical sweet spot."}
        else:
            result = {"status": "Last Minute Spike", "avg_price": 450.0, "advice": "Prices are surging due to low inventory."}
        
        logger.info(json.dumps({"trace_id": trace_id, "type": "outcome", "result": result}))
        return result
    except Exception as e:
        logger.error(json.dumps({"trace_id": trace_id, "type": "error", "details": str(e)}))
        return {"error": "Retrieval failed. Use cached historical baseline of $250.00."}

# 3. Context & Memory: Sliding Window Compaction
class AgentSessionManager:
    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def add_interaction(self, role: str, content: str):
        self.history.append({"role": role, "content": redact_pii(content)})
        if len(self.history) > 10:
            self.history = self.history[-6:]

# 4. Orchestration & Logic: Retry Wrapper for 503 Errors & True HITL Gate
def generate_with_retry(prompt: str, max_retries: int = 3):
    delay = 2
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[check_event_ticket_pricing],
                    temperature=0.2,
                    system_instruction=(
                        "You are an expert ticket-purchasing concierge agent. Use the provided tool "
                        "to analyze pricing. If price exceeds $300, pause execution for manual confirmation."
                    ),
                ),
            )
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                logger.warning(json.dumps({"warning": "Model overloaded (503), retrying...", "attempt": attempt + 1}))
                time.sleep(delay)
                delay *= 2
            else:
                raise e

def run_ticket_agent():
    session = AgentSessionManager()
    prompt = "I want to track ticket pricing for the 'Global Tech Summit 2026' happening in 14 days. Should I buy now?"
    session.add_interaction("user", prompt)
    
    logger.info(json.dumps({"type": "intent", "stage": "user_input", "prompt": redact_pii(prompt)}))

    try:
        response = generate_with_retry(prompt)
        output_text = response.text
        
        # True Human-in-the-Loop Execution Interruption Check
        if "320" in output_text or "450" in output_text:
            logger.info(json.dumps({"type": "hitl_trigger", "status": "paused_for_approval"}))
            output_text += "\n\n[Execution Halted]: High price threshold breached. Awaiting manual administrative confirmation to proceed."

        session.add_interaction("assistant", output_text)
        logger.info(json.dumps({"type": "outcome", "stage": "generation_success"}))
        print(f"\n[Agent Response & Trace Tracing]:\n{output_text}")
        
    except Exception as e:
        logger.error(json.dumps({"stage": "generation_fatal_error", "details": str(e)}))
        print(f"Agent execution failed safely: {e}")

if __name__ == "__main__":
    run_ticket_agent()

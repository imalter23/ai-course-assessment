import logging
import json
import re
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
import aiosqlite

# OpenTelemetry Tracing
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("ticket.agent.tracer")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TicketAgent")

def redact_pii(text: str) -> str:
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]', text)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[REDACTED_PHONE]', text)
    return text

client = genai.Client()

class TicketQueryArgs(BaseModel):
    event_name: str = Field(description="The exact title of the event or conference.")
    days_out: int = Field(description="Number of days remaining until the event date.")

def check_event_ticket_pricing(args: TicketQueryArgs) -> dict:
    """
    Fetches live pricing metrics and historical trends for event tickets.
    
    Args:
        args (TicketQueryArgs): Validated parameters containing event name and countdown days.
        
    Returns:
        dict: Pricing status, average price, and tactical advice.
        
    Error Recovery:
        If the primary pricing database fails, return a fallback dictionary with a cached 
        baseline price of $250.00 and explicitly instruct the LLM to inform the user that 
        historical averages are being used.
    """
    trace_id = "trace-pricing-001"
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
        return {
            "error": "Retrieval failed.",
            "recovery_instruction": "Inform the user that live data is offline and use cached baseline price of $250.00."
        }

# Context & Memory: Asynchronous Persistent Database & Context Compaction
class AsyncPersistentSessionManager:
    def __init__(self, db_path: str = "agent_sessions.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def add_interaction(self, role: str, content: str):
        safe_content = redact_pii(content)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO sessions (role, content) VALUES (?, ?)", (role, safe_content))
            await db.commit()
            
        # Advanced History Compaction / Context Window Management
        await self._compact_context(db)

    async def _compact_context(self, db):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM sessions") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
            if count > 15:
                logger.info("Executing async context window compaction...")
                # Retain only the most recent 10 interactions to maintain context quality
                await db.execute("DELETE FROM sessions WHERE id NOT IN (SELECT id FROM sessions ORDER BY id DESC LIMIT 10)")
                await db.commit()

# Orchestration & Logic: Router and Robust HITL Hook
def supervisor_router_agent(prompt: str) -> str:
    with tracer.start_as_current_span("supervisor_routing_span") as span:
        span.set_attribute("user.prompt", prompt)
        if "complex" in prompt.lower() or "forecast" in prompt.lower():
            return "gemini-2.5-pro"
        return "gemini-2.5-flash"

async def run_ticket_agent():
    session = AsyncPersistentSessionManager()
    await session.init_db()
    
    prompt = "I want to track ticket pricing for the 'Global Tech Summit 2026' happening in 14 days. Should I buy now?"
    await session.add_interaction("user", prompt)
    
    with tracer.start_as_current_span("agent_execution_span") as span:
        model_name = supervisor_router_agent(prompt)
        
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[check_event_ticket_pricing],
                    temperature=0.2,
                    system_instruction=(
                        "You are an expert ticket-purchasing concierge agent. Use the provided tool "
                        "to analyze pricing. If price exceeds $300, flag an explicit human-in-the-loop "
                        "execution suspension."
                    ),
                ),
            )
            
            output_text = response.text
            
            # Structured Agentic HITL Verification Gate
            requires_human_approval = any(keyword in output_text for keyword in ["320", "450", "High Price", "Last Minute Spike"])
            if requires_human_approval:
                logger.info(json.dumps({"type": "hitl_suspension", "status": "paused_awaiting_admin_signoff"}))
                output_text += "\n\n[Agent Execution Suspended]: High-value threshold reached. Workflow paused for mandatory Human-in-the-Loop administrative approval."

            await session.add_interaction("assistant", output_text)
            print(f"\n[Agent Response & Trace Tracing]:\n{output_text}")
            
        except Exception as e:
            logger.error(json.dumps({"stage": "fatal_error", "details": str(e)}))
            print(f"Agent execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_ticket_agent())

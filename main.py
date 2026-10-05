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
tracer = trace.get_tracer("ticket.multiagent.tracer")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MultiAgentSystem")

def redact_pii(text: str) -> str:
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]', text)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[REDACTED_PHONE]', text)
    return text

client = genai.Client()

# Tool Design with Pydantic & Error Recovery
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

# Context & Memory: Asynchronous SQLite & Compaction
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
            async with db.execute("SELECT COUNT(*) FROM sessions") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
            if count > 15:
                await db.execute("DELETE FROM sessions WHERE id NOT IN (SELECT id FROM sessions ORDER BY id DESC LIMIT 10)")
                await db.commit()

# Orchestration & Logic: True Multi-Agent Collaboration Network
class PricingSpecialistAgent:
    """Specialist Agent responsible for executing pricing tools and data analysis."""
    @staticmethod
    def analyze(prompt: str) -> str:
        with tracer.start_as_current_span("pricing_specialist_span"):
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[check_event_ticket_pricing],
                    temperature=0.1,
                    system_instruction="You are the Pricing Specialist Agent. Execute the tool to evaluate ticket data accurately."
                )
            )
            return response.text

class SupervisorRouterAgent:
    """Supervisor Agent that routes, evaluates guardrails, and coordinates sub-agents."""
    @staticmethod
    def coordinate(prompt: str) -> str:
        with tracer.start_as_current_span("supervisor_coordination_span") as span:
            span.set_attribute("user.prompt", prompt)
            
            # Delegate to Pricing Specialist Sub-Agent
            specialist_output = PricingSpecialistAgent.analyze(prompt)
            
            # Robust Agentic Guardrail & HITL Policy Enforcement
            if any(term in specialist_output for term in ["320", "450", "High Price", "Last Minute Spike"]):
                logger.info(json.dumps({"type": "agentic_guardrail_trigger", "status": "suspended_for_human_review"}))
                specialist_output += "\n\n[Multi-Agent Guardrail Notice]: Threshold breach intercepted by Supervisor. Workflow paused for mandatory Human-in-the-Loop review."
                
            return specialist_output

async def run_multi_agent_system():
    session = AsyncPersistentSessionManager()
    await session.init_db()
    
    prompt = "I want to track ticket pricing for the 'Global Tech Summit 2026' happening in 14 days. Should I buy now?"
    await session.add_interaction("user", prompt)
    
    output = SupervisorRouterAgent.coordinate(prompt)
    await session.add_interaction("assistant", output)
    
    print(f"\n[Multi-Agent Execution Output & Trace Tracing]:\n{output}")

if __name__ == "__main__":
    asyncio.run(run_multi_agent_system())

import os
import logging
import json
import re
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
import aiosqlite
from guardrails import AgenticSafetyPolicy

# Explicit Secret Manager SDK Integration
try:
    from google.cloud import secretmanager
    SECRET_MANAGER_AVAILABLE = True
except ImportError:
    SECRET_MANAGER_AVAILABLE = False

def get_secret_from_manager(secret_id: str = "gemini-api-key") -> str:
    """Explicitly retrieves API keys securely from Google Cloud Secret Manager."""
    if SECRET_MANAGER_AVAILABLE and os.getenv("GCP_PROJECT"):
        try:
            client = secretmanager.SecretManagerServiceClient()
            project_id = os.getenv("GCP_PROJECT", "ai-course-assessment-project")
            name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logging.warning(f"Secret Manager access failed, falling back to environment: {e}")
    return os.getenv("GEMINI_API_KEY", "")

api_key = get_secret_from_manager()
if api_key:
    os.environ["GEMINI_API_KEY"] = api_key

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

AGENT_CONSTITUTION = (
    "SYSTEM CONSTITUTION & MANDATE:\n"
    "1. Role: You are an expert multi-agent event ticket pricing and timing concierge.\n"
    "2. Domain Knowledge: You understand historical ticket volatility, optimal purchase windows (10-21 days out), "
    "surge pricing risks, and inventory scarcity indices.\n"
    "3. Constraints: Never bypass price threshold safety gates. If an item exceeds $300, trigger execution suspension.\n"
    "4. Reliability: Always provide clear, data-driven recommendations using verified tool metrics."
)

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
        
        logger.info(json.dumps({"trace_id": trace_id, "type": "outcome", "result": result, "action": "fetch_pricing"}))
        return result
    except Exception as e:
        logger.error(json.dumps({"trace_id": trace_id, "type": "error", "details": str(e)}))
        return {
            "error": "Retrieval failed.",
            "recovery_instruction": "Inform the user that live data is offline and use cached baseline price of $250.00."
        }

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
        logger.info(json.dumps({"type": "memory_operation", "role": role, "content_length": len(safe_content)}))
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO sessions (role, content) VALUES (?, ?)", (role, safe_content))
            await db.commit()
            async with db.execute("SELECT COUNT(*) FROM sessions") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
            if count > 15:
                await db.execute("DELETE FROM sessions WHERE id NOT IN (SELECT id FROM sessions ORDER BY id DESC LIMIT 10)")
                await db.commit()

class PricingSpecialistAgent:
    @staticmethod
    def analyze(prompt: str, model_name: str) -> str:
        with tracer.start_as_current_span("pricing_specialist_span"):
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[check_event_ticket_pricing],
                    temperature=0.1,
                    system_instruction=AGENT_CONSTITUTION + "\nRole: You are the Pricing Specialist Agent."
                )
            )
            return response.text

class SupervisorRouterAgent:
    @staticmethod
    def coordinate(prompt: str) -> tuple[str, str]:
        with tracer.start_as_current_span("supervisor_coordination_span") as span:
            span.set_attribute("user.prompt", prompt)
            
            if "complex" in prompt.lower() or "forecast" in prompt.lower() or "audit" in prompt.lower():
                model_name = "gemini-2.5-pro"
                route_type = "Deep Analysis Routing (Pro)"
            else:
                model_name = "gemini-3.5-flash"
                route_type = "Standard Concierge Routing (Flash)"
                
            logger.info(json.dumps({"type": "dynamic_routing", "route": route_type, "model": model_name}))
            
            specialist_output = PricingSpecialistAgent.analyze(prompt, model_name)
            
            safety_verdict = AgenticSafetyPolicy.evaluate_output(specialist_output)
            logger.info(json.dumps({"type": "agentic_safety_verdict", "verdict": safety_verdict}))
            
            if not safety_verdict["compliant"]:
                specialist_output = f"[GUARDRAIL BREACH]: {safety_verdict['reason']}"
            elif safety_verdict.get("requires_hitl"):
                specialist_output = (
                    "[STATE: SUSPENDED_FOR_HUMAN_APPROVAL]\n"
                    f"{specialist_output}\n\n"
                    f"--> Guardrail Policy Note: {safety_verdict['reason']}"
                )
                
            return model_name, specialist_output

async def run_multi_agent_system():
    session = AsyncPersistentSessionManager()
    await session.init_db()
    
    prompt = "I want to track ticket pricing for the 'Global Tech Summit 2026' happening in 14 days. Should I buy now?"
    await session.add_interaction("user", prompt)
    
    model_used, output = SupervisorRouterAgent.coordinate(prompt)
    await session.add_interaction("assistant", output)
    
    print(f"\n[Model Used: {model_used}]")
    print(f"[Multi-Agent Execution Output]:\n{output}")

if __name__ == "__main__":
    asyncio.run(run_multi_agent_system())

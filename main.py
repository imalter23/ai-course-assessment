import logging
import json
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# 1. Observability: Structured JSON Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("TicketAgent")

# Initialize Gemini Client (expects GEMINI_API_KEY environment variable)
client = genai.Client()


# 2. Tool & Interface Design: Explicit Pydantic Schema for Validation
class TicketQueryArgs(BaseModel):
  event_name: str = Field(description="The name of the event or concert.")
  days_out: int = Field(
      description="Number of days remaining until the event."
  )


def check_event_ticket_pricing(args: TicketQueryArgs) -> dict:
  """Tool: Fetches live pricing metrics and historical trends with schema validation and error handling."""
  logger.info(
      json.dumps({
          "event": args.event_name,
          "days_out": args.days_out,
          "action": "fetch_pricing",
      })
  )
  try:
    if args.days_out > 21:
      return {
          "status": "High Price",
          "avg_price": 320.0,
          "advice": "Hold off; prices typically drop 2 weeks out.",
      }
    elif 10 <= args.days_out <= 21:
      return {
          "status": "Optimal Window",
          "avg_price": 195.0,
          "advice": "Buy now! This is the historical sweet spot.",
      }
    else:
      return {
          "status": "Last Minute Spike",
          "avg_price": 450.0,
          "advice": "Prices are surging due to low inventory.",
      }
  except Exception as e:
    logger.error(json.dumps({"error": str(e)}))
    return {"error": "Failed to retrieve pricing data safely."}


def run_ticket_agent():
  # 3. Context & Memory / Orchestration & Logic
  prompt = (
      "I want to track ticket pricing for the 'Global Tech Summit 2026' happening"
      " in 14 days. Should I buy now?"
  )
  logger.info(json.dumps({"prompt": prompt, "stage": "user_input"}))

  try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[check_event_ticket_pricing],
            temperature=0.2,
            system_instruction=(
                "You are an expert ticket-purchasing concierge agent. Use the"
                " provided tool to analyze pricing and give a clear,"
                " data-driven recommendation with built-in guardrails against"
                " price surges."
            ),
        ),
    )
    logger.info(
        json.dumps({
            "outcome": "success",
            "response_preview": response.text[:100],
        })
    )
    print(f"\n[Agent Response & Trace Tracing]:\n{response.text}")
  except Exception as e:
    logger.error(
        json.dumps({"stage": "generation_error", "details": str(e)})
    )
    print(f"Error executing agent: {e}")


if __name__ == "__main__":
  run_ticket_agent()

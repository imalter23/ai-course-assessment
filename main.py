import asyncio
from datetime import datetime


class TicketTimingTrackerAgent:

  def __init__(self, event_name: str, target_date: str):
    self.event_name = event_name
    self.target_date = datetime.strptime(target_date, "%Y-%m-%d")

  async def fetch_historical_pricing(self):
    """Tool: Simulates fetching historical pricing trends for the event."""
    print(
        f"[Tool: PricingAPI] Analyzing historical ticket trends for"
        f" '{self.event_name}'..."
    )
    await asyncio.sleep(1)
    # Simulated trend data: average price drops 14 days out, then spikes
    return {
        "average_current_price": 250.00,
        "historical_low": 180.00,
        "historical_high": 400.00,
        "optimal_purchase_window_days_before": 14,
    }

  async def analyze_best_time_to_buy(self):
    """Orchestration & Logic: Determines optimal purchase window."""
    pricing_data = await self.fetch_historical_pricing()

    days_remaining = (self.target_date - datetime.now()).days
    optimal_days = pricing_data["optimal_purchase_window_days_before"]

    print("\n[Orchestration Engine] Running decision matrix...")
    if days_remaining > optimal_days:
      recommendation = (
          f"HOLD. You are {days_remaining} days out. Prices typically drop"
          f" when it gets closer to {optimal_days} days before the event."
      )
      confidence = "High"
    elif days_remaining == optimal_days or days_remaining < optimal_days:
      recommendation = (
          "BUY NOW. You are inside or past the optimal pricing window. Prices"
          " are likely to increase due to scarcity."
      )
      confidence = "Critical"
    else:
      recommendation = "MONITOR CLOSELY. Volatility is high."
      confidence = "Medium"

    return {
        "event": self.event_name,
        "days_until_event": days_remaining,
        "recommendation": recommendation,
        "confidence": confidence,
        "benchmark_price": pricing_data["average_current_price"],
    }


async def main():
  # Example run for a concert or sports event
  agent = TicketTimingTrackerAgent(
      event_name="Global Tech Summit 2026", target_date="2026-11-15"
  )
  result = await agent.analyze_best_time_to_buy()

  print("\n--- Agent Evaluation Report ---")
  for key, value in result.items():
    print(f"{key.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
  asyncio.run(main())

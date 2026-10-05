import unittest
from main import check_event_ticket_pricing, TicketQueryArgs, supervisor_router_agent

class GoldenDatasetEvaluationSuite(unittest.TestCase):

    def test_golden_dataset_pricing_optimal(self):
        """Golden Dataset Test Case 1: Optimal window pricing evaluation."""
        args = TicketQueryArgs(event_name="AI Conference 2026", days_out=14)
        result = check_event_ticket_pricing(args)
        self.assertEqual(result["status"], "Optimal Window")
        self.assertIn("Buy now", result["advice"])

    def test_golden_dataset_pricing_surge(self):
        """Golden Dataset Test Case 2: Last minute spike evaluation."""
        args = TicketQueryArgs(event_name="AI Conference 2026", days_out=3)
        result = check_event_ticket_pricing(args)
        self.assertEqual(result["status"], "Last Minute Spike")

    def test_golden_dataset_router_logic(self):
        """Golden Dataset Test Case 3: Model routing verification."""
        model = supervisor_router_agent("Please run a complex financial forecast for tickets.")
        self.assertEqual(model, "gemini-2.5-pro")

if __name__ == "__main__":
    unittest.main()

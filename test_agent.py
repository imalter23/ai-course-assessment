import unittest
from main import check_event_ticket_pricing, TicketQueryArgs, redact_pii

class TestTicketAgent(unittest.TestCase):
    
    def test_pricing_logic_optimal(self):
        args = TicketQueryArgs(event_name="Test Event", days_out=14)
        result = check_event_ticket_pricing(args)
        self.assertEqual(result["status"], "Optimal Window")

    def test_pii_redaction(self):
        sample = "Contact user at test@example.com or 555-019-2834."
        clean = redact_pii(sample)
        self.assertNotIn("test@example.com", clean)
        self.assertIn("[REDACTED_EMAIL]", clean)

if __name__ == "__main__":
    unittest.main()

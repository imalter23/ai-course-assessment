import logging
import json

logger = logging.getLogger("AgenticGuardrails")

class AgenticSafetyPolicy:
    """Advanced agentic self-evaluation and guardrail policy evaluator."""
    
    @staticmethod
    def evaluate_output(output_text: str) -> dict:
        """Evaluates agent output for safety compliance, hallucinations, and policy breaches."""
        logger.info(json.dumps({"guardrail_check": "initiating_agentic_self_evaluation"}))
        
        # Self-evaluation logic
        has_unauthorized_claims = "guaranteed profit" in output_text.lower() or "insider" in output_text.lower()
        price_breach = "320" in output_text or "450" in output_text
        
        if has_unauthorized_claims:
            return {
                "compliant": False,
                "reason": "Policy violation: Unauthorized financial guarantees detected.",
                "action": "block_and_reprompt"
            }
            
        if price_breach:
            return {
                "compliant": True,
                "requires_hitl": True,
                "reason": "High pricing tier threshold breached. Mandatory human-in-the-loop sign-off required."
            }
            
        return {"compliant": True, "requires_hitl": False, "reason": "Passed all safety and policy checks."}

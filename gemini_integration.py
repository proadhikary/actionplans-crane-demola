import os
import google.generativeai as genai
import json
from dotenv import load_dotenv

load_dotenv()

# Configure the Gemini API
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    # For demo purposes, we might want to warn or mock if no key is present
    print("WARNING: GEMINI_API_KEY not found in environment variables. LLM features will not work.")
else:
    genai.configure(api_key=API_KEY)

class PrescriptiveEngine:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    def analyze_telemetry(self, telemetry_data):
        """
        Analyzes raw telemetry data and returns a structured JSON prescription.
        """
        if not API_KEY:
            return self._mock_response(telemetry_data)

        prompt = f"""
        You are an expert Industrial IoT Prescriptive Engine for crane operations.
        Analyze the following crane telemetry data and provide "Decision-Ready Guidance".
        
        Telemetry Data:
        {json.dumps(telemetry_data, indent=2)}

        Roles:
        1. Owner/Operator: Focus on "Go/No-Go" decisions (Risk vs Revenue).
        2. Maintenance Lead: Focus on Logistics and Part ordering.
        3. Technician: Focus on Diagnostic steps and Speed to fix.

        Output strictly in JSON format with the following structure:
        {{
            "summary": "Brief summary of the condition",
            "type": "Warning" or "Critical" or "Optimal",
            "decision_class": "OPERATE" (Low Risk), "MONITOR" (Medium Risk), or "STOP" (High Risk),
            "confidence_score": integer (0-100),
            "urgency_score": integer (1-10),
            "prescription": {{
                "action": "Main action to take",
                "rationale": "Why this action is needed",
                "estimated_fix_time": "e.g. 2-4 Hours",
                "root_cause_probability": "e.g. Bearing (80%), Alignment (20%)",
                "required_tools": ["Tool 1", "Tool 2"],
                "role_guidance": {{
                    "owner": "Clear GO/NO-GO advice",
                    "maintenance_lead": "Part/Labor needs",
                    "technician": "Diagnostic focus"
                }},
                "verification_protocol": [
                    "Step 1 to verify fix",
                    "Step 2 to verify fix",
                    "Final safety check"
                ]
            }}
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            # Clean up potential markdown formatting from the response
            text = response.text.replace('```json', '').replace('```', '')
            analysis = json.loads(text)
            print(analysis)
            return analysis
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return self._mock_response(telemetry_data)

    def _mock_response(self, telemetry_data):
        """Fallback mock response if API fails or key is missing."""
        return {
            "summary": "Simulated Analysis (API Key Missing or Error)",
            "type": "Warning" if telemetry_data.get('vibration_mm_s', 0) > 4.0 else "Optimal",
            "urgency_score": 5 if telemetry_data.get('vibration_mm_s', 0) > 4.0 else 1,
            "prescription": {
                "action": "Check Sensor Calibration",
                "rationale": "Simulated rationale based on heuristic.",
                "role_guidance": {
                    "owner": "Monitor for trends.",
                    "maintenance_lead": "Verify spare parts inventory.",
                    "technician": "Inspect sensor mounting."
                }
            }
        }

engine = PrescriptiveEngine()

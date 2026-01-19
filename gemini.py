from google import genai
from dotenv import load_dotenv
import re

load_dotenv()

client = genai.Client()

def get_drug_info(drug_name):
    prompt = f"""
    Give patient-friendly information for the drug "{drug_name}".

    Include:

    About the drug (short description)
    Common side effects (bullet points, separate each by a newline or dash)
    Storage instructions (bullet points or sentences)
    Don't include any disclaimers or advice to consult a doctor.
    All information should be concise and easy to understand.

    Format it like this:

    About:
    <text>

    Side Effects:
    - effect 1
    - effect 2
    ...

    Storage:
    <text>
    """

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
    except Exception as e:
        print("Gemini API error:", e)
        return {"about": "No info available", "side_effects": [], "storage": ""}

    text = getattr(response, "text", "")
    
    # Split sections using regex
    about_match = re.search(r"About:\s*(.*?)(?=Side Effects:|$)", text, re.DOTALL)
    side_effects_match = re.search(r"Side Effects:\s*(.*?)(?=Storage:|$)", text, re.DOTALL)
    storage_match = re.search(r"Storage:\s*(.*)", text, re.DOTALL)

    about = about_match.group(1).strip() if about_match else ""
    
    side_effects_text = side_effects_match.group(1).strip() if side_effects_match else ""
    # Split by dash or newline
    side_effects = [line.strip("- ").strip() for line in side_effects_text.splitlines() if line.strip()]

    storage = storage_match.group(1).strip() if storage_match else ""

    return {
        "about": about,
        "side_effects": side_effects,
        "storage": storage
    }

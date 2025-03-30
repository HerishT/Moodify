import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def analyze_sentiment(text):
    """
    Analyze sentiment of text using Google Gemini API.
    Returns a dictionary of emotions with their confidence scores.
    """
    prompt = f"""
    Analyze the emotional content in this text: "{text}"

    Respond with ONLY a JSON object containing emotion names as keys and confidence scores as values.

    Include ONLY these emotions: [admiration, adoration, aesthetic appreciation, amusement, anger,
    anxiety, awe, awkwardness, boredom, calmness, confusion, craving, disgust, empathic pain,
    entrancement, excitement, fear, horror, interest, joy, nostalgia, relief, romance, sadness,
    satisfaction, sexual desire, surprise].

    For emotions not present in the text, assign a value of 0. Ensure all confidence values sum to exactly 1.0.
    Focus on the dominant emotions expressed in the text and give them appropriately high scores.
    """

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt + text)

        # Clean and parse response
        response_text = response.text.strip()

        # Remove code block markers if present
        if response_text.startswith("```"):
              response_text = response_text.replace("```json", "").replace("```","")

        # Parse JSON response
        emotion_dict = json.loads(response_text)
        return emotion_dict

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    user_text = input("Enter text to analyze: ")
    emotions = analyze_sentiment(user_text)
    print(json.dumps(emotions, indent=2))


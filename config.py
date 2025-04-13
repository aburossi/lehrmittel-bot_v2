# config.py
"""Stores configuration constants for the LearnLM Streamlit app."""

import google.generativeai as genai

# --- Model Configuration ---
MODEL_NAME = "gemini-1.5-pro-latest" # Using a standard Gemini model as LearnLM might not be directly available/stable via API
# Or use: "learnlm-1.5-pro-experimental" if confirmed available and working for your key

GENERATION_CONFIG = genai.types.GenerationConfig(
    temperature=0.4,
    top_p=0.95,
    top_k=64,
    max_output_tokens=8192,
    response_mime_type="text/plain",
)

# --- UI Configuration ---
PAGE_TITLE = "Lernen mit KI"
PAGE_ICON = "📚"
LAYOUT = "wide"
PLATZHALTER_AUSWAHL_KAPITEL = "-- Unterkapitel auswählen --"
PLATZHALTER_AUSWAHL_ACTIVITY = "-- Lernmodus auswählen --"
AVAILABLE_ACTIVITIES = [
    PLATZHALTER_AUSWAHL_ACTIVITY,
    "Frag mich ab",          # Quiz
    "Erkläre ein Konzept",   # Explain
    "Verwende eine Analogie", # Analogy
    "Vertiefe ein Thema",    # Deepen
    "Reflektiere/Fasse zusammen", # Reflect/Summarize
    "Erstelle eine Konzeptkarte", # Concept Map
]
ACTIVITY_KEY_MAP = {
    "Frag mich ab": "quiz",
    "Erkläre ein Konzept": "explain",
    "Verwende eine Analogie": "analogy",
    "Vertiefe ein Thema": "deepen",
    "Reflektiere/Fasse zusammen": "reflect",
    "Erstelle eine Konzeptkarte": "concept_map",
    PLATZHALTER_AUSWAHL_ACTIVITY: None
}


# --- AWS Configuration ---
DEFAULT_AWS_REGION = "us-east-1"

# --- File Naming Convention ---
# Example: Hauptkapitel_Thema_UnterkapitelName.txt
FILENAME_PATTERN = "*.txt" # Basic pattern, parsing happens in s3_handler

# --- Initial Messages ---
INITIAL_ASSISTANT_MESSAGE = "Hallo! Bitte wähle zuerst oben ein Unterkapitel aus, mit dem du lernen möchtest."
CHAPTER_SELECTED_MESSAGE = "Kapitel '{subchapter_name}' geladen. Bitte wähle links einen Lernmodus aus, um zu starten."
# llm_handler.py
"""Handles interactions with the Google Generative AI model."""

import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig
import config
import prompts

# --- Model Initialization ---
def configure_genai(api_key: str):
    """Configures the Google Generative AI library."""
    try:
        genai.configure(api_key=api_key)
        print("Google Generative AI configured successfully.")
        return True
    except Exception as e:
        st.error(f"Fehler bei der Konfiguration von Google Generative AI: {e}")
        st.stop() # Stop execution if configuration fails
        return False

def create_system_prompt(activity_key: str | None, subchapter_name: str, subchapter_content: str) -> str:
    """Creates the full system prompt by combining base and activity-specific instructions."""
    if not subchapter_name or not subchapter_content:
        return "Fehler: Unterkapitelname oder Inhalt fehlt für System-Prompt."

    # Start with the base prompt, filling in chapter details
    system_prompt = prompts.BASE_SYSTEM_PROMPT_TEMPLATE.format(
        subchapter_name=subchapter_name,
        subchapter_content=subchapter_content
    )

    # Append specific activity instructions if an activity is selected
    if activity_key and activity_key in prompts.ACTIVITY_PROMPT_INSTRUCTIONS:
        activity_instruction = prompts.ACTIVITY_PROMPT_INSTRUCTIONS[activity_key].format(
            subchapter_name=subchapter_name
        )
        system_prompt += f"\n\n---\n{activity_instruction}"
    elif activity_key:
        # Handle case where activity key is provided but no instructions found (should not happen with proper config)
         print(f"Warnung: Kein Anweisungs-Template für Aktivitätsschlüssel '{activity_key}' gefunden.")
         system_prompt += "\n\n---\nFEHLER: Konnte keine spezifischen Anweisungen für den gewählten Modus laden."
    # If no activity_key, only the base prompt is used (though the app logic should prevent this state during active chat)

    return system_prompt

# Cache the model resource based on the system prompt to avoid re-initialization if the prompt hasn't changed
# Note: This cache might grow if many different system prompts are generated. Consider size limits if necessary.
# Using system_prompt as part of the cache key implicitly.
@st.cache_resource(show_spinner="Initialisiere KI-Modell...")
def initialize_learnlm_model(system_prompt: str) -> genai.GenerativeModel | None:
    """Initializes the GenerativeModel with a system instruction."""
    if not system_prompt or system_prompt.startswith("Fehler"):
         st.error(f"Kann Modell nicht initialisieren wegen ungültigem System-Prompt: {system_prompt}")
         return None
    try:
        # Define safety settings - adjust as needed
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }

        model = genai.GenerativeModel(
            model_name=config.MODEL_NAME,
            generation_config=config.GENERATION_CONFIG,
            system_instruction=system_prompt,
            safety_settings=safety_settings
        )
        print(f"GenerativeModel '{config.MODEL_NAME}' initialisiert.")
        # print(f"System Prompt used:\n---\n{system_prompt[:500]}...\n---") # Debug: Print start of prompt
        return model
    except Exception as e:
        st.error(f"Fehler bei der Initialisierung des KI-Modells ({config.MODEL_NAME}): {e}")
        # Attempt to provide more specific feedback
        if "API key not valid" in str(e):
            st.error("Bitte überprüfen Sie Ihren Gemini API Key in den Streamlit Secrets.")
        elif "model not found" in str(e):
             st.error(f"Das Modell '{config.MODEL_NAME}' konnte nicht gefunden werden. Überprüfen Sie den Modellnamen in config.py und Ihre API-Berechtigungen.")
        return None

# --- Chat Session Management ---
def start_chat_session(model: genai.GenerativeModel, history: list = None) -> genai.ChatSession | None:
    """Starts a new chat session with the given model and optional history."""
    if not model:
        st.error("Kann Chat nicht starten: Kein gültiges Modell vorhanden.")
        return None
    try:
        if history is None:
            history = []
        chat_session = model.start_chat(history=history)
        print(f"Neue Chat-Sitzung gestartet (History Länge: {len(history)}).")
        return chat_session
    except Exception as e:
        st.error(f"Fehler beim Starten der Chat-Sitzung: {e}")
        return None

def send_message(chat_session: genai.ChatSession, user_prompt: str) -> str | None:
    """Sends a message to the chat session and returns the assistant's response text."""
    if not chat_session:
        st.error("Nachricht kann nicht gesendet werden: Keine aktive Chat-Sitzung.")
        return "Entschuldigung, es gibt aktuell keine aktive Chat-Sitzung."
    if not user_prompt:
        st.warning("Leere Benutzereingabe ignoriert.")
        return None # Or return an empty string?

    try:
        with st.spinner("Denke nach..."):
            response = chat_session.send_message(user_prompt)
            print(f"Nachricht gesendet. Antwort erhalten.") # Debug
            # Consider adding safety feedback handling here if needed
            # print(response.prompt_feedback)
            return response.text
    except Exception as e:
        st.error(f"Ein Fehler ist bei der Kommunikation mit der KI aufgetreten: {e}")
        # Provide more specific feedback if possible
        if "response was blocked" in str(e):
             return "Entschuldigung, meine Antwort wurde aufgrund von Sicherheitseinstellungen blockiert. Versuche die Frage anders zu formulieren."
        elif "quota" in str(e).lower():
             return "Entschuldigung, das Anfragelimit (Quota) wurde möglicherweise erreicht. Bitte versuche es später erneut."
        else:
            return f"Entschuldigung, ich bin auf einen Kommunikationsfehler gestoßen: {e}"
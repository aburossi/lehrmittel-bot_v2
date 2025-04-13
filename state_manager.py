# state_manager.py
"""Manages the Streamlit session state."""

import streamlit as st
import config

def initialize_session_state():
    """Initializes the session state variables if they don't exist."""
    if "secrets" not in st.session_state:
        st.session_state.secrets = {}
    if "s3_client" not in st.session_state:
        st.session_state.s3_client = None
    if "subchapter_map" not in st.session_state:
        st.session_state.subchapter_map = {} # {display_name: object_key}
    if "selected_subchapter_name" not in st.session_state:
        st.session_state.selected_subchapter_name = config.PLATZHALTER_AUSWAHL_KAPITEL
    if "selected_subchapter_key" not in st.session_state:
        st.session_state.selected_subchapter_key = None
    if "subchapter_content" not in st.session_state:
        st.session_state.subchapter_content = None

    # Chat related state
    if "messages" not in st.session_state:
        st.session_state.messages = [] # List of {"role": "user/assistant", "content": "..."}
    if "current_activity_key" not in st.session_state:
        st.session_state.current_activity_key = None # e.g., "quiz", "explain"
    if "learnlm_model" not in st.session_state:
        st.session_state.learnlm_model = None # The initialized genai.GenerativeModel
    if "chat_session" not in st.session_state:
        st.session_state.chat_session = None # The active genai.ChatSession

    # Keep track of the activity selected in the sidebar UI element
    if "sidebar_activity_selection" not in st.session_state:
        st.session_state.sidebar_activity_selection = config.PLATZHALTER_AUSWAHL_ACTIVITY


def reset_chat_state(clear_model=True):
    """Resets chat history, active model, and session."""
    print("Resetting chat state...")
    st.session_state.messages = []
    st.session_state.chat_session = None
    st.session_state.current_activity_key = None
    st.session_state.sidebar_activity_selection = config.PLATZHALTER_AUSWAHL_ACTIVITY # Reset UI too
    if clear_model:
        st.session_state.learnlm_model = None


def reset_subchapter_state():
    """Resets subchapter selection and content, and also the chat."""
    print("Resetting subchapter state...")
    st.session_state.selected_subchapter_name = config.PLATZHALTER_AUSWAHL_KAPITEL
    st.session_state.selected_subchapter_key = None
    st.session_state.subchapter_content = None
    reset_chat_state(clear_model=True) # Reset chat when chapter changes


def add_message(role: str, content: str):
    """Adds a message to the chat history in session state."""
    if content: # Avoid adding empty messages
        st.session_state.messages.append({"role": role, "content": content})
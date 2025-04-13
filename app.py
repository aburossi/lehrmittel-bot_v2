# app.py
"""Main Streamlit application file for the LearnLM Tutor."""

import streamlit as st
from google.generativeai import ChatSession # Only for type hint

# Import modules from the repository
import config
import prompts
import secrets_handler
import s3_handler
import llm_handler
import state_manager

# --- 1. Initialize & Configure ---
st.set_page_config(
    page_title=config.PAGE_TITLE,
    page_icon=config.PAGE_ICON,
    layout=config.LAYOUT
)
# Initialize session state variables if they don't exist
state_manager.initialize_session_state()

# --- 2. Load Secrets and Initialize Clients ---
if not st.session_state.secrets:
    st.session_state.secrets = secrets_handler.load_secrets()
    # Configure GenAI only once after secrets are loaded
    if not llm_handler.configure_genai(st.session_state.secrets["GEMINI_API_KEY"]):
        st.stop() # Stop if GenAI config fails

# Initialize S3 client only once
if not st.session_state.s3_client:
    st.session_state.s3_client = s3_handler.get_s3_client(
        aws_access_key_id=st.session_state.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.session_state.secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=st.session_state.secrets.get("AWS_REGION"), # Uses optional value
        bucket_name=st.session_state.secrets["S3_BUCKET_NAME"]
    )
    if not st.session_state.s3_client:
        st.error("S3 Client konnte nicht initialisiert werden. Die Anwendung kann nicht fortfahren.")
        st.stop() # Stop if S3 client fails

# --- 3. Load Available Subchapters ---
if not st.session_state.subchapter_map and st.session_state.s3_client:
    st.session_state.subchapter_map = s3_handler.get_available_subchapters_from_s3(
        st.session_state.secrets["S3_BUCKET_NAME"],
        st.session_state.s3_client
    )

# --- 4. Main Application Area ---
st.title(f"{config.PAGE_ICON} {config.PAGE_TITLE}")
st.caption(f"Betrieben mit Google {config.MODEL_NAME}")

# Subchapter Selection Dropdown
subchapter_options = [config.PLATZHALTER_AUSWAHL_KAPITEL] + list(st.session_state.subchapter_map.keys())

# Check if the previously selected name is still valid
current_selection_name = st.session_state.selected_subchapter_name
if current_selection_name not in subchapter_options:
    current_selection_name = config.PLATZHALTER_AUSWAHL_KAPITEL # Reset if invalid

selected_name = st.selectbox(
    "Wähle das Unterkapitel aus, das du lernen möchtest:",
    options=subchapter_options,
    index=subchapter_options.index(current_selection_name), # Keep selection across reruns
    key="sbSubchapterSelect" # Unique key for the selectbox
)

# --- 5. Handle Subchapter Change ---
if selected_name != st.session_state.selected_subchapter_name:
    if selected_name == config.PLATZHALTER_AUSWAHL_KAPITEL:
        # User deselected chapter
        state_manager.reset_subchapter_state()
        state_manager.add_message("assistant", config.INITIAL_ASSISTANT_MESSAGE)
    else:
        # New chapter selected
        st.session_state.selected_subchapter_name = selected_name
        st.session_state.selected_subchapter_key = st.session_state.subchapter_map.get(selected_name)

        if st.session_state.selected_subchapter_key:
            # Load content
            content = s3_handler.load_subchapter_content_from_s3(
                st.session_state.secrets["S3_BUCKET_NAME"],
                st.session_state.selected_subchapter_key,
                st.session_state.s3_client
            )
            if content:
                st.session_state.subchapter_content = content
                # Successfully loaded, reset chat but keep content
                state_manager.reset_chat_state(clear_model=True)
                state_manager.add_message(
                    "assistant",
                    config.CHAPTER_SELECTED_MESSAGE.format(subchapter_name=selected_name)
                )
                print(f"Subchapter '{selected_name}' content loaded.")
            else:
                # Loading failed (error shown by loader function)
                st.error(f"Konnte Inhalt für '{selected_name}' nicht laden.")
                state_manager.reset_subchapter_state() # Full reset on load failure
                state_manager.add_message("assistant", config.INITIAL_ASSISTANT_MESSAGE)
        else:
            # Should not happen if map is correct, but handle defensively
            st.error(f"Interner Fehler: Konnte Objekt-Schlüssel für '{selected_name}' nicht finden.")
            state_manager.reset_subchapter_state()
            state_manager.add_message("assistant", config.INITIAL_ASSISTANT_MESSAGE)

    # Rerun to update UI immediately after state changes
    st.rerun()


# --- 6. Sidebar for Activity Selection ---
with st.sidebar:
    st.header("Lernmodus")

    # Display current chapter or placeholder
    if st.session_state.selected_subchapter_name != config.PLATZHALTER_AUSWAHL_KAPITEL:
        st.info(f"Aktuelles Kapitel:\n**{st.session_state.selected_subchapter_name}**")
    else:
        st.warning("Bitte zuerst ein Kapitel im Hauptbereich auswählen.")

    # Activity selection - enabled only if a chapter is selected and loaded
    activity_disabled = st.session_state.subchapter_content is None

    selected_activity_display_name = st.radio(
        "Wähle eine Lernaktivität:",
        options=config.AVAILABLE_ACTIVITIES,
        key="sidebar_activity_selection", # Use the state variable directly
        disabled=activity_disabled,
        # index=0 # Start with placeholder selected
    )

    # Add a reset button
    if st.button("Chat zurücksetzen", disabled=activity_disabled):
        state_manager.reset_chat_state(clear_model=True)
        # Add a message indicating reset (optional)
        state_manager.add_message("assistant", "Chat wurde zurückgesetzt. Bitte wähle einen neuen Lernmodus.")
        st.rerun()


# --- 7. Handle Activity Change (Model/Session Reload) ---
new_activity_key = config.ACTIVITY_KEY_MAP.get(selected_activity_display_name)

# Check if activity changed *and* a valid chapter is loaded *and* it's not the placeholder
if (new_activity_key != st.session_state.current_activity_key and
    new_activity_key is not None and
    st.session_state.subchapter_content is not None):

    print(f"Activity changed from '{st.session_state.current_activity_key}' to '{new_activity_key}'")
    st.session_state.current_activity_key = new_activity_key

    # 1. Get current history (important!)
    current_history = st.session_state.messages # Use the simple list format

    # 2. Create the new system prompt for the selected activity
    system_prompt = llm_handler.create_system_prompt(
        activity_key=new_activity_key,
        subchapter_name=st.session_state.selected_subchapter_name,
        subchapter_content=st.session_state.subchapter_content
    )

    # 3. Initialize the model with the new prompt
    # Model initialization is cached by llm_handler based on system_prompt
    st.session_state.learnlm_model = llm_handler.initialize_learnlm_model(system_prompt)

    if st.session_state.learnlm_model:
        # 4. Start a new chat session with the existing history
        st.session_state.chat_session = llm_handler.start_chat_session(
            st.session_state.learnlm_model,
            history=current_history # Pass history to maintain context!
        )

        if st.session_state.chat_session:
            # 5. Add the introductory message for the new mode
            start_message = prompts.ACTIVITY_START_MESSAGES.get(new_activity_key, "Modus gestartet.")
            formatted_start_message = start_message.format(subchapter_name=st.session_state.selected_subchapter_name)

            # Send this initial message to the LLM to get the *actual* first turn/question
            initial_llm_response = llm_handler.send_message(st.session_state.chat_session, f"System: Starte Modus '{selected_activity_display_name}'. Gib die erste Anweisung oder Frage aus.")

            # Display a message indicating the mode change
            state_manager.add_message("assistant", f"Okay, ich wechsle in den Modus: **{selected_activity_display_name}**.")
            if initial_llm_response:
                 state_manager.add_message("assistant", initial_llm_response)
            else:
                 state_manager.add_message("assistant", "Ich bin bereit. Wie kann ich dir in diesem Modus helfen?") # Fallback

            # Rerun to update the chat display with the mode change and initial message
            st.rerun()
        else:
            st.error("Konnte die Chat-Sitzung für den neuen Modus nicht starten.")
            # Reset activity state if session start fails
            st.session_state.current_activity_key = None
            st.session_state.sidebar_activity_selection = config.PLATZHALTER_AUSWAHL_ACTIVITY
    else:
        st.error("Konnte das KI-Modell für den neuen Modus nicht initialisieren.")
        # Reset activity state if model init fails
        st.session_state.current_activity_key = None
        st.session_state.sidebar_activity_selection = config.PLATZHALTER_AUSWAHL_ACTIVITY


# --- 8. Display Chat Messages ---
st.markdown("---")
st.subheader("Chat")

if not st.session_state.messages:
     if st.session_state.selected_subchapter_name == config.PLATZHALTER_AUSWAHL_KAPITEL:
          st.info(config.INITIAL_ASSISTANT_MESSAGE)
     elif st.session_state.subchapter_content and not st.session_state.current_activity_key:
          st.info(config.CHAPTER_SELECTED_MESSAGE.format(subchapter_name=st.session_state.selected_subchapter_name))
     # Add other placeholder messages if needed

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 9. Handle User Input ---
# Determine if chat input should be disabled
chat_input_disabled = (
    st.session_state.subchapter_content is None or
    st.session_state.current_activity_key is None or
    st.session_state.chat_session is None
)
disabled_reason = ""
if st.session_state.subchapter_content is None:
    disabled_reason = "Bitte wähle zuerst ein Unterkapitel."
elif st.session_state.current_activity_key is None:
    disabled_reason = "Bitte wähle links einen Lernmodus."
elif st.session_state.chat_session is None:
    disabled_reason = "Chat-Sitzung wird initialisiert..." # Or specific error

user_prompt = st.chat_input(
    f"Deine Frage im Modus '{st.session_state.sidebar_activity_selection}'..." if not chat_input_disabled else disabled_reason,
    disabled=chat_input_disabled,
    key="user_chat_input"
)

if user_prompt:
    # Add user message to state and display it immediately
    state_manager.add_message("user", user_prompt)
    with st.chat_message("user"):
         st.markdown(user_prompt)

    # Send message to LLM and get response
    assistant_response = llm_handler.send_message(st.session_state.chat_session, user_prompt)

    # Add assistant response to state
    state_manager.add_message("assistant", assistant_response)

    # Rerun to display the new assistant message
    st.rerun()
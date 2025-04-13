# secrets_handler.py
"""Handles loading and validation of secrets from Streamlit."""

import streamlit as st

REQUIRED_SECRETS = [
    "GEMINI_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "S3_BUCKET_NAME"
]

OPTIONAL_SECRETS = {
    "AWS_REGION": None # Will use default from config if not provided
}

def load_secrets():
    """
    Loads required and optional secrets from st.secrets.
    Returns a dictionary with secret keys and values.
    Stops the app with st.error if required secrets are missing.
    """
    secrets = {}
    missing = []
    try:
        # Load required secrets
        for key in REQUIRED_SECRETS:
            value = st.secrets.get(key)
            if not value:
                missing.append(key)
            secrets[key] = value

        if missing:
            st.error(f"Fehlende erforderliche Streamlit-Geheimnisse: {', '.join(missing)}. Bitte konfigurieren.")
            st.stop()

        # Load optional secrets
        for key, default_value in OPTIONAL_SECRETS.items():
            secrets[key] = st.secrets.get(key, default_value)

        print("Secrets loaded successfully.") # For debugging - remove in production
        return secrets

    except KeyError as e:
        st.error(f"Fehlendes erforderliches Streamlit-Geheimnis: {e}. Bitte konfigurieren.")
        st.stop()
    except Exception as e:
        st.error(f"Ein Fehler ist beim Laden der Geheimnisse aufgetreten: {e}")
        st.stop()
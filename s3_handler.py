# s3_handler.py
"""Handles interactions with AWS S3."""

import streamlit as st
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
import config # Import config for defaults like region

# --- AWS S3 Client Initialization (Cached) ---
# Cache the S3 client resource to avoid recreating it on every script run
@st.cache_resource(show_spinner="Verbinde mit AWS S3...")
def get_s3_client(aws_access_key_id: str, aws_secret_access_key: str, region_name: str | None, bucket_name: str) -> boto3.client | None:
    """
    Initializes and returns an S3 client using credentials.
    Tests the connection by trying to access the bucket.
    """
    resolved_region = region_name or config.DEFAULT_AWS_REGION
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=resolved_region
        )
        # Test connection by trying to access the bucket head
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Successfully connected to S3 bucket '{bucket_name}' in region '{resolved_region}'.")
        return s3_client
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404' or 'NotFound' in str(e):
             st.error(f"S3-Bucket '{bucket_name}' nicht gefunden in Region '{resolved_region}'. Überprüfen Sie Bucket-Namen und Region.")
        elif error_code == '403' or 'AccessDenied' in str(e):
            st.error(f"Zugriff auf S3-Bucket '{bucket_name}' verweigert. Überprüfen Sie die IAM-Berechtigungen.")
        elif 'InvalidAccessKeyId' in str(e) or 'SignatureDoesNotMatch' in str(e):
             st.error(f"Ungültige AWS-Anmeldeinformationen. Überprüfen Sie Access Key ID und Secret Access Key.")
        else:
            st.error(f"Fehler beim Verbinden mit S3 ({error_code}): {e}")
        return None
    except Exception as e:
        st.error(f"Unerwarteter Fehler bei der Initialisierung des S3-Clients: {e}")
        return None

# --- S3 Helper Functions (Cached Data) ---

# Cache the list of subchapters to avoid listing S3 objects repeatedly
@st.cache_data(show_spinner="Verfügbare Unterkapitel auflisten...")
def get_available_subchapters_from_s3(bucket_name: str, _s3_client: boto3.client) -> dict[str, str]:
    """
    Lists objects in the S3 bucket, parses names matching the expected pattern,
    and returns a dictionary mapping {display_name: object_key}.
    The _s3_client parameter is used for cache invalidation when the client changes.
    """
    if not _s3_client:
        st.error("S3 Client nicht initialisiert, kann Unterkapitel nicht auflisten.")
        return {}

    subchapter_map = {}
    paginator = _s3_client.get_paginator('list_objects_v2')
    try:
        page_iterator = paginator.paginate(Bucket=bucket_name)
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    object_key = obj['Key']
                    # Handle potential folder structure in object key
                    filename = Path(object_key).name
                    stem = Path(filename).stem

                    # Basic check for format - adapt if needed
                    # Assumes Haupt_Thema_UnterkapitelName.txt
                    parts = stem.split('_')
                    if len(parts) >= 3 and filename.endswith(".txt"):
                        display_name = parts[-1] # Take the last part as display name
                        subchapter_map[display_name] = object_key
                    else:
                        # Optionally log skipped files for debugging
                        # print(f"Info: Skipping object with unexpected name format: {object_key}")
                        pass # Silently skip files not matching the format

    except ClientError as e:
        st.error(f"Fehler beim Auflisten von Dateien im S3-Bucket '{bucket_name}': {e}")
        return {}
    except Exception as e:
        st.error(f"Ein unerwarteter Fehler ist beim Auflisten von S3-Dateien aufgetreten: {e}")
        return {}

    if not subchapter_map:
         st.warning(f"Keine gültigen Unterkapitel-Dateien (Format: ..._UnterkapitelName.txt) im S3-Bucket '{bucket_name}' gefunden.")

    # Sort by display name for consistent dropdown order
    sorted_subchapter_map = dict(sorted(subchapter_map.items()))
    return sorted_subchapter_map

# Cache the content of a specific subchapter
@st.cache_data(show_spinner="Lade Inhalt des Unterkapitels...")
def load_subchapter_content_from_s3(bucket_name: str, object_key: str, _s3_client: boto3.client) -> str | None:
    """Loads the content of a specific object from S3."""
    if not _s3_client:
        st.error("S3 Client nicht initialisiert, kann Inhalt nicht laden.")
        return None
    if not object_key:
        st.error("Kein Objekt-Schlüssel angegeben zum Laden.")
        return None

    try:
        response = _s3_client.get_object(Bucket=bucket_name, Key=object_key)
        content = response['Body'].read().decode('utf-8')
        print(f"Successfully loaded content for object key: {object_key}")
        return content
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'NoSuchKey':
            st.error(f"Unterkapitel-Datei '{object_key}' nicht im S3-Bucket '{bucket_name}' gefunden.")
        elif error_code == 'AccessDenied':
            st.error(f"Zugriff auf Datei '{object_key}' verweigert. Überprüfen Sie die IAM-Berechtigungen.")
        else:
            st.error(f"Fehler beim Zugriff auf die S3-Datei '{object_key}' ({error_code}): {e}")
        return None
    except Exception as e:
        st.error(f"Ein Fehler ist beim Lesen der Datei '{object_key}' aus S3 aufgetreten: {e}")
        return None
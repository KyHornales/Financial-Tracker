import os

import streamlit as st
from supabase import Client, create_client


@st.cache_resource
def get_supabase() -> Client:
    """Create the server-only Supabase client.

    The secret key bypasses RLS and must only exist in Streamlit secrets.
    It must never be committed or sent to a browser.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        try:
            url = url or st.secrets.get("SUPABASE_URL")
            key = key or st.secrets.get("SUPABASE_SECRET_KEY") or st.secrets.get(
                "SUPABASE_SERVICE_ROLE_KEY"
            )
        except Exception:
            pass
    if not url or not key:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_SECRET_KEY in Streamlit secrets."
        )
    return create_client(url, key)


supabase = get_supabase()

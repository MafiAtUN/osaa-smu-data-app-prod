import streamlit as st
import hmac
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

USE_APP_PASSWORD = os.getenv("USE_APP_PASSWORD", "false").lower() == "true"

# check password
def check_password():
    """
    Returns `True` if the user had the correct password.
    """

    def password_entered():
        """
        Checks whether a password entered by the user is correct.
        """

        if hmac.compare_digest(st.session_state["app_password"], os.getenv("app_password")):
            st.session_state["app_password_correct"] = True
            del st.session_state["app_password"]  # remove the password
        else:
            st.session_state["app_password_correct"] = False

    # return True if the password is validated.
    if st.session_state.get("app_password_correct", False):
        return True

    # show input for password.
    st.image("content/OSAA-Data-logo.svg")

    st.warning("This app is **in development**. It is only to be used by authorized members of OSAA.", icon="⚠️")

    st.markdown("Welcome to the Office of the Special Advisor to Africa's Strategic Management Unit's Data App. Please enter the app password to access the data app.")

    st.text_input(
        "Password",
        placeholder="enter the app password...",
        on_change=password_entered,
        key="app_password",
        label_visibility="collapsed"
    )

    if "app_password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False


if USE_APP_PASSWORD and not check_password():
    st.stop()

# create session states
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = {}
if 'formatted_chat_history' not in st.session_state:
    st.session_state.formatted_chat_history = {}






# Simple routing - execute home.py as the main page
# Navigation is handled via st.page_link in home.py
st.set_page_config(page_title="SMU Data App", page_icon="🏠", layout="wide")

# Execute home.py
with open("home.py", "r", encoding="utf-8") as f:
    home_code = f.read()
exec(compile(home_code, "home.py", "exec"), globals())
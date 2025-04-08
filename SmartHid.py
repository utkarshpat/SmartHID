import streamlit as st
from streamlit_option_menu import option_menu
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import time
import json

# ===== PASSWORD PROTECTION =====
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.login_attempts = 0
    st.session_state.lockout_until = 0

def check_password():
    if st.session_state.authenticated:
        return True

    if st.session_state.lockout_until > time.time():
        remaining = int(st.session_state.lockout_until - time.time())
        st.error(f"⏳ Account locked. Try again in {remaining//60}m {remaining%60}s")
        st.stop()

    with st.form("auth_form"):
        st.warning("🔐 Enter password to access SmartHID Pro")
        password = st.text_input("Password", type="password", key="password_input")
        submit = st.form_submit_button("Login")

        if submit:
            if password == st.secrets.get("APP_PASSWORD"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.session_state.login_attempts += 1
                remaining_attempts = 5 - st.session_state.login_attempts
                st.error(f"❌ Wrong password! {remaining_attempts} attempts remaining")
                if st.session_state.login_attempts >= 5:
                    st.session_state.lockout_until = time.time() + 300
                    st.error("🚫 Account locked for 5 minutes")
                    st.rerun()

    st.stop()

check_password()

# ===== AUTO REFRESH TIMER (best approach, no flicker) =====
refresh_interval = 5  # seconds
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
else:
    now = time.time()
    if now - st.session_state.last_refresh >= refresh_interval:
        st.session_state.last_refresh = now
        st.experimental_rerun()

# ===== FIREBASE INIT =====
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(json.loads(st.secrets["firebase_json"]))
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://smarthid-32dfc-default-rtdb.firebaseio.com/'
        })
    except Exception as e:
        st.error(f"Firebase initialization failed: {e}")
        st.stop()

# ===== ENHANCED STATUS =====
def get_device_status():
    try:
        status_data = db.reference('hid/status').get() or {}
        last_seen = status_data.get("lastSeen", 0)
        is_online = status_data.get("online", False) and (time.time() - last_seen < 15)
        return "🟢 Online" if is_online else "🔴 Offline", last_seen
    except:
        return "🔴 Error", 0

# ===== DATABASE SETUP =====
hid_ref = db.reference('hid')
typing_ref = hid_ref.child('inputText')
mouse_ref = hid_ref.child('mouseData')
ducky_ref = hid_ref.child('duckyScript')
mode_ref = hid_ref.child('mode')
led_ref = hid_ref.child('ledColor')

def init_path(ref, default):
    if not ref.get(): ref.set(default)

init_path(typing_ref, "")
init_path(mouse_ref, {"x":0,"y":0,"click":False,"leftClick":False,"rightClick":False,"scroll":0})
init_path(ducky_ref, "")
init_path(mode_ref, "Typing Mode")
init_path(led_ref, "OFF")

# ===== PAGE CONFIG =====
st.set_page_config(page_title="SmartHID Pro", page_icon="🖱", layout="wide")

# ===== CUSTOM CSS =====
st.markdown("""
<style>
#mouseCanvas {
    border: 2px solid black;
    position: relative;
    margin: auto;
}
#cursor {
    background-color: red;
    border-radius: 50%;
    width: 10px;
    height: 10px;
    position: absolute;
    pointer-events: none;
}
.led-preview {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    margin: 10px auto;
    box-shadow: 0 0 10px rgba(0,0,0,0.2);
}
.status-box {
    background: #f8f9fa;
    padding: 10px;
    border-radius: 5px;
    border: 1px solid #ddd;
}
</style>
""", unsafe_allow_html=True)

# ===== SIDEBAR =====
with st.sidebar:
    st.title("Control Panel")
    current_mode = st.radio("**Operation Mode**", ["Typing Mode", "Mouse Mode", "Ducky Mode"], index=0)
    try:
        mode_ref.set(current_mode)
    except Exception as e:
        st.error(f"Failed to set mode: {e}")

    st.markdown("---")
    st.subheader("💡 LED Settings")
    led_options = ["OFF", "RED", "GREEN", "BLUE", "YELLOW", "WHITE", "Custom RGB"]
    led_color = st.selectbox("Select Color:", led_options)

    if led_color == "Custom RGB":
        custom_rgb = st.color_picker("Pick a Custom RGB Color", "#FFFFFF")
        try:
            led_ref.set(custom_rgb)
            preview_color = custom_rgb
        except Exception as e:
            st.error(f"Failed to set custom RGB: {e}")
    else:
        try:
            led_ref.set(led_color)
            preview_color = led_color.lower() if led_color != "OFF" else "black"
        except Exception as e:
            st.error(f"Failed to set LED color: {e}")

    st.markdown(f'<div class="led-preview" style="background-color: {preview_color};"></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📡 Device Status")
    status, last_seen = get_device_status()
    last_seen_str = datetime.fromtimestamp(last_seen).strftime('%H:%M:%S') if last_seen > 0 else "Never"
    st.markdown(f"""
    <div class="status-box" style="background-color: black; color: white">
        <b>ESP32:</b> {status}<br>
        <small>Last active: {last_seen_str}</small>
    </div>
    """, unsafe_allow_html=True)

# ===== PAGES =====
def home_page():
    st.title("🎮 SmartHID Pro Controller")
    st.markdown("""
    ## Remote Device Control System
    **Features:**
    - ✍️ **Text Typing** - Send keyboard input
    - 🖱️ **Precision Mouse** - Real-time control
    - 🦆 **Ducky Script** - Automate tasks
    - 🌈 **LED Control** - RGB lighting
    """)

def keyboard_page():
    st.title("⌨️ Text Input Mode")
    if current_mode == "Typing Mode":
        text = st.text_area("Enter text to send:", height=200)
        if st.button("Send Text"):
            if text.strip():
                try:
                    typing_ref.set(text.strip())
                    st.success("Text sent!")
                except Exception as e:
                    st.error(f"Failed to send text: {e}")
            else:
                st.warning("Please enter some text")
    else:
        st.warning("Switch to Typing Mode in sidebar")

def mouse_page():
    st.title("🖱️ Precision Mouse Control")
    if current_mode == "Mouse Mode":
        st.markdown("Canvas for mouse control would go here.")
        st.warning("Mouse control UI not implemented in this demo.")
    else:
        st.warning("Switch to Mouse Mode in sidebar")

def ducky_page():
    st.title("🦆 Ducky Script Mode")
    if current_mode == "Ducky Mode":
        script = st.text_area("Enter Ducky Script:", height=300)
        if st.button("Execute Script"):
            if script.strip():
                try:
                    ducky_ref.set(script.strip())
                    st.success("Script sent!")
                except Exception as e:
                    st.error(f"Failed to send script: {e}")
            else:
                st.warning("Please enter a valid script")
    else:
        st.warning("Switch to Ducky Mode in sidebar")

# ===== PAGE ROUTING =====
PAGES = {
    "Home": home_page,
    "Keyboard": keyboard_page,
    "Mouse": mouse_page,
    "Ducky": ducky_page
}

selected = option_menu(
    None,
    ["Home", "Keyboard", "Mouse", "Ducky"],
    icons=["house", "keyboard", "mouse", "terminal"],
    menu_icon="cast",
    default_index=0,
    orientation="horizontal"
)

PAGES[selected]()

# ===== FOOTER =====
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
    SmartHID Pro | Developed by Utkarsh Patel
</div>
""", unsafe_allow_html=True)

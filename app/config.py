"""
File Name : config.py

What this file does:
- Reads all secret keys and settings from the .env file
- Keeps all app settings in one place

Who uses this file:
- service files
- router files
- other backend files

Where this file stays:
- Inside the app/ folder

Connected with:
- .env file
"""

from dotenv import load_dotenv
import os


# Load all values from the .env file
load_dotenv()


# ============================================
# APP SETTINGS
# Purpose:
# Basic app information and security settings
# ============================================

# App name
APP_NAME = os.getenv("APP_NAME", "InsureFlow AI")

# Secret key for app security
SECRET_KEY = os.getenv("SECRET_KEY")



# ============================================
# VAPI SETTINGS
# Purpose:
# Used to connect with Vapi Voice AI
#
# Used in:
# vapi_service.py
# ============================================

# Vapi API key
VAPI_API_KEY = os.getenv("VAPI_API_KEY")

# Vapi webhook secret
VAPI_WEBHOOK_SECRET = os.getenv("VAPI_WEBHOOK_SECRET")

# Main Vapi API URL
VAPI_BASE_URL = "https://api.vapi.ai"



# ============================================
# TWILIO SETTINGS
# Purpose:
# Used for phone calls
#
# Used in:
# vapi_service.py
# ============================================

# Twilio account SID
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")

# Twilio auth token
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Twilio phone number
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")



# ============================================
# GOHIGHLEVEL CRM SETTINGS
# Purpose:
# Used to update lead status after calls
#
# Used in:
# ghl_service.py
# ============================================

# GoHighLevel API key
GHL_API_KEY = os.getenv("GHL_API_KEY")

# GoHighLevel API base URL
GHL_BASE_URL = os.getenv("GHL_BASE_URL")



# ============================================
# REDIS SETTINGS
# Purpose:
# Used to manage outbound call queue
#
# Used in:
# call_worker.py
# ============================================

# Redis connection URL
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")



# ============================================
# DATABASE PARTNER API SETTINGS
# Purpose:
# Used to connect with external database API
#
# Used in:
# db_service.py
# ============================================

# Database API URL
DB_API_URL = os.getenv("DB_API_URL")

# Database API secret key
DB_API_KEY = os.getenv("DB_API_KEY")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


if __name__ == "__main__":
    print("Config file run successfully!")
    print(f"App Name: {APP_NAME}")
    print(f"Twilio Number: {TWILIO_PHONE_NUMBER}")

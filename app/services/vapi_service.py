"""
ফাইলের নাম  : vapi_service.py
ফাইলের কাজ  : Vapi API এর সাথে সব যোগাযোগ এই file করে
               1. Agency র জন্য Assistant বানানো
               2. Outbound call শুরু করা
               3. Call এর details নেওয়া
               4. Assistant delete করা
কে use করে  : campaigns.py, webhooks.py
সংযুক্ত     : config.py (Vapi API key এর জন্য)
"""

import httpx
from app import config


# ============================================
# VAPI CLIENT
# কাজ : Vapi API তে request পাঠানোর জন্য
#       সব request এ Authorization header লাগে
# ============================================
def get_vapi_headers():
    """
    কাজ  : Vapi API request এর জন্য headers বানায়
    দেয়  : Authorization header সহ dict
    """
    return {
        "Authorization": f"Bearer {config.VAPI_API_KEY}",
        "Content-Type": "application/json"
    }


# ============================================
# CREATE AGENCY ASSISTANT
# কাজ : নতুন Agency sign up করলে তাদের জন্য
#       Vapi তে automatically Assistant বানায়
# কে call করে : campaigns.py (agency প্রথমবার campaign করলে)
# ============================================
async def create_agency_assistant(
    agency_id: int,
    agency_name: str,
    business_type: str,
    custom_prompt: str,
    transfer_number: str,
    welcome_message: str
):
    """
    কাজ  : Agency র জন্য Vapi তে Assistant create করে
    নেয়  : agency_id, agency_name, business_type, 
            custom_prompt, transfer_number, welcome_message
    দেয়  : assistant_id (Vapi থেকে)
    করে  : Vapi API তে POST request করে Assistant বানায়
    """

    # Agency র জন্য System Prompt বানাও
    system_prompt = f"""
    You are an AI voice assistant for {agency_name}.
    Business Type: {business_type}
    
    {custom_prompt}
    
    Rules:
    - Be polite and professional always
    - Speak in Bengali if customer speaks Bengali
    - Speak in English if customer speaks English
    - If customer is interested in insurance → use bookAppointment tool
    - If customer wants to talk to a human agent → use transfer_call_tool
    - If customer is busy → politely end the call
    - If customer is not interested → politely end the call
    - Keep conversation short and focused
    - Never make up information about policies
    """

    # Vapi Assistant Configuration
    assistant_config = {
        "name": f"{agency_name}_Assistant_{agency_id}",
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ],
            "temperature": 0.7,
            "maxTokens": 500
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "charlie"
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en"
        },
        "firstMessage": welcome_message,
        "firstMessageMode": "assistant-speaks-first",
        "tools": [
            {
                # Book Appointment Tool
                # কাজ: Meeting book করার জন্য FastAPI call করে
                "type": "function",
                "function": {
                    "name": "bookAppointment",
                    "description": "Use this when customer wants to book a meeting or appointment",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_name": {
                                "type": "string",
                                "description": "Name of the customer"
                            },
                            "datetime": {
                                "type": "string",
                                "description": "Preferred date and time"
                            },
                            "lead_id": {
                                "type": "string",
                                "description": "ID of the lead"
                            },
                            "timezone": {
                                "type": "string",
                                "description": "Customer timezone"
                            }
                        },
                        "required": ["customer_name", "datetime"]
                    }
                },
                "server": {
                    "url": f"{config.NGROK_URL}/tools/book-appointment",
                    "headers": {
                        "x-vapi-secret": config.VAPI_WEBHOOK_SECRET
                    }
                }
            },
            {
                # Transfer Call Tool
                # কাজ: Customer কে human agent এ transfer করে
                "type": "transferCall",
                "destinations": [
                    {
                        "type": "number",
                        "number": transfer_number,
                        "message": "একজন এজেন্টের সাথে সংযুক্ত করছি, অপেক্ষা করুন।"
                    }
                ]
            }
        ],
        "serverUrl": f"{config.NGROK_URL}/webhooks/vapi",
        "serverUrlSecret": config.VAPI_WEBHOOK_SECRET
    }

    # Vapi API তে Request পাঠাও
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.VAPI_BASE_URL}/assistant",
            json=assistant_config,
            headers=get_vapi_headers(),
            timeout=30
        )

    if response.status_code == 201:
        assistant_data = response.json()
        assistant_id = assistant_data.get("id")
        print(f"✅ Assistant created | Agency: {agency_id} | Assistant ID: {assistant_id}")
        return assistant_id
    else:
        print(f"❌ Assistant creation failed | Error: {response.text}")
        return None


# ============================================
# START OUTBOUND CALL
# কাজ : একটা lead কে outbound call দেয়
# কে call করে : call_worker.py (queue থেকে lead নিয়ে)
# ============================================
async def start_outbound_call(
    lead_phone: str,
    lead_id: int,
    agency_id: int,
    assistant_id: str,
    twilio_number: str
):
    """
    কাজ  : Lead কে Vapi দিয়ে outbound call দেয়
    নেয়  : lead_phone, lead_id, agency_id, assistant_id, twilio_number
    দেয়  : call_id (Vapi থেকে)
    করে  : Vapi API তে POST request করে call শুরু করে
    """

    call_config = {
        "assistantId": assistant_id,
        "phoneNumberId": twilio_number,
        "customer": {
            "number": lead_phone
        },
        # Call এর সাথে extra data পাঠাচ্ছি
        # Webhook এ এই data পাবো
        "assistantOverrides": {
            "variableValues": {
                "lead_id": str(lead_id),
                "agency_id": str(agency_id)
            }
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.VAPI_BASE_URL}/call/phone",
            json=call_config,
            headers=get_vapi_headers(),
            timeout=30
        )

    if response.status_code == 201:
        call_data = response.json()
        call_id = call_data.get("id")
        print(f"✅ Call started | Lead: {lead_id} | Call ID: {call_id}")
        return call_id
    else:
        print(f"❌ Call failed | Lead: {lead_id} | Error: {response.text}")
        return None


# ============================================
# GET CALL DETAILS
# কাজ : একটা call এর সব details নেয় Vapi থেকে
# কে call করে : webhooks.py (call শেষ হলে)
# ============================================
async def get_call_details(call_id: str):
    """
    কাজ  : Vapi থেকে call এর সব details নিয়ে আসে
    নেয়  : call_id
    দেয়  : call details (transcript, duration, recording)
    করে  : Vapi API তে GET request করে
    """

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.VAPI_BASE_URL}/call/{call_id}",
            headers=get_vapi_headers(),
            timeout=30
        )

    if response.status_code == 200:
        print(f"✅ Call details fetched | Call ID: {call_id}")
        return response.json()
    else:
        print(f"❌ Failed to get call details | Call ID: {call_id}")
        return None


# ============================================
# DELETE ASSISTANT
# কাজ : Agency delete হলে তাদের Assistant ও delete করে
# কে call করে : agency management (agency বন্ধ হলে)
# ============================================
async def delete_assistant(assistant_id: str):
    """
    কাজ  : Vapi থেকে Assistant delete করে
    নেয়  : assistant_id
    দেয়  : success/failure
    কখন : Agency account বন্ধ হলে
    """

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{config.VAPI_BASE_URL}/assistant/{assistant_id}",
            headers=get_vapi_headers(),
            timeout=30
        )

    if response.status_code == 200:
        print(f"✅ Assistant deleted | ID: {assistant_id}")
        return True
    else:
        print(f"❌ Failed to delete assistant | ID: {assistant_id}")
        return False
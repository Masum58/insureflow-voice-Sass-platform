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
# CREATE BOOK APPOINTMENT TOOL
# কাজ : Vapi তে bookAppointment tool বানায়
# ============================================
async def create_book_appointment_tool(agency_id: int):
    """
    কাজ  : Agency র জন্য bookAppointment tool বানায়
    দেয়  : tool_id
    """
    tool_config = {
        "type": "function",
        "function": {
            "name": "bookAppointment",
            "description": "Use when customer wants to book a meeting",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "datetime"     : {"type": "string"},
                    "lead_id"      : {"type": "string"},
                    "timezone"     : {"type": "string"}
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
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.VAPI_BASE_URL}/tool",
            json=tool_config,
            headers=get_vapi_headers(),
            timeout=30
        )

    if response.status_code == 201:
        tool_id = response.json().get("id")
        print(f"✅ bookAppointment tool created | ID: {tool_id}")
        return tool_id
    else:
        print(f"❌ Tool creation failed | {response.text}")
        return None


# ============================================
# CREATE TRANSFER CALL TOOL
# কাজ : Vapi তে transferCall tool বানায়
# ============================================
async def create_transfer_call_tool(transfer_number: str):
    """
    কাজ  : Agency র জন্য transferCall tool বানায়
    নেয়  : transfer_number (agent এর number)
    দেয়  : tool_id
    """
    tool_config = {
        "type": "transferCall",
        "destinations": [
            {
                "type"   : "number",
                "number" : transfer_number,
                "message": "একজন এজেন্টের সাথে সংযুক্ত করছি"
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.VAPI_BASE_URL}/tool",
            json=tool_config,
            headers=get_vapi_headers(),
            timeout=30
        )

    if response.status_code == 201:
        tool_id = response.json().get("id")
        print(f"✅ transferCall tool created | ID: {tool_id}")
        return tool_id
    else:
        print(f"❌ Transfer tool failed | {response.text}")
        return None

# ============================================
# CREATE SEARCH KNOWLEDGE BASE TOOL
# ============================================
async def create_search_knowledge_base_tool(agency_id: int):
    """
    কাজ  : Agency র জন্য searchKnowledgeBase tool create করে
    """
    tool_config = {
        "type": "function",
        "messages": [
            {
                "type": "request-start",
                "content": "Give me a moment.",
            }
        ],
        "function": {
            "name": "searchKnowledgeBase",
            "description": "Searches the insurance knowledge base for exact policy details. Use this to find plan information, premiums, and policy documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query based on customer question."
                    },
                    "agency_id": {
                        "type": "integer",
                        "default": agency_id
                    }
                },
                "required": ["query"]
            }
        },
        "server": {
            "url": f"{config.NGROK_URL}/webhooks/vapi",
            "secret": config.VAPI_WEBHOOK_SECRET
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.VAPI_BASE_URL}/tool",
            json=tool_config,
            headers=get_vapi_headers(),
            timeout=30
        )

    if response.status_code == 201:
        tool_id = response.json().get("id")
        print(f"✅ searchKnowledgeBase tool created | ID: {tool_id}")
        return tool_id
    else:
        print(f"❌ Search Knowledge Base tool failed | {response.text}")
        return None


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
    দেয়  : assistant_id, book_tool_id, transfer_tool_id
    """

    # Step 1 — Tools বানাও
    print(f"🔧 Creating tools for Agency {agency_id}...")
    book_tool_id     = await create_book_appointment_tool(agency_id)
    transfer_tool_id = await create_transfer_call_tool(transfer_number)
    search_tool_id   = await create_search_knowledge_base_tool(agency_id)

    # Agency র জন্য System Prompt বানাও
    system_prompt = f"""
    You are an AI voice assistant for {agency_name}.
    Business Type: {business_type}
    
    {custom_prompt}
    
    Rules:
    - Be polite and professional always
    - Speak in Bengali if customer speaks Bengali
    - Speak in English if customer speaks English
    - IMPORTANT: Use the searchKnowledgeBase tool to find plan details, policy info, or premiums.
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
            "maxTokens": 500,
            "toolIds": [
                book_tool_id,
                transfer_tool_id,
                search_tool_id
            ]
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "21m00Tcm4TlvDq8ikWAM",
            #"credentialId": config.VAPI_ELEVENLABS_CREDENTIAL_ID
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en",
            #"credentialId": config.VAPI_DEEPGRAM_CREDENTIAL_ID
        },
        "firstMessage": welcome_message,
        "firstMessageMode": "assistant-speaks-first",
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
        return assistant_id, book_tool_id, transfer_tool_id
    else:
        print(f"❌ Assistant creation failed | Error: {response.text}")
        return None, None, None


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
    twilio_number: str,
    vapi_phone_number_id : str = None  # ← নতুন parameter
):
    """
    কাজ  : Lead কে Vapi দিয়ে outbound call দেয়
    নেয়  : lead_phone, lead_id, agency_id, assistant_id, twilio_number
    দেয়  : call_id (Vapi থেকে)
    করে  : Vapi API তে POST request করে call শুরু করে
    """
    # Agency র নিজের number, না থাকলে system default
    phone_number_id = vapi_phone_number_id or config.VAPI_PHONE_NUMBER_ID

    call_config = {
        "assistantId": assistant_id,
        "phoneNumberId": phone_number_id,
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
    
# ============================================
# IMPORT TWILIO NUMBER TO VAPI
# কাজ : Agency র Twilio number Vapi তে import করে
# কে call করে : agencies.py (provision এ)
# ============================================
async def import_twilio_number(
    twilio_sid   : str,
    twilio_token : str,
    twilio_number: str,
    business_name: str
) -> str:
    """
    কাজ  : Twilio number Vapi তে import করে
    নেয়  : twilio_sid, twilio_token, twilio_number, business_name
    দেয়  : vapi_phone_number_id
    কখন : POST /agencies/ provision এ automatically call হয়

    Flow:
    Twilio credentials → Vapi API → vapi_phone_number_id পায়
    """

    import_config = {
        "provider"          : "twilio",
        "twilioAccountSid"  : twilio_sid,
        "twilioAuthToken"   : twilio_token,
        "number"            : twilio_number,
        "name"              : f"{business_name}_number"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.VAPI_BASE_URL}/phone-number",
                json   = import_config,
                headers= get_vapi_headers(),
                timeout= 30
            )

        if response.status_code == 201:
            data                 = response.json()
            vapi_phone_number_id = data.get("id")
            print(f"✅ Twilio imported to Vapi | Number: {twilio_number} | ID: {vapi_phone_number_id}")
            return vapi_phone_number_id
        else:
            print(f"❌ Twilio import failed | Error: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Twilio import error | {str(e)}")
        return None
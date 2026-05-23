"""
ফাইলের নাম  : webhooks.py
ফাইলের কাজ  : Vapi থেকে আসা সব call event receive করে process করে
               Inbound + Outbound দুইটাই handle করে
কে call করে : Vapi (automatically)
সংযুক্ত     : db_service.py, ghl_service.py, rag_service.py
"""

from fastapi import APIRouter, Request
#from app.services import db_service, ghl_service, rag_service
from app.services import db_service, rag_service,django_service
from app.workers import call_worker
from app.routers.agencies import AGENCY_STORE

router = APIRouter()


# ============================================
# MAIN WEBHOOK ENDPOINT
# URL : POST /webhooks/vapi
# কে call করে : Vapi Dashboard এ এই URL set করা আছে
# ============================================
@router.post("/vapi")
async def vapi_webhook(request: Request):
    """
    কাজ  : Vapi এর সব call event receive করে সঠিক handler এ পাঠায়
    """
    try:
        payload = await request.json()
        # ডিবাগিং এর জন্য পুরো ডাটা প্রিন্ট করি
        print(f"\n📥 Full Payload Received: {payload}")
    except:
        return {"status": "error", "message": "Invalid JSON"}

    message    = payload.get("message", {})
    # ... (বাকি কোড আগের মতোই থাকবে)
    event_type = message.get("type")
    call       = message.get("call", {})
    call_type  = call.get("type")

    # অপ্রয়োজনীয় ইভেন্টগুলো ইগনোর করি যাতে লগ পরিষ্কার থাকে
    ignored_events = ["status-update", "speech-update", "conversation-update", "assistant.started"]
    if event_type in ignored_events:
        return {"status": "ignored"}

    print(f"\n🔔 Webhook | Event: {event_type} | Type: {call_type} | Call ID: {call.get('id')}")

    # ============================================
    # ১. ASSISTANT REQUEST (Dynamic Config & RAG)
    # ============================================
    if event_type == "assistant-request":
        return await handle_assistant_request(message)

    # ============================================
    # ২. TOOL CALLS (Booking, Transfer, etc.)
    # ============================================
    elif event_type == "tool-calls":
        from app.routers import tools
        return await tools.handle_tool_calls(message)

    # ============================================
    # ৩. CALL STARTED
    # ============================================
    elif event_type == "call-start":
        if call_type in ["inboundPhoneCall", "webCall"]:
            return await handle_inbound_started(call)
        elif call_type == "outboundPhoneCall":
            return await handle_outbound_started(call)

    # ============================================
    # ৪. CALL ENDED
    # ============================================
    elif event_type == "end-of-call-report":
        if call_type in ["inboundPhoneCall", "webCall"]:
            return await handle_inbound_ended(message)
        elif call_type == "outboundPhoneCall":
            return await handle_outbound_ended(message)

    # ============================================
    # ৫. OTHER EVENTS
    # ============================================
    else:
        print(f"ℹ️ Info: Handled event {event_type}")
        return {"status": "success"}
    
# ============================================
# HANDLE ASSISTANT REQUEST
# কাজ : Inbound call এ Dynamic System Prompt দেয়
# কখন: Call শুরুর আগে Vapi এই event পাঠায়
# ============================================
async def handle_assistant_request(message: dict):
    """
    কাজ  : Call শুরুর আগে Dynamic Assistant config return করে
    """
    message = message or {}
    call    = message.get("call") or {}
    
    # ফোন নম্বরটি সরাসরি message অবজেক্টে থাকে (Full Payload থেকে দেখা গেছে)
    phone_obj       = message.get("phoneNumber") or {}
    called_number   = phone_obj.get("number", "")
    call_id         = call.get("id")
    
    print(f"\n🔔 Assistant Request | Call: {call_id} | To: {called_number}")

    # ১. AGENCY_STORE থেকে phone number দিয়ে business খোঁজো
    business_id = None
    agency      = {}
    for bid, data in AGENCY_STORE.items():
        if data.get("twilio_number") == called_number:
            business_id = bid
            agency      = data
            break
    
    # ২. Fallback (যদি নম্বর না পাওয়া যায়)
    if not business_id:
        metadata  = call.get("metadata") or {}
        business_id = metadata.get("business_id", "default")

    agency_id   = business_id
    print(f"🏢 Identified Agency: {business_id}")

    # ৩. এজেন্সি তথ্য এবং RAG কনটেক্সট নিয়ে আসো
    try:
        rag_context = await rag_service.build_context(
            agency_id = business_id,
            query     = "insurance plans and policy coverage"
        )
    except:
        
        rag_context = ""

    # ৪. ডাইনামিক সিস্টেম প্রম্পট
    agency_name = agency.get("name", "Insurance Agency")
    base_prompt = agency.get("custom_prompt", "You are a helpful insurance assistant.")
    
    system_prompt = f"""
You are an AI voice assistant for {agency_name}.
{base_prompt}

=== KNOWLEDGE BASE ===
{rag_context if rag_context else "Please assist based on general insurance knowledge."}
=== END KNOWLEDGE BASE ===

Rules:
- STRICTLY SPEAK IN ENGLISH ONLY. Do not use any other language like Bengali.
- Use the searchKnowledgeBase tool to find details about plans/premiums.
- If you can't find info, offer to transfer to a human agent.
- Be concise and professional.
    """

    # Vapi কে রেসপন্স দাও
    return {
        "assistant": {
            "model": {
                "provider": "openai",
                "model"   : "gpt-4o",
                "messages": [{"role": "system", "content": system_prompt}],
                "temperature": 0.7,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "searchKnowledgeBase",
                            "description": "Search for specific information in the company knowledge base (insurance plans, premiums, policy details).",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "The search query based on customer question."},
                                    "agency_id": {"type": "integer", "default": agency_id}
                                },
                                "required": ["query"]
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "bookAppointment",
                            "description": "Book a meeting or appointment with an agent.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "customer_name": {"type": "string"},
                                    "datetime": {"type": "string", "description": "ISO format date and time."},
                                    "lead_id": {"type": "string", "default": "1"}
                                }
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "transferCall",
                            "description": "Transfer the call to a human agent.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "agency_id": {"type": "integer", "default": agency_id}
                                }
                            }
                        }
                    }
                ]
            },
            "voice": {
                "provider": "11labs",
                "voiceId" : "paul"
            },
            "transcriber": {
                "provider": "deepgram",
                "model" : "nova-2",
                "language": "en"
            },
            "firstMessage": f"Hello! Welcome to {agency_name}. How can I help you today?"
        }
    }


# ============================================
# INBOUND CALL STARTED
# কাজ : Customer call করলে record তৈরি করে
# কখন: Call connect হওয়ার সাথে সাথে
# ============================================
async def handle_inbound_started(call: dict):
    """
    কাজ  : Inbound call শুরুর record তৈরি করে
    নেয়  : call object (Vapi থেকে)
    """
    if not call:
        return {"status": "error", "message": "No call data"}

    call_id         = call.get("id")
    customer_number = call.get("customer", {}).get("number")
    agency_id       = call.get("metadata", {}).get("agency_id", 1)

    print(f"📲 Inbound Started | Call: {call_id} | From: {customer_number}")

    # DB তে call record save করো
    await db_service.save_call({
        "call_id"    : call_id,
        "agency_id"  : agency_id,
        "lead_id"    : None,
        "status"     : "in_progress",
        "call_type"  : "inbound",
        "customer_number": customer_number
    })

    return {"status": "success"}


# ============================================
# INBOUND CALL ENDED
# কাজ : Inbound call শেষে সব data save করে
# কখন: Call disconnect হলে
# ============================================
async def handle_inbound_ended(message: dict):
    """
    কাজ  : Inbound call এর সব data save করে
    নেয়  : full message (transcript, duration সহ)
    """
    call      = message.get("call") or {} # call যদি None হয় তবে খালি dict নিবে
    call_id   = call.get("id")
    metadata  = call.get("metadata") or {}
    agency_id = metadata.get("agency_id", 1)
    
    transcript = message.get("transcript", "")
    duration   = message.get("durationSeconds", 0)
    summary    = message.get("summary", "")

    print(f"📴 Inbound Ended | Call: {call_id} | Duration: {duration}s")

    if not call_id:
        return {"status": "error", "message": "No call ID"}

    # DB তে call update করো
    await db_service.update_call(call_id, {
        "status"          : "ended",
        "transcript"      : transcript,
        "duration_seconds": duration,
        "call_type"       : "inbound"
    })

    return {"status": "success"}


# ============================================
# OUTBOUND CALL STARTED
# কাজ : AI কাউকে call দিলে record তৈরি করে
# কখন: Lead এর phone এ call connect হলে
# ============================================
async def handle_outbound_started(call: dict):
    """
    কাজ  : Outbound call শুরুর record তৈরি করে
    নেয়  : call object (Vapi থেকে)
    দেয়  : success message
    করে  : DB তে call record save করে
    """

    call_id         = call.get("id")
    customer_number = call.get("customer", {}).get("number")
    agency_id       = call.get("metadata", {}).get("agency_id", 1)
    lead_id         = call.get("metadata", {}).get("lead_id")

    print(f"📤 Outbound Started | Call: {call_id} | To: {customer_number}")

    # DB তে call record save করো
    await db_service.save_call({
        "call_id"        : call_id,
        "agency_id"      : agency_id,
        "lead_id"        : lead_id,
        "status"         : "in_progress",
        "call_type"      : "outbound",
        "customer_number": customer_number
    })
   
    if lead_id:
        await db_service.update_lead(lead_id,{
            "status": "calling"
        })

    return {"status": "success", "type": "outbound_started"}


# ============================================
# OUTBOUND CALL ENDED
# কাজ : Outbound call শেষে সব data save করে
# কখন: Call disconnect হলে
# ============================================

async def handle_outbound_ended(message: dict):
    """
    কাজ  : Outbound call এর সব data Django তে পাঠায়
    করে  : django_service.send_call_log() → Django handle করবে
    """
    call        = message.get("call", {})
    call_id     = call.get("id")
    metadata    = call.get("metadata", {})
    business_id = metadata.get("business_id", "")
    lead_id     = metadata.get("lead_id")
    transcript  = message.get("transcript", "")
    duration    = message.get("durationSeconds", 0)
    summary     = message.get("summary", "")
    recording   = message.get("recordingUrl", "")

    # Active call count কমাও
    await call_worker.decrement_active_calls(business_id)

    # Intent detect করো
    intent = detect_intent(message)

    print(f"📴 Outbound Ended | Call: {call_id} | Duration: {duration}s | Intent: {intent}")

    # Duration format
    minutes            = int(duration) // 60
    seconds            = int(duration) % 60
    duration_formatted = f"{minutes:02d}:{seconds:02d}"

    # ✅ Django তে call log পাঠাও
    if business_id and lead_id:
        await django_service.send_call_log(
            business_id  = business_id,
            call_log_data= {
                "lead_id"     : lead_id,
                "lead_status" : "done",
                "name"        : metadata.get("lead_name", "Customer"),
                "phone_number": call.get("customer", {}).get("number", ""),
                "duration"    : duration_formatted,
                "status"      : intent.capitalize(),
                "summary"     : summary,
                "transcript"  : transcript,
                "audio_url"   : recording
            }
        )

    return {
        "status": "success",
        "type"  : "outbound_ended",
        "intent": intent
    }

# ============================================
# HELPER — INTENT DETECT
# কাজ : Call এর message থেকে intent বের করে
# ============================================
def detect_intent(message: dict) -> str:
    """
    কাজ  : Call এর data থেকে customer এর intent বোঝে
    নেয়  : message object
    দেয়  : intent string

    Intent হতে পারে:
    → interested      (আগ্রহী)
    → not_interested  (আগ্রহী না)
    → busy            (ব্যস্ত)
    → talk_to_agent   (agent এর সাথে কথা বলতে চায়)
    → no_answer       (call ধরেনি)
    → voicemail       (voicemail এ গেছে)
    """

    # Vapi এর end reason check করো
    end_reason = message.get("endedReason", "")

    if end_reason == "customer-did-not-answer":
        return "no_answer"

    if end_reason == "voicemail":
        return "voicemail"

    # Transcript থেকে intent বোঝো
    transcript = message.get("transcript", "").lower()

    if any(word in transcript for word in [
        "interested", "yes", "আগ্রহী", "হ্যাঁ", "নেব", "want"
    ]):
        return "interested"

    if any(word in transcript for word in [
        "busy", "ব্যস্ত", "later", "পরে", "call back"
    ]):
        return "busy"

    if any(word in transcript for word in [
        "not interested", "আগ্রহী না", "no", "না", "don't want"
    ]):
        return "not_interested"

    if any(word in transcript for word in [
        "agent", "human", "person", "এজেন্ট", "মানুষ"
    ]):
        return "talk_to_agent"

    return "unknown"


# ============================================
# HELPER — INTENT TO LEAD STATUS
# কাজ : Intent কে Lead Status এ convert করে
# ============================================
def intent_to_lead_status(intent: str) -> str:
    """
    কাজ  : Intent string কে Lead DB status এ convert করে
    নেয়  : intent
    দেয়  : lead status

    Mapping:
    interested    → qualified
    busy          → follow_up
    not_interested→ not_interested
    talk_to_agent → transferred
    no_answer     → no_answer
    voicemail     → voicemail
    """

    mapping = {
        "interested"    : "qualified",
        "busy"          : "follow_up",
        "not_interested": "not_interested",
        "talk_to_agent" : "transferred",
        "no_answer"     : "no_answer",
        "voicemail"     : "voicemail",
        "unknown"       : "called"
    }

    return mapping.get(intent, "called")


# ============================================
# TEST ENDPOINT
# ============================================
@router.get("/test")
async def webhooks_test():
    return {"router": "webhooks", "status": "ready"}
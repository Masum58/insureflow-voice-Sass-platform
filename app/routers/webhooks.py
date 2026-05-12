"""
ফাইলের নাম  : webhooks.py
ফাইলের কাজ  : Vapi থেকে আসা সব call event receive করে process করে
               Inbound + Outbound দুইটাই handle করে
কে call করে : Vapi (automatically)
সংযুক্ত     : db_service.py, ghl_service.py, rag_service.py
"""

from fastapi import APIRouter, Request
from app.services import db_service, ghl_service, rag_service
from app.workers import call_worker

router = APIRouter()


# ============================================
# MAIN WEBHOOK ENDPOINT
# URL : POST /webhooks/vapi
# কে call করে : Vapi Dashboard এ এই URL set করা আছে
# ============================================
@router.post("/vapi")
async def vapi_webhook(request: Request):
    """
    কাজ  : Vapi এর সব call event receive করে
    নেয়  : Vapi থেকে JSON payload
    দেয়  : Success/Error response
    করে  : Event type দেখে সঠিক handler এ পাঠায়
    """

    try:
        payload = await request.json()
    except:
        payload = {}

    message    = payload.get("message", {})
    event_type = message.get("type")
    call       = message.get("call", {})
    call_type  = call.get("type")

    print(f"\n📞 Webhook | Event: {event_type} | Type: {call_type}")

    # ============================================
    # CALL STARTED
    # ============================================
    if event_type == "call-start":
        if call_type == "inboundPhoneCall":
            return await handle_inbound_started(call)
        elif call_type == "outboundPhoneCall":
            return await handle_outbound_started(call)
        elif call_type =="webCall":
            return await handle_inbound_started(call)

    # ============================================
    # CALL ENDED
    # ============================================
    elif event_type == "end-of-call-report":
        if call_type == "inboundPhoneCall":
            return await handle_inbound_ended(message)
        elif call_type == "outboundPhoneCall":
            return await handle_outbound_ended(message)
        elif call_type == "webCall":
            return await handle_inbound_ended(message)

    # ============================================
    # UNKNOWN EVENT
    # ============================================
    else:
        print(f"⚠️ Unknown event: {event_type}")
        return {"status": "ignored"}
    
# ============================================
# HANDLE ASSISTANT REQUEST
# কাজ : Inbound call এ Dynamic System Prompt দেয়
#        RAG থেকে context inject করে
# কখন: Call শুরুর আগে Vapi এই event পাঠায়
# ============================================
async def handle_assistant_request(message: dict):
    """
    কাজ  : Call শুরুর আগে Dynamic Assistant config return করে
    নেয়  : message object
    দেয়  : assistant config (RAG context সহ)
    করে  :
    1. Phone number থেকে agency_id বের করে
    2. ChromaDB থেকে context build করে
    3. Dynamic system prompt তৈরি করে
    4. Vapi কে assistant config দেয়
    """

    call          = message.get("call", {})
    call_id       = call.get("id")
    called_number = call.get("phoneNumber", {}).get("number", "")
    agency_id     = call.get("metadata", {}).get("agency_id", 1)

    print(f"\n🤖 Assistant Request | Call: {call_id} | Agency: {agency_id}")

    # Agency info নিয়ে আসো
    agency = await db_service.get_agency(agency_id)

    # RAG Context বানাও
    # Default query দিয়ে শুরু করি
    # Call চলাকালীন আরো specific হবে
    rag_context = await rag_service.build_context(
        agency_id = agency_id,
        query     = "insurance information premium coverage"
    )

    # Dynamic System Prompt বানাও
    agency_name   = agency.get("name", "Insurance Agency")
    business_type = agency.get("business_type", "insurance")
    base_prompt   = agency.get("custom_prompt", "")

    system_prompt = f"""
You are an AI voice assistant for {agency_name}.
Business Type: {business_type}

{base_prompt}

=== KNOWLEDGE BASE ===
{rag_context}
=== END KNOWLEDGE BASE ===

Rules:
- Always use the knowledge base above to answer questions
- Be polite and professional
- Speak in Bengali if customer speaks Bengali
- Speak in English if customer speaks English
- If customer wants to book appointment → use bookAppointment tool
- If customer wants human agent → use transfer_call_tool
- Never make up information not in the knowledge base
    """

    print(f"✅ Assistant Request | Context: {len(rag_context)} chars | Agency: {agency_name}")

    # Vapi কে Dynamic Assistant Config দাও
    return {
        "assistant": {
            "model": {
                "provider": "openai",
                "model"   : "gpt-4o",
                "messages": [
                    {
                        "role"   : "system",
                        "content": system_prompt
                    }
                ]
            },
            "voice": {
                "provider": "11labs",
                "voiceId" : "charlie"
            },
            "transcriber": {
                "provider": "deepgram",
                "model"   : "nova-2",
                "language": "en"
            },
            "firstMessage": agency.get(
                "welcome_message",
                f"Hello! I'm {agency_name} AI. How can I help you?"
            )
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
    দেয়  : success message
    করে  : DB তে call record save করে
    """

    call_id         = call.get("id")
    customer_number = call.get("customer", {}).get("number")
    phone_number    = call.get("phoneNumber", {}).get("number")
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

    # GHL তে নতুন contact তৈরি করো
    await ghl_service.create_contact(
        name     = "Inbound Customer",
        phone    = customer_number or "",
        agency_id= agency_id
    )

    return {"status": "success", "type": "inbound_started"}


# ============================================
# INBOUND CALL ENDED
# কাজ : Inbound call শেষে সব data save করে
# কখন: Call disconnect হলে
# ============================================
async def handle_inbound_ended(message: dict):
    """
    কাজ  : Inbound call এর সব data save করে
    নেয়  : full message (transcript, duration সহ)
    দেয়  : success message
    করে  : DB update + GHL note add
    """

    call      = message.get("call", {})
    call_id   = call.get("id")
    agency_id = call.get("metadata", {}).get("agency_id", 1)
    transcript= message.get("transcript", "")
    duration  = message.get("durationSeconds", 0)
    summary   = message.get("summary", "")

    # Customer number নাও
    customer_number = call.get("customer", {}).get("number", "")
    ghl_contact_id  = call.get("metadata", {}).get("ghl_contact_id", "")

    print(f"📴 Inbound Ended | Call: {call_id} | Duration: {duration}s")

    # DB তে call update করো
    await db_service.update_call(call_id, {
        "status"          : "ended",
        "transcript"      : transcript,
        "duration_seconds": duration,
        "call_type"       : "inbound"
    })

    # GHL তে call note add করো
    if ghl_contact_id:
        await ghl_service.add_call_note(
            ghl_contact_id  = ghl_contact_id,
            call_summary    = summary or transcript[:500],
            duration_seconds= duration,
            intent          = "inbound_completed"
        )

    return {"status": "success", "type": "inbound_ended"}


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

    # Lead status → "called" update করো
    if lead_id:
        await db_service.update_lead(lead_id, {
            "status": "called"
        })

    return {"status": "success", "type": "outbound_started"}


# ============================================
# OUTBOUND CALL ENDED
# কাজ : Outbound call শেষে সব data save করে
# কখন: Call disconnect হলে
# ============================================
async def handle_outbound_ended(message: dict):
    """
    কাজ  : Outbound call এর সব data save করে
    নেয়  : full message (intent, transcript, duration সহ)
    দেয়  : success message
    করে  : DB update + Lead status update + GHL sync
    """

    call       = message.get("call", {})
    call_id    = call.get("id")
    agency_id  = call.get("metadata", {}).get("agency_id", 1)
    lead_id    = call.get("metadata", {}).get("lead_id")
    transcript = message.get("transcript", "")
    duration   = message.get("durationSeconds", 0)
    summary    = message.get("summary", "")

    # Active call count কমাও
    await call_worker.decrement_active_calls(agency_id)
    # Intent detect করো
    intent = detect_intent(message)

    print(f"📴 Outbound Ended | Call: {call_id} | Duration: {duration}s | Intent: {intent}")

    # DB তে call update করো
    await db_service.update_call(call_id, {
        "status"          : "ended",
        "intent"          : intent,
        "transcript"      : transcript,
        "duration_seconds": duration,
        "call_type"       : "outbound"
    })

    # Lead status update করো
    if lead_id:
        lead_status = intent_to_lead_status(intent)
        await db_service.update_lead(lead_id, {
            "status": lead_status
        })

    # GHL CRM update করো
    ghl_contact_id = call.get("metadata", {}).get("ghl_contact_id", "")
    if ghl_contact_id:
        await ghl_service.update_contact_status(
            ghl_contact_id= ghl_contact_id,
            intent        = intent,
            agency_id     = agency_id
        )
        await ghl_service.add_call_note(
            ghl_contact_id  = ghl_contact_id,
            call_summary    = summary or transcript[:500],
            duration_seconds= duration,
            intent          = intent
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
"""
ফাইলের নাম  : call_worker.py
ফাইলের কাজ  : Redis Queue থেকে leads নিয়ে
               একটা একটা করে Vapi দিয়ে call দেয়
               
               Flow:
               Redis Queue → Lead নাও → Vapi Call → Status Update
               
কে use করে  : campaigns.py (campaign start হলে)
সংযুক্ত     : vapi_service.py, db_service.py, redis
"""

import json
import asyncio
import redis.asyncio as aioredis
from app.services import vapi_service
from app.services import django_service
from app.routers.agencies import AGENCY_STORE
from app import config


# ============================================
# REDIS CONNECTION
# কাজ : Async Redis connection তৈরি করে
# ============================================
async def get_redis():
    """
    কাজ  : Async Redis client return করে
    দেয়  : Redis connection object
    """
    return await aioredis.from_url(
        config.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )


# ============================================
# MAIN WORKER FUNCTION
# কাজ : Campaign এর সব leads কে call দেয়
# কে call করে : campaigns.py (campaign start এ)
# ============================================
async def run_campaign_worker(agency_id: int):
    """
    কাজ  : Redis Queue থেকে leads নিয়ে call দেয়
    নেয়  : agency_id
    করে  :
    1. Redis Queue থেকে lead নেয়
    2. Vapi দিয়ে call দেয়
    3. Status update করে
    4. Queue empty হলে campaign complete করে
    """

    redis = await get_redis()
    queue_key  = f"campaign:{agency_id}:queue"
    status_key = f"campaign:{agency_id}:status"

    print(f"\n🚀 Worker Started | Agency: {agency_id}")

    # ============================================
    # Campaign চলতে থাকবে যতক্ষণ Queue তে leads আছে
    # ============================================
    while True:

        # Queue তে কতটা leads আছে?
        queue_size = await redis.llen(queue_key)

        if queue_size == 0:
            print(f"✅ Queue empty | Campaign complete | Agency: {agency_id}")
            await update_campaign_status(redis, status_key, "completed")
            break

        # ============================================
        # Queue থেকে একটা Lead নাও (Left Pop)
        # ============================================
        lead_json = await redis.lpop(queue_key)

        if not lead_json:
            break

        lead_data = json.loads(lead_json)

        lead_id      = lead_data.get("lead_id")
        phone        = lead_data.get("phone")
        name         = lead_data.get("name")
        assistant_id = lead_data.get("assistant_id")
        twilio_number= lead_data.get("twilio_number")
        vapi_phone_number_id= lead_data.get("vapi_phone_number_id")  # ← এটা add করো

        print(f"\n📞 Calling | Lead: {lead_id} | Name: {name} | Phone: {phone}")

        # ============================================
        # Concurrent Call Limit Check করো
        # একসাথে max 5টা call হবে
        # ============================================
        active_calls = await get_active_calls_count(redis, agency_id)

        if active_calls >= 5:
            print(f"⏳ Max calls reached ({active_calls}/5) | Waiting...")
            # Lead টা আবার Queue তে দাও
            await redis.rpush(queue_key, lead_json)
            await asyncio.sleep(10)
            continue

        # ============================================
        # Vapi দিয়ে Call দাও
        # ============================================
        call_id = await vapi_service.start_outbound_call(
            lead_phone   = phone,
            lead_id      = lead_id,
            agency_id    = agency_id,
            assistant_id = assistant_id,
            twilio_number= twilio_number,
            vapi_phone_number_id = vapi_phone_number_id  # ← এটা add করো
        )

        if call_id:
            print(f"✅ Call started | Call ID: {call_id} | Lead: {name}")

            # Active calls count বাড়াও
            await increment_active_calls(redis, agency_id)

            # Campaign status update করো
            await increment_called_count(redis, status_key)

        else:
            print(f"❌ Call failed | Lead: {lead_id} | {name}")
            # Django service দিয়ে log করবো
            # business_id লাগবে তাই এখন শুধু log করি
            print(f"⚠️ Lead {lead_id} call failed — will retry next campaign")
        # প্রতিটা call এর মধ্যে 2 second wait করো
        # Vapi rate limit avoid করতে
        await asyncio.sleep(2)

    print(f"🏁 Worker Finished | Agency: {agency_id}")
    await redis.close()


# ============================================
# ACTIVE CALLS MANAGEMENT
# কাজ : একসাথে কতটা call চলছে track করে
# ============================================
async def get_active_calls_count(redis, agency_id: int) -> int:
    """
    কাজ  : Agency র active call count দেয়
    নেয়  : redis, agency_id
    দেয়  : active call count (int)
    """
    count = await redis.get(f"campaign:{agency_id}:active_calls")
    return int(count) if count else 0


async def increment_active_calls(redis, agency_id: int):
    """
    কাজ  : Active call count বাড়ায়
    কখন : Call শুরু হলে
    """
    await redis.incr(f"campaign:{agency_id}:active_calls")
    # 5 minute পর automatically expire করবে
    await redis.expire(f"campaign:{agency_id}:active_calls", 300)


async def decrement_active_calls(agency_id: int):
    """
    কাজ  : Active call count কমায়
    কখন : Call শেষ হলে (webhooks.py call করবে)
    """
    redis = await get_redis()
    current = await redis.get(f"campaign:{agency_id}:active_calls")
    if current and int(current) > 0:
        await redis.decr(f"campaign:{agency_id}:active_calls")
    await redis.close()


# ============================================
# CAMPAIGN STATUS UPDATE
# কাজ : Campaign এর progress update করে
# ============================================
async def update_campaign_status(redis, status_key: str, status: str):
    """
    কাজ  : Campaign status update করে
    নেয়  : redis, status_key, new status
    কখন : Campaign complete বা stop হলে
    """
    existing = await redis.get(status_key)
    if existing:
        data = json.loads(existing)
        data["status"] = status
        await redis.set(status_key, json.dumps(data))
    print(f"📊 Campaign status: {status}")


async def increment_called_count(redis, status_key: str):
    """
    কাজ  : Called leads count বাড়ায়
    কখন : প্রতিটা call শুরু হলে
    """
    existing = await redis.get(status_key)
    if existing:
        data = json.loads(existing)
        data["called"] = data.get("called", 0) + 1
        await redis.set(status_key, json.dumps(data))

# ============================================
# ফাইলটি সরাসরি রান করে টেস্ট করার জন্য
# ============================================
if __name__ == "__main__":
    async def test_worker():
        print("🚀 Starting Call Worker manually for Agency 102...")
        
        # আপনার টেস্ট এজেন্সির আইডি (যেমন 102) দিয়ে ওয়ার্কার চালু করুন
        await run_campaign_worker(agency_id=102)

    # স্ক্রিপ্টটি রান করার জন্য
    asyncio.run(test_worker())
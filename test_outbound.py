import requests
import time

BASE_URL = "http://127.0.0.1:8000"

print("🚀 Testing Outbound Campaign...")

# Step 1: Setup Agency (Creates Vapi Assistant)
print("\n[1] Setting up Agency Assistant...")
setup_data = {
    "agency_id": 102,
    "agency_name": "ABC Insurance",
    "business_type": "Health Insurance",
    "transfer_number": "+8801322158015"
}

try:
    res = requests.post(f"{BASE_URL}/campaigns/setup-agency", json=setup_data)
    if res.status_code == 200:
        print("✅ Agency Setup Success:", res.json())
    else:
        print("❌ Agency Setup Failed:", res.text)
        exit()
except Exception as e:
    print("❌ Failed to connect to local server. Make sure Uvicorn is running!")
    exit()

time.sleep(2)

# Step 2: Start Campaign (Pulls lead & places call)
print("\n[2] Starting Campaign (Calling your number)...")
start_data = {
    "agency_id": 102,
    "campaign_name": "Test Outbound"
}

res = requests.post(f"{BASE_URL}/campaigns/start", json=start_data)
if res.status_code == 200:
    print("✅ Campaign Started Successfully:", res.json())
    print("\n📞 Please wait... You should receive a call on your phone (+8801335117990) shortly!")
else:
    print("❌ Campaign Start Failed:", res.text)

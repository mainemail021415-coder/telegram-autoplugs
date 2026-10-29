from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "online", "message": "Peony SMM Interactive Login Backend is running!"}

# Temporary storage para sa active client sessions habang naghihintay ng OTP
active_clients = {}

class SendCodeRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str

@app.post("/api/send-code")
async def send_code(data: SendCodeRequest):
    try:
        client = TelegramClient(StringSession(), data.api_id, data.api_hash)
        await client.connect()
        
        # Mag-request ng sign in code mula sa Telegram
        result = await client.send_code_request(data.phone)
        session_string = client.session.save()
        
        # I-save muna pansamantala gamit ang phone bilang key
        active_clients[data.phone] = {
            "session": session_string,
            "api_id": data.api_id,
            "api_hash": data.api_hash,
            "phone_code_hash": result.phone_code_hash
        }
        
        await client.disconnect()
        return {"status": "code_sent", "message": "Naipadala na ang Telegram login code sa iyong Telegram app!"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class VerifyAndStartRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    code: str
    message: str
    groups: list[str]

@app.post("/api/verify-code")
async def verify_code(data: VerifyAndStartRequest):
    client_data = active_clients.get(data.phone)
    if not client_data:
        raise HTTPException(status_code=400, detail="Mag-request muna ng code bago mag-verify.")

    try:
        client = TelegramClient(StringSession(client_data["session"]), data.api_id, data.api_hash)
        await client.connect()
        
        # I-sign in ang user gamit ang code na inilagay nila
        await client.sign_in(data.phone, data.code, phone_code_hash=client_data["phone_code_hash"])
        
        success_logs = []
        for group in data.groups:
            clean_group = group.strip()
            if not clean_group:
                continue
            try:
                await client.send_message(clean_group, data.message)
                success_logs.append(f"Successfully sent via account to {clean_group}")
                await asyncio.sleep(15)  # 15 seconds anti-flood delay
            except Exception as ex:
                success_logs.append(f"Failed {clean_group}: {str(ex)}")

        await client.disconnect()
        
        # Linisin ang temporary storage pagkatapos magamit
        if data.phone in active_clients:
            del active_clients[data.phone]

        return {"status": "success", "logs": success_logs, "message": "Matagumpay na nakakonekta at naisagawa ang autoplug!"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

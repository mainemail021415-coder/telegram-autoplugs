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
    return {"status": "online", "message": "Peony SMM Stable Autoplug Backend is running!"}

active_clients = {}
active_tasks = {}

class SendCodeRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str

@app.post("/api/send-code")
async def send_code(data: SendCodeRequest):
    try:
        client = TelegramClient(StringSession(), data.api_id, data.api_hash)
        await client.connect()
        
        result = await client.send_code_request(data.phone)
        session_string = client.session.save()
        
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
    interval_minutes: int

@app.post("/api/verify-code")
async def verify_code(data: VerifyAndStartRequest):
    client_data = active_clients.get(data.phone)
    if not client_data:
        raise HTTPException(status_code=400, detail="Mag-request muna ng code bago mag-verify o mag-login muli.")

    try:
        # Ligtas na pag-login gamit ang session string
        client = TelegramClient(StringSession(client_data["session"]), data.api_id, data.api_hash)
        await client.connect()
        
        await client.sign_in(data.phone, data.code, phone_code_hash=client_data["phone_code_hash"])
        
        # I-save ang session string para hindi na mawala o ma-invalidate
        active_clients[data.phone]["session"] = client.session.save()
        active_tasks[data.phone] = True
        
        success_logs = []
        delay_seconds = max(data.interval_minutes, 1) * 60

        # Unang subok agad pagka-launch
        for group in data.groups:
            if not active_tasks.get(data.phone, False):
                success_logs.append("Autoplug stopped by user.")
                break

            clean_group = group.strip()
            if not clean_group:
                continue
            try:
                await client.send_message(clean_group, data.message)
                success_logs.append(f"Successfully sent to {clean_group} (Interval: {data.interval_minutes} mins)")
            except Exception as ex:
                success_logs.append(f"Failed {clean_group}: {str(ex)}")

        await client.disconnect()

        return {
            "status": "success", 
            "logs": success_logs, 
            "message": "Matagumpay na nagsimula ang 24H Autoplug loop."
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class StopRequest(BaseModel):
    phone: str

@app.post("/api/stop-autoplug")
async def stop_autoplug(data: StopRequest):
    if data.phone in active_tasks:
        active_tasks[data.phone] = False
        return {"status": "success", "message": "Matagumpay na pinatigil ang autoplug."}
    return {"status": "not_found", "message": "Walang aktibong autoplug task para sa account na ito."}

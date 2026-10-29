from fastapi import FastAPI, HTTPException, BackgroundTasks
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
    return {"status": "online", "message": "Peony SMM Stable Auto-Delete Backend is running!"}

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

# Background loop para sa 24 hours autoplug kasama ang 10-minute auto-delete
async def run_autoplug_loop(phone: str, session_str: str, api_id: int, api_hash: str, message: str, groups: list[str], interval_minutes: int):
    active_tasks[phone] = True
    delay_seconds = max(interval_minutes, 1) * 60

    try:
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        await client.connect()

        while active_tasks.get(phone, False):
            for group in groups:
                if not active_tasks.get(phone, False):
                    break
                
                clean_group = group.strip()
                if not clean_group:
                    continue
                
                sent_msg = None
                try:
                    # 1. Ipadala ang mensahe sa target group
                    sent_msg = await client.send_message(clean_group, message)
                    print(f"Successfully sent to {clean_group}")
                except Exception as ex:
                    print(f"Failed to send {clean_group}: {str(ex)}")
                
                # 2. Maghintay ng 10 minuto (600 seconds) para sa auto-delete
                if sent_msg:
                    for _ in range(600):
                        if not active_tasks.get(phone, False):
                            break
                        await asyncio.sleep(1)
                    
                    if active_tasks.get(phone, False):
                        try:
                            # Direktang burahin ang mensahe gamit ang message ID at group entity
                            await client.delete_messages(clean_group, [sent_msg.id])
                            print(f"Successfully deleted message in {clean_group}")
                        except Exception as del_ex:
                            print(f"Failed to delete in {clean_group}: {str(del_ex)}")

                # Maikling pahinga bago lumipat sa kasunod na grupo
                await asyncio.sleep(5)

            # 3. Maghintay ngayon ng itinakdang interval minutes ng user bago ang susunod na ikot
            for _ in range(delay_seconds):
                if not active_tasks.get(phone, False):
                    break
                await asyncio.sleep(1)

        await client.disconnect()
    except Exception as e:
        print(f"Loop Error for {phone}: {str(e)}")
    finally:
        if phone in active_tasks:
            del active_tasks[phone]

@app.post("/api/verify-code")
async def verify_code(data: VerifyAndStartRequest, background_tasks: BackgroundTasks):
    client_data = active_clients.get(data.phone)
    if not client_data:
        raise HTTPException(status_code=400, detail="Mag-request muna ng code bago mag-verify.")

    try:
        client = TelegramClient(StringSession(client_data["session"]), data.api_id, data.api_hash)
        await client.connect()
        
        await client.sign_in(data.phone, data.code, phone_code_hash=client_data["phone_code_hash"])
        session_str = client.session.save()
        await client.disconnect()

        # Itigil ang lumang task kung meron man bago simulan ang bago
        active_tasks[data.phone] = False
        await asyncio.sleep(1)

        # Patakbuhin sa background ang tuloy-tuloy na loop
        background_tasks.add_task(
            run_autoplug_loop,
            data.phone,
            session_str,
            data.api_id,
            data.api_hash,
            data.message,
            data.groups,
            data.interval_minutes
        )

        return {
            "status": "success", 
            "logs": [
                f"Nagsimula na ang 24H Autoplug loop.",
                f"Interval set to {data.interval_minutes} minutes.",
                "10-minute Auto-Delete feature is active."
            ], 
            "message": "Matagumpay na naisagawa ang autoplug!"
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

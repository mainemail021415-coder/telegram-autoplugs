from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from telethon import TelegramClient

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Idagdag ito para kapag binuksan sa browser, may sumalubong na mensahe sa halip na "Not Found"
@app.get("/")
async def root():
    return {"status": "online", "message": "Peony SMM Telegram Autoplug Backend is running successfully!"}

class AutoplugRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    message: str
    groups: list[str]

@app.post("/api/start-autoplug")
async def start_autoplug(data: AutoplugRequest):
    print(f"--- NATANGGAP ANG REQUEST MULA SA WEBSITE ---")
    print(f"API ID: {data.api_id}")
    print(f"Target Groups: {data.groups}")
    print(f"Message: {data.message}")
    
    try:
        # Patatakbuhin ang Telethon automation sa background
        asyncio.create_task(run_real_telegram_plugs(data.api_id, data.api_hash, data.message, data.groups))
        return {"status": "success", "message": "Autoplug successfully triggered on Render backend server!"}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_real_telegram_plugs(api_id, api_hash, message, groups):
    client = TelegramClient(f'session_{api_id}', api_id, api_hash)
    try:
        print("Kumokonekta sa Telegram MTProto servers...")
        await client.connect()
        
        for group in groups:
            print(f"Nagpapadala ng mensahe sa {group}...")
            await client.send_message(group, message)
            await asyncio.sleep(20) # Anti-flood delay
            
    except Exception as e:
        print(f"Telegram Error: {e}")
    finally:
        await client.disconnect()
        print("Telegram client disconnected safely.")

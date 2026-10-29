from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from telethon import TelegramClient

app = FastAPI()

# I-allow ang CORS para makapag-connect ang frontend website mo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AutoplugRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    message: str
    groups: list[str]

@app.post("/api/start-autoplug")
async def start_autoplug(data: AutoplugRequest):
    # Dito natin pwedeng patakbuhin ang Telethon session ng client
    # Tandaan: Para sa mga web-based clients, mas mainam na gumamit ng temporary session
    try:
        # Halimbawa ng Telethon background worker initiation
        asyncio.create_task(run_telegram_plugs(data.api_id, data.api_hash, data.message, data.groups))
        return {"status": "success", "message": "Autoplug started successfully on backend!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_telegram_plugs(api_id, api_hash, message, groups):
    # Pansamantalang client connection para sa automation loop
    # Note: Kailangan muna nila ma-authenticate ang session (Phone login / string session)
    client = TelegramClient('session_client', api_id, api_hash)
    await client.connect()
    
    try:
        for group in groups:
            # MESSAGE DELAY SAFETY (15-25 seconds para iwas FloodWait)
            await client.send_message(group, message)
            await asyncio.sleep(20) # Average ng 15-25 seconds delay
    finally:
        await client.disconnect()
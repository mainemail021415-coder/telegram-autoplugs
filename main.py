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

class AutoplugRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    message: str
    groups: list[str]

@app.post("/api/start-autoplug")
async def start_autoplug(data: AutoplugRequest):
    try:
        # I-trigger ang background task para mag-send ng real messages sa Telegram
        asyncio.create_task(run_real_telegram_plugs(data.api_id, data.api_hash, data.message, data.groups))
        return {"status": "success", "message": "Real Telethon autoplug started successfully on backend!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_real_telegram_plugs(api_id, api_hash, message, groups):
    # Gamitin ang dynamic session para sa bawat kliyente
    client = TelegramClient(f'session_{api_id}', api_id, api_hash)
    await client.connect()
    
    try:
        for group in groups:
            # Tunay na pagpapadala ng mensahe sa Telegram groups
            await client.send_message(group, message)
            # Anti-flood safety delay (15-25 seconds)
            await asyncio.sleep(20)
    except Exception as e:
        print(f"Error sending message: {e}")
    finally:
        await client.disconnect()

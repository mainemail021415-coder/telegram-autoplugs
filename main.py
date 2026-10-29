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
    print(f"--- NAGSIMULA ANG AUTOPLUG --- Groups: {data.groups}")
    try:
        # Patatakbuhin natin ang Telethon at ibabalik ang resulta
        success_logs = []
        client = TelegramClient(f'session_{data.api_id}', data.api_id, data.api_hash)
        await client.connect()
        
        for group in data.groups:
            try:
                await client.send_message(group.strip(), data.message)
                success_logs.append(f"Successfully sent message to {group.strip()}")
                await asyncio.sleep(15) # Safe anti-flood interval
            except Exception as ex:
                success_logs.append(f"Failed to send to {group.strip()}: {str(ex)}")
                
        await client.disconnect()
        return {"status": "success", "logs": success_logs, "message": "Kumpleto na ang pagpapadala sa mga target groups!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

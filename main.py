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
    return {"status": "online", "message": "Peony SMM Telethon User-Client Backend is running!"}

class UserAutoplugRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    message: str
    groups: list[str]

@app.post("/api/start-autoplug")
async def start_autoplug(data: UserAutoplugRequest):
    success_logs = []
    
    try:
        # Gumagamit tayo ng temporary session para sa user client
        client = TelegramClient(StringSession(), data.api_id, data.api_hash)
        await client.connect()
        
        # Suriin kung authorized ang session
        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(
                status_code=400, 
                detail="Hindi authorized ang API ID/Hash o kailangan ng interactive login. Subukang gamitin ang iyong personal session."
            )

        for group in data.groups:
            clean_group = group.strip()
            if not clean_group:
                continue
            try:
                # Nagpapadala ang personal account ng user sa target group/channel
                await client.send_message(clean_group, data.message)
                success_logs.append(f"Successfully sent via account to {clean_group}")
                
                # 15 seconds anti-flood safety interval
                await asyncio.sleep(15)
            except Exception as ex:
                success_logs.append(f"Failed {clean_group}: {str(ex)}")

        await client.disconnect()
        return {"status": "success", "logs": success_logs, "message": "Kumpleto na ang pagpapalabas ng plug gamit ang iyong Telegram account!"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from telethon import TelegramClient

app = FastAPI()

# I-allow ang CORS para makapag-connect ang GitHub Pages website mo
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
        # Patatakbuhin ang automation sa background habang nagpapadala ng instant response sa frontend
        asyncio.create_task(run_real_telegram_plugs(data.api_id, data.api_hash, data.message, data.groups))
        return {"status": "success", "message": "Autoplug successfully triggered on Render backend server!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_real_telegram_plugs(api_id, api_hash, message, groups):
    # Pagbuo ng Telegram client gamit ang credentials ng kliyente
    client = TelegramClient(f'session_{api_id}', api_id, api_hash)
    await client.connect()
    
    try:
        for group in groups:
            # Tunay na pagpapadala ng mensahe sa Telegram group
            await client.send_message(group, message)
            # Anti-flood delay: 20 seconds (pasok sa 15-25s safe interval)
            await asyncio.sleep(20)
    except Exception as e:
        print(f"Error during plugging: {e}")
    finally:
        await client.disconnect()

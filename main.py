from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import httpx

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
    return {"status": "online", "message": "Peony SMM Telegram Bot Backend is running successfully!"}

class BotAutoplugRequest(BaseModel):
    bot_token: str
    message: str
    groups: list[str]

@app.post("/api/start-autoplug")
async def start_autoplug(data: BotAutoplugRequest):
    print(f"--- NATANGGAP ANG BOT REQUEST --- Groups: {data.groups}")
    success_logs = []
    url = f"https://api.telegram.org/bot{data.bot_token}/sendMessage"
    
    try:
        async with httpx.AsyncClient() as client:
            for group in data.groups:
                clean_group = group.strip()
                if not clean_group:
                    continue
                try:
                    payload = {
                        "chat_id": clean_group,
                        "text": data.message
                    }
                    response = await client.post(url, json=payload, timeout=10.0)
                    res_data = response.json()
                    
                    if res_data.get("ok"):
                        success_logs.append(f"Successfully sent to {clean_group}")
                    else:
                        err_desc = res_data.get("description", "Unknown error")
                        success_logs.append(f"Failed {clean_group}: {err_desc}")
                    
                    # Anti-flood delay (15 seconds)
                    await asyncio.sleep(15)
                except Exception as ex:
                    success_logs.append(f"Error {clean_group}: {str(ex)}")

        return {"status": "success", "logs": success_logs, "message": "Kumpleto na ang pagpapadala ng bot sa mga target groups!"}
    
    except Exception as e:
        print(f"Server Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

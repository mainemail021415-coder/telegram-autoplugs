import os
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

# Kunin ang mga default credentials at permanent string session mula sa environment variables ng Render
DEFAULT_API_ID = int(os.getenv("API_ID", 39718460))
DEFAULT_API_HASH = os.getenv("API_HASH", "5443837869bbc53e4455f3fba89f0bb3")
DEFAULT_STRING_SESSION = os.getenv("STRING_SESSION", "")

active_tasks = {}
live_logs_storage = {}

@app.get("/")
async def root():
    return {"status": "online", "message": "Peony SMM Live Logs Autoplug Backend is running securely with StringSession!"}

class StartAutoplugRequest(BaseModel):
    phone: str
    message: str
    groups: list[str]
    interval_minutes: int
    api_id: int = DEFAULT_API_ID
    api_hash: str = DEFAULT_API_HASH

async def run_autoplug_loop(phone: str, session_str: str, api_id: int, api_hash: str, message: str, groups: list[str], interval_minutes: int):
    active_tasks[phone] = True
    
    if phone not in live_logs_storage:
        live_logs_storage[phone] = []

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    end_time = datetime.now() + timedelta(hours=24)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            live_logs_storage[phone].append("Error: Hindi awtorisado ang STRING_SESSION. Paki-suri ang environment variable sa Render.")
            active_tasks[phone] = False
            return

        cycle_count = 1

        while active_tasks.get(phone, False):
            if datetime.now() >= end_time:
                live_logs_storage[phone].append("Tapos na ang 24-hour limit. Kusang pinatigil ang Autoplug.")
                break

            live_logs_storage[phone].append(f"--- Nagsimula na ang Ikot #{cycle_count} ---")
            
            for index, group in enumerate(groups):
                if not active_tasks.get(phone, False):
                    break
                
                clean_group = group.strip()
                if not clean_group:
                    continue
                
                try:
                    if not client.is_connected():
                        await client.connect()
                except Exception:
                    await asyncio.sleep(2)
                    try:
                        await client.connect()
                    except:
                        pass

                sent_msg = None
                try:
                    sent_msg = await client.send_message(clean_group, message)
                    current_time = datetime.now().strftime("%I:%M:%S %p")
                    log_text = f"Successfully sent to {clean_group} (Ikot #{cycle_count}) - {current_time}"
                    live_logs_storage[phone].append(log_text)
                except Exception as ex:
                    current_time = datetime.now().strftime("%I:%M:%S %p")
                    err_str = str(ex)
                    log_text = f"Failed {clean_group}: {err_str} - {current_time}"
                    live_logs_storage[phone].append(log_text)
                    
                    if "AuthKeyUnregistered" in err_str or "Session" in err_str or "Authorization" in err_str:
                        live_logs_storage[phone].append("Na-invalidate ang session. Suriin ang STRING_SESSION.")
                        active_tasks[phone] = False
                        break
                
                if sent_msg:
                    async def delete_after_10mins(target_group, msg_id):
                        for _ in range(60):
                            if not active_tasks.get(phone, False):
                                break
                            await asyncio.sleep(10)
                        if active_tasks.get(phone, False):
                            try:
                                if client.is_connected():
                                    await client.delete_messages(target_group, [msg_id])
                                    del_time = datetime.now().strftime("%I:%M:%S %p")
                                    live_logs_storage[phone].append(f"Auto-deleted message in {target_group} - {del_time}")
                            except:
                                pass
                    
                    asyncio.create_task(delete_after_10mins(clean_group, sent_msg.id))

                if index < len(groups) - 1:
                    live_logs_storage[phone].append(f"Naghihintay ng 1 minuto bago ang susunod na grupo...")
                    for _ in range(60):
                        if not active_tasks.get(phone, False):
                            break
                        await asyncio.sleep(1)

            if not active_tasks.get(phone, False):
                break

            delay_seconds = max(interval_minutes, 35) * 60
            live_logs_storage[phone].append(f"Tapos na ang Ikot #{cycle_count}. Naghihintay ng {interval_minutes} mins para sa susunod na ikot...")
            
            sleep_remaining = delay_seconds
            while sleep_remaining > 0 and active_tasks.get(phone, False):
                chunk = min(10, sleep_remaining)
                await asyncio.sleep(chunk)
                sleep_remaining -= chunk

            cycle_count += 1

    except Exception as e:
        live_logs_storage[phone].append(f"Loop Error: {str(e)}")
    finally:
        try:
            if client.is_connected():
                await client.disconnect()
        except:
            pass
        if phone in active_tasks:
            del active_tasks[phone]
        live_logs_storage[phone].append("--- Autoplug ay ganap nang tumigil ---")

@app.post("/api/start-autoplug")
async def start_autoplug(data: StartAutoplugRequest, background_tasks: BackgroundTasks):
    session_str = DEFAULT_STRING_SESSION
    if not session_str:
        raise HTTPException(status_code=400, detail="Walang nakitang STRING_SESSION sa Render environment variables.")

    active_tasks[data.phone] = False
    await asyncio.sleep(1)
    
    live_logs_storage[data.phone] = [f"Nagsimula na ang 24H Autoplug loop gamit ang StringSession (Interval: {data.interval_minutes} mins)."]

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

    return {"status": "success", "message": "Nagsimula na ang autoplug nang diretso gamit ang permanent session!"}

class LogsRequest(BaseModel):
    phone: str

@app.post("/api/get-logs")
async def get_logs(data: LogsRequest):
    logs = live_logs_storage.get(data.phone, [])
    return {"status": "success", "logs": logs}

class StopRequest(BaseModel):
    phone: str

@app.post("/api/stop-autoplug")
async def stop_autoplug(data: StopRequest):
    if data.phone in active_tasks:
        active_tasks[data.phone] = False
        return {"status": "success", "message": "Matagumpay na pinatigil ang autoplug."}
    return {"status": "not_found", "message": "Walang aktibong task."}

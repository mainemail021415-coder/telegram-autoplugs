import os
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_API_ID = int(os.getenv("API_ID", 39718460))
DEFAULT_API_HASH = os.getenv("API_HASH", "5443837869bbc53e4455f3fba89f0bb3")

VALID_KEYCODES = {"021415", "2001415"}

active_tasks = {}
live_logs_storage = {}

@app.get("/")
async def root():
    return {"status": "online", "message": "Peony SMM Dynamic StringSession Autoplug Backend is running!"}

class StartAutoplugRequest(BaseModel):
    keycode: str
    string_session: str
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
            live_logs_storage[phone].append("Error: Hindi awtorisado o mali ang ibinigay na String Session.")
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
                    await asyncio.sleep(3)
                    try:
                        await client.connect()
                    except:
                        pass

                sent_msg = None
                try:
                    sent_msg = await client.send_message(clean_group, message)
                    current_time = datetime.now().strftime("%I:%M:%S %p")
                    live_logs_storage[phone].append(f"Successfully sent to {clean_group} (Ikot #{cycle_count}) - {current_time}")
                except FloodWaitError as e:
                    current_time = datetime.now().strftime("%I:%M:%S %p")
                    live_logs_storage[phone].append(f"FloodWait: Kailangan maghintay ng {e.seconds} segundo sa {clean_group} - {current_time}")
                    await asyncio.sleep(e.seconds)
                    try:
                        sent_msg = await client.send_message(clean_group, message)
                        live_logs_storage[phone].append(f"Successfully sent to {clean_group} pagkatapos mag-antay (Ikot #{cycle_count})")
                    except Exception as ex2:
                        live_logs_storage[phone].append(f"Failed pa rin sa {clean_group}: {str(ex2)}")
                except Exception as ex:
                    current_time = datetime.now().strftime("%I:%M:%S %p")
                    err_str = str(ex)
                    live_logs_storage[phone].append(f"Failed {clean_group}: {err_str} - {current_time}")
                    
                    if "AuthKeyUnregistered" in err_str or "Session" in err_str or "Authorization" in err_str:
                        live_logs_storage[phone].append("Na-invalidate ang session.")
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
                                if not client.is_connected():
                                    await client.connect()
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
        live_logs_storage[phone].append(f"Loop Crash Error: {str(e)}")
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
    if data.keycode not in VALID_KEYCODES:
        raise HTTPException(status_code=400, detail="Invalid o expired na ang Client Keycode!")

    if not data.string_session.strip():
        raise HTTPException(status_code=400, detail="Kailangan mong ilagay ang iyong Telegram String Session!")

    active_tasks[data.phone] = False
    await asyncio.sleep(1)
    
    live_logs_storage[data.phone] = [f"Nagsimula na ang 24H Autoplug gamit ang client-provided StringSession (Interval: {data.interval_minutes} mins)."]

    background_tasks.add_task(
        run_autoplug_loop,
        data.phone,
        data.string_session,
        data.api_id,
        data.api_hash,
        data.message,
        data.groups,
        data.interval_minutes
    )

    return {"status": "success", "message": "Matagumpay na na-verify ang Keycode at Session! Nagsimula na ang autoplug."}

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

# --- ADMIN ENDPOINTS ---

@app.get("/api/admin/active-tasks")
async def get_active_tasks(admin_key: str):
    if admin_key not in VALID_KEYCODES:
        raise HTTPException(status_code=403, detail="Unauthorized Admin Key!")
    
    tasks_info = []
    for phone, is_active in active_tasks.items():
        if is_active:
            tasks_info.append({"phone": phone})
            
    return {"status": "success", "active_users": tasks_info}

class AdminStopRequest(BaseModel):
    admin_key: str
    phone: str

@app.post("/api/admin/stop-user")
async def admin_stop_user(data: AdminStopRequest):
    if data.admin_key not in VALID_KEYCODES:
        raise HTTPException(status_code=403, detail="Unauthorized Admin Key!")
        
    if data.phone in active_tasks:
        active_tasks[data.phone] = False
        return {"status": "success", "message": f"Matagumpay na pinatigil ang plug ng numerong {data.phone}"}
    
    return {"status": "not_found", "message": "Walang nakitang aktibong task para sa numerong ito."}

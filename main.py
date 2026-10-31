from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from datetime import datetime, timedelta
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
    return {"status": "online", "message": "Peony SMM Live Logs Autoplug Backend is running!"}

active_clients = {}
active_tasks = {}
live_logs_storage = {}

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

async def run_autoplug_loop(phone: str, session_str: str, api_id: int, api_hash: str, message: str, groups: list[str], interval_minutes: int):
    active_tasks[phone] = True
    
    if phone not in live_logs_storage:
        live_logs_storage[phone] = []

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    end_time = datetime.now() + timedelta(hours=24)

    try:
        await client.connect()
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
                
                # Seguraduhing active ang koneksyon bago mag-send
                try:
                    if not client.is_connected():
                        await client.connect()
                except Exception as conn_ex:
                    live_logs_storage[phone].append(f"Reconnecting warning: {str(conn_ex)}")
                    await asyncio.sleep(3)
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
                    
                    # Kung sakaling nasira ang session, i-stop ang loop para hindi magpatuloy ang error
                    if "AuthKeyUnregistered" in err_str or "Session" in err_str:
                        live_logs_storage[phone].append("Na-invalidate ang session. Kailangan mag-login muli.")
                        active_tasks[phone] = False
                        break
                
                # 10 minutes auto-delete task
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

                # 1 minute delay bago ang susunod na grupo
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
            await client.disconnect()
        except:
            pass
        if phone in active_tasks:
            del active_tasks[phone]
        live_logs_storage[phone].append("--- Autoplug ay ganap nang tumigil ---")

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

        active_tasks[data.phone] = False
        await asyncio.sleep(1)
        
        live_logs_storage[data.phone] = [f"Nagsimula na ang 24H Autoplug loop (Interval: {data.interval_minutes} mins)."]

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

        return {"status": "success", "message": "Nagsimula na ang autoplug!"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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

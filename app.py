from flask import Flask, request, jsonify
from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio

app = Flask(__name__)

# Ang iyong Main API ID at API Hash
API_ID = 31448878
API_HASH = '2db42e4cb269229bfaeb9eca5a0f3ba6'

@app.route('/api/autoplug', methods=['POST'])
def handle_autoplug():
    data = request.json
    
    # Kunin ang mga datos na ipinadala mula sa web form ni client
    session_string = data.get('session_string')
    phone = data.get('phone')
    message = data.get('message')
    groups_raw = data.get('groups', '')
    
    if not session_string or not message or not groups_raw:
        return jsonify({"success": False, "message": "May mga kulang na impormasyon sa form."}), 400

    # Hatiin ang mga grupo kada linya
    groups_list = [g.strip() for g in groups_raw.split('\n') if g.strip()]

    # Patakbuhin ang Telethon client nang asynchronous
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_complete_task = loop.run_until_complete(
            send_messages_to_groups(session_string, message, groups_list)
        )
        return jsonify({"success": True, "message": "Matagumpay na naisalang ang mga mensahe sa mga grupo!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Nagka-error: str({e})"}), 500

async def send_messages_to_groups(session_string, message, groups_list):
    client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        await client.disconnect()
        raise Exception("Mali o expired ang session string na ibinigay.")

    success_count = 0
    for group in groups_list:
        try:
            await client.send_message(group, message)
            success_count += 1
            # Mag-aabang ng konti para iwas FloodWait
            await asyncio.sleep(2) 
        except Exception as e:
            print(f"Hindi naipadala sa {group}: {e}")
            
    await client.disconnect()
    return success_count

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

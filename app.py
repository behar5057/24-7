import os
import logging
from flask import Flask, request, jsonify
import requests
from collections import defaultdict, deque

# Initialize Flask app
app = Flask(__name__)

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8080306073:AAHy6IO4j_uResEEN_H2K-PJ2TkPws79mH8")
ADMIN_ID = os.environ.get('ADMIN_ID', "6120264201")

# Telegram API URL
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Data structures for managing chats
active_connections = {}
waiting_queue = deque()
user_states = defaultdict(lambda: 'idle')

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# App version (for deployment tracking)
APP_VERSION = "1.0.0"
GIT_COMMIT = os.environ.get('GIT_COMMIT', 'local')

def send_telegram_message(chat_id, text, parse_mode=None):
    """Send message to Telegram user"""
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    if parse_mode:
        payload['parse_mode'] = parse_mode
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False

def send_message_with_keyboard(chat_id, text, buttons):
    """Send message with inline keyboard"""
    url = f"{TELEGRAM_API}/sendMessage"
    keyboard = []
    
    for button_row in buttons:
        row = []
        for button_text, callback_data in button_row:
            row.append({"text": button_text, "callback_data": callback_data})
        keyboard.append(row)
    
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown',
        'reply_markup': {'inline_keyboard': keyboard}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending message with keyboard: {e}")
        return False

def answer_callback_query(callback_query_id, text=None):
    """Answer callback query"""
    url = f"{TELEGRAM_API}/answerCallbackQuery"
    payload = {'callback_query_id': callback_query_id}
    if text:
        payload['text'] = text
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Error answering callback: {e}")

def edit_message_text(chat_id, message_id, text):
    """Edit existing message"""
    url = f"{TELEGRAM_API}/editMessageText"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        return False

def try_match_users():
    """Try to match users from the waiting queue"""
    if len(waiting_queue) >= 2:
        user1 = waiting_queue.popleft()
        user2 = waiting_queue.popleft()
        
        active_connections[user1] = user2
        active_connections[user2] = user1
        user_states[user1] = 'chatting'
        user_states[user2] = 'chatting'
        
        # Notify both users
        success1 = send_telegram_message(
            user1, 
            "✅ *Connected with a new partner!*\n\nStart chatting! Use /stop to end the conversation.\nRemember: Be respectful and have fun! 🎉",
            "Markdown"
        )
        
        success2 = send_telegram_message(
            user2, 
            "✅ *Connected with a new partner!*\n\nStart chatting! Use /stop to end the conversation.\nRemember: Be respectful and have fun! 🎉",
            "Markdown"
        )
        
        if not success1 or not success2:
            # Clean up failed connection
            if user1 in active_connections:
                del active_connections[user1]
            if user2 in active_connections:
                del active_connections[user2]
            user_states[user1] = 'idle'
            user_states[user2] = 'idle'

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    """Main webhook handler"""
    try:
        data = request.get_json()
        logger.info(f"Received update from Telegram")
        
        # Handle message
        if 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            # Handle commands
            if text.startswith('/'):
                if text == '/start':
                    handle_start(chat_id)
                elif text == '/chat':
                    handle_chat(chat_id)
                elif text == '/stop':
                    handle_stop(chat_id)
                elif text == '/status':
                    handle_status(chat_id)
                else:
                    send_telegram_message(chat_id, "Unknown command. Use /start to see available commands.")
            else:
                # Handle regular message
                handle_message(chat_id, text)
        
        # Handle callback queries (button presses)
        elif 'callback_query' in data:
            callback_query = data['callback_query']
            chat_id = callback_query['message']['chat']['id']
            data = callback_query['data']
            message_id = callback_query['message']['message_id']
            
            if data == 'start_chat':
                handle_chat(chat_id, message_id)
            elif data == 'help':
                handle_help(chat_id, message_id)
            
            # Answer callback query
            answer_callback_query(callback_query['id'])
        
        return jsonify(success=True)
    
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return jsonify(success=False, error=str(e)), 500

def handle_start(chat_id):
    """Handle /start command"""
    if user_states[chat_id] == 'chatting':
        send_telegram_message(chat_id, "You are already in a chat! Use /stop to end the current conversation.")
        return
    
    if chat_id in waiting_queue:
        waiting_queue.remove(chat_id)
    
    user_states[chat_id] = 'idle'
    
    buttons = [
        [("Start Random Chat", "start_chat")],
        [("Help", "help")]
    ]
    
    welcome_text = f"""
👋 Welcome to *Chattelo*! (v{APP_VERSION})

I'm your random chat bot that connects you with strangers for anonymous conversations.

*Available Commands:*
/start - Show this welcome message
/chat - Start looking for a chat partner
/stop - End current conversation
/status - Check bot status

*How it works:*
1. Use /chat or click 'Start Random Chat'
2. Wait for me to find you a partner
3. Start chatting anonymously!
4. Use /stop when you want to end the chat

Remember to be respectful and follow community guidelines! 🚫
    """
    
    send_message_with_keyboard(chat_id, welcome_text, buttons)

def handle_chat(chat_id, message_id=None):
    """Handle /chat command"""
    if user_states[chat_id] == 'chatting':
        if message_id:
            edit_message_text(chat_id, message_id, "You are already in a chat! Use /stop to end it first.")
        else:
            send_telegram_message(chat_id, "You are already in a chat! Use /stop to end it first.")
        return
    
    if user_states[chat_id] == 'waiting':
        if message_id:
            edit_message_text(chat_id, message_id, "You are already in the waiting queue. Please be patient!")
        else:
            send_telegram_message(chat_id, "You are already in the waiting queue. Please be patient!")
        return
    
    waiting_queue.append(chat_id)
    user_states[chat_id] = 'waiting'
    
    if message_id:
        edit_message_text(chat_id, message_id, "🔍 Searching for a chat partner... Please wait!\n\nYou can cancel anytime using /stop")
    else:
        send_telegram_message(chat_id, "🔍 Searching for a chat partner... Please wait!\n\nYou can cancel anytime using /stop")
    
    try_match_users()

def handle_stop(chat_id):
    """Handle /stop command"""
    if user_states[chat_id] == 'chatting':
        partner_id = active_connections.get(chat_id)
        if partner_id:
            send_telegram_message(partner_id, "❌ Your chat partner has ended the conversation.\n\nUse /chat to find a new partner!")
            
            if chat_id in active_connections:
                del active_connections[chat_id]
            if partner_id in active_connections:
                del active_connections[partner_id]
        
        send_telegram_message(chat_id, "✅ Chat ended. Use /chat to find a new partner!")
        
    elif user_states[chat_id] == 'waiting':
        if chat_id in waiting_queue:
            waiting_queue.remove(chat_id)
        send_telegram_message(chat_id, "✅ Removed from waiting queue.")
    
    else:
        send_telegram_message(chat_id, "You're not in a chat or waiting queue.")
    
    user_states[chat_id] = 'idle'

def handle_message(chat_id, text):
    """Handle regular messages"""
    if user_states[chat_id] != 'chatting':
        send_telegram_message(chat_id, "You're not in a chat! Use /chat to find a partner first.")
        return
    
    partner_id = active_connections.get(chat_id)
    if not partner_id:
        send_telegram_message(chat_id, "Partner not found. Use /chat to find a new partner.")
        user_states[chat_id] = 'idle'
        return
    
    # Forward message to partner
    success = send_telegram_message(partner_id, f"*Partner:* {text}", "Markdown")
    
    if not success:
        send_telegram_message(chat_id, "❌ Failed to send message. Your partner may have left the chat.\nUse /chat to find a new partner.")
        if chat_id in active_connections:
            del active_connections[chat_id]
        user_states[chat_id] = 'idle'

def handle_help(chat_id, message_id):
    """Handle help button"""
    help_text = """
*Chattelo Help Guide*

*Commands:*
/start - Show welcome message
/chat - Start looking for a partner  
/stop - End current chat or leave queue
/status - Check bot status

*How to use:*
1. Click 'Start Random Chat' or type /chat
2. Wait for a partner to connect
3. Chat anonymously
4. Use /stop when done

*Rules:*
- Be respectful to others
- No spam or harassment
- No sharing personal information
- Have fun! 🎉

*GitHub:* https://github.com/yourusername/chattelo-bot
    """
    edit_message_text(chat_id, message_id, help_text)

def handle_status(chat_id):
    """Handle /status command"""
    status_text = f"""
🤖 *Chattelo Bot Status*

*Version:* {APP_VERSION}
*Commit:* {GIT_COMMIT[:8]}
*Active Chats:* {len(active_connections) // 2}
*Waiting Users:* {len(waiting_queue)}
*Total Users:* {len(user_states)}

*Server:* PythonAnywhere
*Status:* ✅ Operational

Use /chat to start a conversation!
    """
    send_telegram_message(chat_id, status_text, "Markdown")

@app.route('/')
def index():
    """Health check route"""
    return jsonify({
        "status": "Chattelo Bot is running!",
        "version": APP_VERSION,
        "commit": GIT_COMMIT,
        "active_chats": len(active_connections) // 2,
        "waiting_users": len(waiting_queue),
        "total_users": len(user_states),
        "github_repo": "https://github.com/yourusername/chattelo-bot"
    })

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Set webhook URL"""
    webhook_url = f"https://perfctex.pythonanywhere.com/{BOT_TOKEN}"
    set_webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(set_webhook_url, timeout=10)
        success = response.status_code == 200
        
        return jsonify({
            "success": success,
            "webhook_url": webhook_url,
            "message": "Webhook set successfully" if success else "Failed to set webhook",
            "version": APP_VERSION
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete_webhook', methods=['GET'])
def delete_webhook():
    """Delete webhook"""
    try:
        response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", timeout=10)
        success = response.status_code == 200
        
        return jsonify({
            "success": success,
            "message": "Webhook deleted successfully" if success else "Failed to delete webhook"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/github-webhook', methods=['POST'])
def github_webhook():
    """GitHub webhook for deployment notifications"""
    if request.headers.get('X-GitHub-Event') == 'push':
        logger.info("Received GitHub push notification")
        # Could trigger auto-deployment here
        return jsonify({"message": "GitHub webhook received"})
    return jsonify({"message": "Not a push event"})

if __name__ == '__main__':
    # This won't run on PythonAnywhere, only locally
    app.run(debug=True)

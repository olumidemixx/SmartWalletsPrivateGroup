import os
import time
from datetime import datetime
from dotenv import find_dotenv, load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telethon import TelegramClient
import re
from collections import defaultdict
import logging
import asyncio
import sys
from contextlib import suppress
from httpx import Timeout
import logging
import nest_asyncio
from flask import Flask
#from threading import Thread
from telegram import Update
from flask import request
#from keep_alive import keep_alive
nest_asyncio.apply()
#PORT = 8443  # Render will provide the PORT environment variable
# Telegram bot configuration
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
# Telethon client configuration
BOT_TOKEN = "7931001355:AAFtun7fy35zwg5z_1T_ugoln1f5zdM5Sa0"#"7327291802:AAFPM911VQH5uyTX2uPG8j503NCt3r62yMs"#3os.getenv("BOT_TOKEN")
API_ID = 21202746#int(os.getenv("API_ID"))
API_HASH = "e700432294937e6925a83149ee7165a0"#os.getenv("API_HASH")
# Create Telethon client
telethon_client = TelegramClient('llb', API_ID, API_HASH)

# Excluded token address
EXCLUDED_TOKEN = 'So11111111111111111111111111111112'

# Authorized users allowed to command the bot in THETRACKOORS group
AUTHORIZED_USERS = {'orehub1378', 'Kemoo1975', 'jeremi1234', 'Busiiiiii'}
# The THETRACKOORS group identifier
THETRACKOORS_CHAT_ID = -1002241230605  # Replace with actual chat ID for THETRACKOORS

# Global variable to indicate if THETRACKOORS is being monitored
is_tracking_thetrackoors = False

class MonitoringSession:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.is_monitoring = False
        self.multi_trader_tokens = {}
        self.previous_messages = []
        self.monitoring_task = None
        self.token_pump_types = {}
        self.token_market_caps = {}
        self.token_sol_amounts = {}
        self.token_timestamps = {}
        self.start_time = None
        self.round_start_time = None


async def initialize_telethon():
    #global telethon_client
    #telethon_client = TelegramClient('piped', API_ID, API_HASH)
    await telethon_client.start()
    #logging.info("Telethon client initialized and started")

async def check_authorization(update):
    """Check if the chat is the THETRACKOORS group"""
    # Check if the chat is THETRACKOORS
    return update.effective_chat.id == THETRACKOORS_CHAT_ID

def extract_market_cap(text):
    """Extract market cap value and unit from the message"""
    mc_pattern = r'(?:(?:MC|MCP):\s*\$?\s*([\d.]+)\s*([KkMm])?|\$?\s*([\d.]+)\s*([KkMm])?\s*(?=(?:MC|MCP)))'
    match = re.search(mc_pattern, text, re.IGNORECASE)

    if match:
        value = match.group(1) or match.group(3)
        unit = match.group(2) or match.group(4)
        value = float(value)
        if unit:
           unit = unit.upper()
        else:
            unit='Null'
        return {'value': value, 'unit': unit}
        
        #try:
         #   value = float(value)
            # Standardize unit to uppercase
          #  if unit:
           #     unit = unit.upper()
            #else:
             #   unit = 'K'  # Default to K if no unit specified
            #return {'value': value, 'unit': unit}
        #except ValueError:
         
        
        #   return None
    return ("NULL")

def extract_sol_amount(text):
    """Extract the last number before 'SOL' in the text"""
    try:
        sol_pos = text.find('SOL')
        if sol_pos == -1:
            #logging.debug("No 'SOL' found in text")
            return None

        text_before_sol = text[:sol_pos]
        numbers = re.findall(r'[-+]?\d*\.\d+|\d+', text_before_sol)

        if numbers:
            try:
                return float(numbers[-1])
            except ValueError as e:
                #logging.debug(f"Could not convert number to float: {e}")
                return None
        logging.debug("No numbers found before 'SOL'")
        return None
    except Exception as e:
        logging.error(f"Error in extract_sol_amount: {e}")
        return None

def has_pump_keywords(text):
    """Check if the message contains any pump-related keywords with case sensitivity for PUMP"""
    pump_match = any(pump_word in text for pump_word in ['PUMP', 'Pump'])
    other_keywords = any(keyword in text.lower() for keyword in ['pumpfun', 'raydium'])
    None_of_them = 'None'
    return pump_match or other_keywords or None_of_them

async def is_valid_buy_message(text):

    buy_pattern = r'(?:BUY|Buy|buy|Swap|Swapped|Received)'
    sell_pattern = r'(?:SELL|Sell|sell)'

    buy_matches = list(re.finditer(buy_pattern, text))
    sell_matches = list(re.finditer(sell_pattern, text))

    if not sell_matches:
        return bool(buy_matches)

    if buy_matches and sell_matches:
        first_buy_pos = buy_matches[0].start()
        first_sell_pos = sell_matches[0].start()
        return first_buy_pos < first_sell_pos

    return False

def extract_pump_type(text):
    """Extract pump type from the message with case sensitivity for PUMP"""
    # Define a regex pattern to match 'Received: <FLOAT/INTEGER> SOL'
    sol_received_pattern = r'Received:\s*([-+]?\d*\.\d+|\d+)\s*SOL'
    
    # Check for 'Received: <FLOAT/INTEGER> SOL' format
    if re.search(sol_received_pattern, text):
        return None

    """Extract pump type from the message with case sensitivity for PUMP"""
    if 'pumpfun' in text.lower():
        return 'PUMPFUN'
    elif 'raydium' in text.lower():
        return 'RAYDIUM'
    elif 'PUMP' in text or 'Pump' in text:
        return 'PUMPFUN'
    elif 'JUPITER' in text or 'Jupiter' in text:
        return 'JUPITER'
    elif 'Received:' in text:
        return "NULL"
    return "NONE"

def get_token_address(text, chat_link):
    """Extract token address based on the chat source"""
    try:
        solana_addresses = re.findall(r'[0-9A-HJ-NP-Za-km-z]{32,44}', text)
        if not solana_addresses:
            #logging.info(f"No Solana addresses found in message from {chat_link}")
            return None

        #logging.info(f"Found {len(solana_addresses)} addresses in message from {chat_link}")
        
        # Define index mapping with safety checks
        if 'ray_green_bot' in chat_link:
            return solana_addresses[5] if len(solana_addresses) > 5 else solana_addresses[-1]
        
        if 'handi_cat_bot' in chat_link:
            return solana_addresses[5] if len(solana_addresses) > 5 else solana_addresses[-1]
        
        if 'Wallet_tracker_solana_spybot' in chat_link:
            return solana_addresses[6] if len(solana_addresses) > 6 else solana_addresses[-1]
            
        if 'Godeye_wallet_trackerBot' in chat_link:
            return solana_addresses[2] if len(solana_addresses) > 2 else solana_addresses[-1]
        
        if 'GMGN_alert_bot' in chat_link:
            return solana_addresses[3] if len(solana_addresses) > 3 else solana_addresses[-1]
        
        if 'FireSorcerer_bot' in chat_link:
            return solana_addresses[3] if len(solana_addresses) > 3 else solana_addresses[-1]
        
        if 'Solbix_bot' in chat_link:
            return solana_addresses[4] if len(solana_addresses) > 4 else solana_addresses[-1]
        
        if 'EVMTrackerBot' in chat_link:
            if 'SOL' in text[:47]:
                return solana_addresses[0] if len(solana_addresses) > 0 else solana_addresses[-1]
        
        if 'SOLWalletTrackerBot' in chat_link:
            if 'SOL' in text[:125]:
                return solana_addresses[0] if len(solana_addresses) > 0 else solana_addresses[-1]
            
        if 'EtherDROPS7_bot' in chat_link:
            return solana_addresses[1] if len(solana_addresses) > 1 else solana_addresses[-1]
            
        if 'defined_bot' in chat_link:
            return solana_addresses[3] if len(solana_addresses) > 3 else solana_addresses[-1]
            
        if 'CashCash_alert_bot' in chat_link:
            return solana_addresses[2] if len(solana_addresses) > 2 else solana_addresses[-1]
        
        if 'spark_green_bot' in chat_link:
            return solana_addresses[5] if len(solana_addresses) > 5 else solana_addresses[-1]
        
        # Default case
        return solana_addresses[-1] if solana_addresses else None

    except Exception as e:
        logging.error(f"Error in get_token_address for {chat_link}: {e}")
        logging.error(f"Message text: {text[:100]}...")  # Log first 100 chars of message
        return None

# Add this at the top level of your file
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

async def scrap_message(chat, session, limit=300):
    """Scrape messages and track token purchases"""
    message_count = 0
    #logging.info(f"Starting to scrape messages from {chat} with limit {limit}")
    try:
        message_count = 0
        async for message in telethon_client.iter_messages(chat, limit=limit):
            try:
                message_count += 1
                if message.text:
                    text = message.text
                    if await is_valid_buy_message(text):
                        #logging.info(f"Found valid buy message in {chat}")
                        trader_pattern = r'(?:TRADER|Trader|trader)\d+'
                        trader_match = re.search(trader_pattern, text)

                        token_address = get_token_address(text, chat)
                        
                        if token_address is None:
                            continue

                        if trader_match and token_address != EXCLUDED_TOKEN:
                            trader = trader_match.group()
                            pump_type = extract_pump_type(text)
                            market_cap = extract_market_cap(text)
                            sol_amount = extract_sol_amount(text)
                            timestamp = message.date.timestamp()

                            if token_address not in session.multi_trader_tokens:
                                session.multi_trader_tokens[token_address] = set()
                                session.token_market_caps[token_address] = {}
                                session.token_sol_amounts[token_address] = {}
                                session.token_timestamps[token_address] = {}
                                if pump_type:
                                    session.token_pump_types[token_address] = pump_type

                            session.multi_trader_tokens[token_address].add(trader)
                            if market_cap is not None:
                                session.token_market_caps[token_address][trader] = market_cap
                            if sol_amount is not None:
                                session.token_sol_amounts[token_address][trader] = sol_amount
                            session.token_timestamps[token_address][trader] = timestamp

            except Exception as message_error:
                logging.error(f"Error processing message in {chat}: {message_error}")
                continue

        #logging.info(f"Finished scraping {message_count} messages from {chat}")
    except Exception as e:
        logging.error(f"Error scraping messages from {chat}: {e}")

async def monitor_channels(context, session):
    global is_tracking_thetrackoors
    global chat_limits

    chat_limits = {
        'https://t.me/ray_green_bot': 40,
        #'https://t.me/handi_cat_bot': 40,
        'https://t.me/Wallet_tracker_solana_spybot': 23,
        #'https://t.me/Godeye_wallet_trackerBot': 23,
        'https://t.me/GMGN_alert_bot': 40,
        'https://t.me/FireSorcerer_bot': 23,
        #'https://t.me/Solbix_bot': 8,
        #'https://t.me/Cielo_finance_free_bot': 40,
        #'https://t.me/SOLWalletTrackerBot': 23,
        #'https://t.me/CashCash_alert_bot': 23,
        'https://t.me/spark_green_bot': 40,
        'https://t.me/defined_bot': 40,
        #'https://t.me/EtherDROPS7_bot': 40
    }

    # Initialize previous round data
    previous_tokens = {}  # Format: {token_address: number_of_traders}

    while session.is_monitoring:
        try:
            session.round_start_time = time.time()
            session.multi_trader_tokens.clear()
            session.token_pump_types.clear()
            session.token_market_caps.clear()
            session.token_sol_amounts.clear()
            session.token_timestamps.clear()

            # Scrape messages from all channels
            for chat_link, limit in chat_limits.items():
                await scrap_message(chat_link, session, limit)
                await asyncio.sleep(1.5)
            
            current_messages = []
            current_tokens = {}  # Track current round's tokens and trader counts

            # Process current round's tokens
            for address, traders in session.multi_trader_tokens.items():
                if len(traders) >= 2:
                    current_tokens[address] = len(traders)
                    
                    # Only generate message if token is new or has different number of traders
                    if address not in previous_tokens or previous_tokens[address] != len(traders):
                        sorted_traders = sorted(
                            traders,
                            key=lambda t: (
                                session.token_timestamps[address].get(t, 0),
                                int(''.join(filter(str.isdigit, t)))
                            )
                        )

                        message_parts = [f"{len(traders)} traders bought `{address}`: \n"]
                        
                        for idx, trader in enumerate(sorted_traders, 1):
                            sol_amount = session.token_sol_amounts[address].get(trader)
                            pump_type = session.token_pump_types.get(address, "Unknown")
                            
                            sol_amount_str = f"{sol_amount:.1f} SOL" if sol_amount is not None else "unknown amount"
                            
                            suffix = 'st' if idx == 1 else 'nd' if idx == 2 else 'rd' if idx == 3 else 'th'
                            trader_message = (
                                f"{idx}{suffix} trader {trader} bought {sol_amount_str} "
                                f"on {pump_type}"
                            ).strip()
                            trader_real = (
                                f"{idx}{suffix} trader  "
                                f"{trader}"
                            ).strip()
                            
                            message_parts.append(trader_real)
                        #message_parts.append("\nThis message was sent to the private group 150 seconds ago")
                        #message_parts.append("DM @thegroovymate for access to the privates")

                        current_messages.append("\n".join(message_parts))

            # Compare current and previous states
            has_changes = False
            
            # Check for new tokens or tokens with different trader counts
            for address, trader_count in current_tokens.items():
                if address not in previous_tokens :#or previous_tokens[address] != trader_count:
                    has_changes = True
                    break

            # Check for tokens that disappeared in current round
            #for address in previous_tokens:
             #   if address not in current_tokens:
              #      has_changes = True
               #     break

            # Send messages based on changes
            if has_changes:
                for message in current_messages[:2]:
                    if "So11111111111111111111111111111111111111112" in message:
                        continue
                    await context.bot.send_message(
                        chat_id=session.chat_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    await asyncio.sleep(1)
            
            #else:
             #   await context.bot.send_message(
              #      chat_id=session.chat_id,
               #     text="..."
                #)

            # Update previous tokens for next round
            previous_tokens = current_tokens.copy()
            
            # Sleep before next round
            await asyncio.sleep(1.5)
            logging.info("Another round Commences")
        

        except Exception as e:
            logging.error(f"Error in monitor_channels: {e}")
            logging.error(f"Current state - traders: {len(session.multi_trader_tokens)}")
            await asyncio.sleep(3)

        if not session.is_monitoring:
            final_duration = time.time() - session.start_time
            await context.bot.send_message(
                chat_id=session.chat_id,
                text=f"Monitoring stopped. Total running time: {final_duration:.2f} seconds"
            )
            break

async def start(update, context):
    """Stop the message monitoring process for the THETRACKOORS group"""
    global is_tracking_thetrackoors
    chat_id = update.effective_chat.id
    
    if chat_id in context.bot_data:
        await context.bot.send_message(
                chat_id=chat_id,
                text="NOTHING FOR YOU......"
            )
        
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="I am Zenith Bot and I track Smart wallets and KOL wallets.\n"
                 "To know the latest tokens smart wallets and KOLs are buying, join my channel where I drop the calls below:\n"
                 "https://t.me/Smart_Money_Buy"
        )


async def stop(update, context):
    """Stop the message monitoring process for the THETRACKOORS group"""
    global is_tracking_thetrackoors
    chat_id = update.effective_chat.id
    
    if chat_id in context.bot_data:
        session = context.bot_data[chat_id]
        if session.is_monitoring:
            session.is_monitoring = False
            if session.monitoring_task:
                session.monitoring_task.cancel()
            final_duration = time.time() - session.start_time
            session.multi_trader_tokens.clear()
            session.previous_messages.clear()
            session.token_pump_types.clear()
            session.token_market_caps.clear()
            session.token_sol_amounts.clear()
            session.token_timestamps.clear()
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Zenith bot has stopped monitoring .\nTotal running time: {final_duration:.2f} seconds"
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Zenith bot is not actively monitoring"
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="I am Zenith Bot and I track Smart wallets and KOL wallets.\n"
                 "To know the latest tokens smart wallets and KOLs are buying, join my channel where I drop the calls below:\n"
                 "https://t.me/Smart_Money_Buy"
        )

    

from flask import Flask
#from threading import Thread
from telegram import Update
from flask import request


async def main():
    global application
    await initialize_telethon()

    application = Application.builder().token(BOT_TOKEN).build()
    await application.initialize()
    await application.start()

    session = MonitoringSession(THETRACKOORS_CHAT_ID)  # Create a new session
    session.is_monitoring = True  # Set monitoring to True
    session.start_time = time.time()  # Set start time
    session.monitoring_task = asyncio.create_task(monitor_channels(application, session))  # Start monitoring directly

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))

    PORT = int(os.environ.get('PORT', '8080'))
    WEBHOOK_URL = "https://smartwalletsprivategroup.onrender.com/telegram"
    await application.bot.set_webhook(url=WEBHOOK_URL)

    app = Flask(__name__)

    @app.route('/')
    def home():
        return "Bot is running!"

    @app.route('/telegram', methods=['POST'])
    def telegram_webhook():
        if request.method == 'POST':
            try:
                update = Update.de_json(request.get_json(force=True), application.bot)
                # Use the existing event loop
                asyncio.run_coroutine_threadsafe(
                    application.process_update(update),
                    loop
                ).result()
                return 'OK'
            except Exception as e:
                logging.error(f"Error in webhook: {e}")
                return 'Error', 500
        return 'Only POST requests are allowed'

    # Run Flask in a separate thread
    from threading import Thread
    def run_flask():
        app.run(host='0.0.0.0', port=PORT)
    
    Thread(target=run_flask).start()
    
    # Keep the main event loop running
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

if __name__ == "__main__":
    print("Starting bot...")
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    #logging.info("Bot initialization started")
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
        logging.info("Bot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        logging.error(f"Fatal error: {e}")
        raise

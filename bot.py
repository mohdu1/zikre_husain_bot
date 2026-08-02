import logging
from datetime import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from telegram.error import BadRequest
import config
from sheets import db

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation States
ONBOARDING_NAME = 0
RIYAZ_Q1, RIYAZ_Q2, KALAAM_INPUT, VOICE_PROMPT, VOICE_INPUT, PRACTICE_CHECK = range(1, 7)

# --- Progress Formatting Helper ---
def format_progress_bars(user_id: int) -> str:
    riyaz_count, practice_count = db.get_progress_counts(user_id)
    
    # Riyaz Bar (Goal: 6)
    r_goal = 6
    r_prog = min(riyaz_count, r_goal)
    r_bar = f"[{'█' * r_prog}{'░' * (r_goal - r_prog)}]"
    r_msg = "🔥 Target achieved!" if riyaz_count >= r_goal else f"{r_goal - riyaz_count} more needed this week."
    
    # Practice Bar (Goal: 3)
    p_goal = 3
    p_prog = min(practice_count, p_goal)
    p_bar = f"[{'█' * (p_prog * 2)}{'░' * ((p_goal - p_prog) * 2)}]"
    p_msg = "🌟 Target achieved!" if practice_count >= p_goal else f"{p_goal - practice_count} more needed this week."
    
    return (
        f"🎙️ **Riyaz Progress (Morning Drills):**\n`{r_bar}` **{riyaz_count}/{r_goal} sessions** ({r_msg})\n\n"
        f"📅 **Group Practice Progress:**\n`{p_bar}` **{practice_count}/{p_goal} sessions** ({p_msg})"
    )

def get_practice_keyboard(selected: set):
    categories = ["Raudat Tahera Majlis", "Darees Majlis", "Party Practice"]
    keyboard = []
    for cat in categories:
        prefix = "✅ " if cat in selected else ""
        keyboard.append([InlineKeyboardButton(f"{prefix}{cat}", callback_data=f"toggle_{cat}")])
    keyboard.append([InlineKeyboardButton("DONE", callback_data="att_done")])
    keyboard.append([InlineKeyboardButton("❌ Skip / None", callback_data="att_skip")])
    return InlineKeyboardMarkup(keyboard)

# --- Onboarding & Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if user:
        await update.message.reply_text(
            f"Welcome back, **{user['Name']}**! 🌙\n\nLaunching your check-in sequence...",
            parse_mode="Markdown"
        )
        return await start_sequence(update.message, context)
    else:
        await update.message.reply_text(
            "Welcome to the **Zikre Husain Tracking Bot**! 🌙\n\n"
            "Please reply with your **Full Name** to complete registration.",
            parse_mode="Markdown"
        )
        return ONBOARDING_NAME

async def save_new_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text.strip()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    db.register_user(user_id, chat_id, full_name)
    await update.message.reply_text(
        f"Jazakallah, **{full_name}**! You are now registered.\n\nLaunching your check-in sequence...",
        parse_mode="Markdown"
    )
    return await start_sequence(update.message, context)

# --- Master Check-In Sequence Entry Point ---
async def start_mark_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start_sequence(update.message, context)

async def start_sequence(target, context):
    user_id = target.chat_id
    
    # 1. Anti-Cheat Lockout Check for Riyaz
    if db.has_logged_today("Riyaz_Log", user_id):
        await context.bot.send_message(
            user_id,
            f"⚠️ You have already completed your Riyaz check-in for today!\n\n{format_progress_bars(user_id)}\n\nMoving directly to Group Practice check...",
            parse_mode="Markdown"
        )
        return await prompt_group_practice(target, context)

    # 2. Start Riyaz Q1
    text = "Did you complete your morning Riyaz (Alankar, Aakar, vocal drills) today? 🎙️"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, completed Riyaz!", callback_data="rq1_yes")],
        [InlineKeyboardButton("❌ No / Skip", callback_data="rq1_no")]
    ])
    
    if hasattr(target, 'reply_text'):
        await target.reply_text(text, reply_markup=keyboard)
    else:
        await context.bot.send_message(target.chat_id, text, reply_markup=keyboard)
    return RIYAZ_Q1

# --- Riyaz & Kalaam Branching ---
async def handle_riyaz_q1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['did_riyaz'] = (query.data == "rq1_yes")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, practiced Kalaam", callback_data="rq2_yes")],
        [InlineKeyboardButton("❌ No", callback_data="rq2_no")]
    ])
    await query.edit_message_text(
        "Did you practice any specific Kalaam today? 🎶",
        reply_markup=keyboard
    )
    return RIYAZ_Q2

async def handle_riyaz_q2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    did_riyaz = context.user_data.get('did_riyaz', False)
    did_kalaam = (query.data == "rq2_yes")
    
    # CASE 1: No Riyaz AND No Kalaam -> Auto-proceed without Voice Note
    if not did_riyaz and not did_kalaam:
        await query.edit_message_text(
            f"Noted! Let's aim to get some practice in tomorrow morning. 💪\n\n{format_progress_bars(user_id)}",
            parse_mode="Markdown"
        )
        return await prompt_group_practice(query.message, context)
        
    # CASE 2: Yes Riyaz, BUT No Kalaam -> Auto-log "Only Riyaz" and ask Voice Note
    if did_riyaz and not did_kalaam:
        user = db.get_user(user_id)
        name = user["Name"] if user else "Unknown Member"
        success, msg = db.log_riyaz(user_id, name, "Only Riyaz")
        await query.edit_message_text(
            f"Great job! 🔥\n{msg}\n\n{format_progress_bars(user_id)}",
            parse_mode="Markdown"
        )
        return await prompt_voice_note(query.message, context)
        
    # CASE 3: Practiced a Kalaam (whether did_riyaz is Yes or No) -> Ask Kalaam Name
    await query.edit_message_text(
        "Awesome! Which Kalaam did you practice today?\n*(Type the Kalaam name in the chat below)*:",
        parse_mode="Markdown"
    )
    return KALAAM_INPUT

async def handle_kalaam_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    name = user["Name"] if user else "Unknown Member"
    kalaam = update.message.text.strip()
    
    # If they answered Yes to both Riyaz AND Kalaam, log both to sheet
    if context.user_data.get('did_riyaz', False):
        db.log_riyaz(user_id, name, "Only Riyaz")
        
    success, msg = db.log_riyaz(user_id, name, kalaam)
    await update.message.reply_text(
        f"Great job! 🔥\n{msg}\n\n{format_progress_bars(user_id)}",
        parse_mode="Markdown"
    )
    return await prompt_voice_note(update.message, context)

# --- Voice Note Prompt (Only triggered if they logged Riyaz or Kalaam) ---
async def prompt_voice_note(target, context):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Yes, submit Voice Note", callback_data="vprompt_yes")],
        [InlineKeyboardButton("No, continue to Practice check", callback_data="vprompt_no")]
    ])
    await context.bot.send_message(
        target.chat_id,
        "Would you like to submit a voice note of your practice for Admin review? 🔊",
        reply_markup=keyboard
    )
    return VOICE_PROMPT

async def handle_voice_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "vprompt_no":
        await query.edit_message_text("Noted! Moving to Group Practice check... 👍")
        return await prompt_group_practice(query.message, context)
    else:
        await query.edit_message_text("🎙️ **Please record and send your Telegram Voice Note / Audio file now:**", parse_mode="Markdown")
        return VOICE_INPUT

async def handle_voice_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    name = user["Name"] if user else f"User {user_id}"

    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_CHAT_ID,
            text=f"🎙️ **New Voice Note Submission**\nFrom: {name} (ID: `{user_id}`)",
            parse_mode="Markdown"
        )
        await update.message.forward(chat_id=config.ADMIN_CHAT_ID)
        await update.message.reply_text("✅ Voice note submitted to Admin! Jazakallah! ✨")
    except Exception as e:
        logger.error(f"Voice note forward error: {e}")
        await update.message.reply_text("❌ Failed to send to Admin.")
        
    return await prompt_group_practice(update.message, context)

# --- Group Practice Check ---
async def prompt_group_practice(target, context):
    user_id = target.chat_id
    
    # Anti-Cheat Lockout Check for Group Practice
    if db.has_logged_today("Attendance_Log", user_id):
        await context.bot.send_message(
            user_id,
            f"⚠️ You have already completed your Group Practice check-in for today!\n\n{format_progress_bars(user_id)}\n\n**All done for today! Come back tomorrow 🌙**",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    context.user_data['att_selected'] = set()
    text = "📅 **Group Practice Check:**\nDid you attend any group practice session today?\n*(Select all that apply and tap DONE)*:"
    keyboard = get_practice_keyboard(context.user_data['att_selected'])
    
    await context.bot.send_message(user_id, text, reply_markup=keyboard, parse_mode="Markdown")
    return PRACTICE_CHECK

async def handle_practice_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cat = query.data.split("toggle_")[1]
    selected = context.user_data.get('att_selected', set())
    
    if cat in selected:
        selected.remove(cat)
    else:
        selected.add(cat)
        
    context.user_data['att_selected'] = selected
    try:
        await query.edit_message_reply_markup(reply_markup=get_practice_keyboard(selected))
    except BadRequest:
        pass
    return PRACTICE_CHECK

async def handle_practice_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    selected = context.user_data.get('att_selected', set())

    if not selected:
        await query.answer("Please select at least one practice, or tap Skip!", show_alert=True)
        return PRACTICE_CHECK

    user = db.get_user(user_id)
    name = user["Name"] if user else "Unknown Member"
    
    results = []
    for act in selected:
        success, msg = db.log_attendance(user_id, name, act)
        results.append(msg)

    res_text = "\n".join(results)
    await query.edit_message_text(
        f"Mashallah!! ✨\n\n{res_text}\n\n{format_progress_bars(user_id)}\n\n**All done for today! Jazakallah! 🌙**",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def handle_practice_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await query.edit_message_text(
        f"No group practice logged today.\n\n{format_progress_bars(user_id)}\n\n**All done for today! Come back tomorrow 🌙**",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- 11 PM Daily Check-In Broadcast ---
async def daily_broadcast(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Executing 11 PM daily check-in broadcast...")
    chat_ids = db.get_all_chat_ids()
    
    for chat_id in set(chat_ids):
        try:
            user_id = int(chat_id)
            progress_text = format_progress_bars(user_id)
            text = (
                "🌙 **Daily Zikre Husain Check-In**\n\n"
                f"{progress_text}\n\n"
                "Don't let your potential go to waste—consistency is everything! Let's stay on track. 💯\n\n"
                "It is time for your daily attendance check-in!\n"
                "👉 Tap /mark right now to launch your check-in sequence."
            )
            await context.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {chat_id}: {e}")

# --- Local Test: Immediate Startup Notification ---
async def send_startup_notification(context: ContextTypes.DEFAULT_TYPE):
    """Fires 3 seconds after local script boot to simulate the daily notification."""
    logger.info("Executing local startup test notification...")
    chat_ids = db.get_all_chat_ids()
    
    for chat_id in set(chat_ids):
        try:
            user_id = int(chat_id)
            progress_text = format_progress_bars(user_id)
            text = (
                "🌙 **Zikre Husain Check-In Notification**\n\n"
                f"{progress_text}\n\n"
                "Did you complete your Riyaz and group practice today?\n"
                "👉 Tap /mark right now to launch your quick check-in sequence!"
            )
            await context.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Failed to send local test notification to {chat_id}: {e}")

# --- Application Setup ---
def main():
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    onboarding_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ONBOARDING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_user)]
        },
        fallbacks=[CommandHandler("start", start)]
    )

    sequence_conv = ConversationHandler(
        entry_points=[
            CommandHandler("mark", start_mark_command),
            CommandHandler("riyaz", start_mark_command),
            CommandHandler("start", start_mark_command)
        ],
        states={
            RIYAZ_Q1: [CallbackQueryHandler(handle_riyaz_q1, pattern="^rq1_.*")],
            RIYAZ_Q2: [CallbackQueryHandler(handle_riyaz_q2, pattern="^rq2_.*")],
            KALAAM_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_kalaam_input)],
            VOICE_PROMPT: [CallbackQueryHandler(handle_voice_prompt, pattern="^vprompt_.*")],
            VOICE_INPUT: [MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_note)],
            PRACTICE_CHECK: [
                CallbackQueryHandler(handle_practice_toggle, pattern="^toggle_"),
                CallbackQueryHandler(handle_practice_done, pattern="^att_done$"),
                CallbackQueryHandler(handle_practice_skip, pattern="^att_skip$")
            ]
        },
        fallbacks=[
            CommandHandler("start", start_mark_command),
            CommandHandler("mark", start_mark_command),
            CommandHandler("riyaz", start_mark_command)
        ],
        per_message=False
    )

    app.add_handler(onboarding_conv)
    app.add_handler(sequence_conv)

    job_queue = app.job_queue
    if job_queue:
        # 11 PM Scheduled Job
        target_time = time(hour=23, minute=0, second=0, tzinfo=config.IST)
        job_queue.run_daily(daily_broadcast, time=target_time, name="daily_reminder_11pm")
        logger.info("Scheduled 11 PM IST Daily Check-in Broadcast.")
        
        # Local Test Job: Triggers notification 3 seconds after script boot
        job_queue.run_once(send_startup_notification, when=3, name="startup_test_notif")
        logger.info("Scheduled local startup test notification to trigger in 3 seconds...")

    logger.info("Zikre Husain Bot (Plain English + Startup Notification Engine) is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
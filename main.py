# main.py

from pyrogram import Client, filters
from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import QueryIdInvalid
from config import API_ID, API_HASH, BOT_TOKEN, ADMINS # Import all from config.py
from database import Database # Import your Database class from database.py
from datetime import datetime
import asyncio # Pyrogram is async
import logging # For logging events and errors

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database connection
db = Database()

# Initialize the Pyrogram Client
# "MovieFilterBot" is the session name, change if you have multiple bots
app = Client("MovieFilterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Start Command ---
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    db.add_or_update_user(user_id, username) # Track user
    await message.reply_text("Hello! I'm a movie filter bot. Send me a movie title to find it, or use inline mode (@yourbotname movie title).")
    logger.info(f"User {user_id} ({username}) started the bot.")


# --- Search by Text Message ---
@app.on_message(filters.text & filters.private & ~filters.command)
async def text_search(client, message):
    query = message.text
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logger.info(f"User {user_id} ({username}) searched for: '{query}'")

    movie = db.get_movie_by_title(query)

    if movie:
        response_text = f"**{movie['original_title']}** ({movie['year']})\n"
        if "imdb_id" in movie and movie["imdb_id"]:
            response_text += f"IMDb: [Link](https://www.imdb.com/title/{movie['imdb_id']})\n"
        # Add more details if you fetch them (e.g., plot, genre)

        keyboard = []
        if "file_id" in movie and movie["file_id"]:
            keyboard.append([InlineKeyboardButton("Get Movie File", callback_data=f"get_file_{movie['imdb_id']}")])
        if "direct_link" in movie and movie["direct_link"]:
            keyboard.append([InlineKeyboardButton("Watch Online", url=movie["direct_link"])])

        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            reply_markup = None

        await message.reply_text(
            response_text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=True
            # Use movie.get("thumbnail_id") here if you want to include a photo with the message
            # photo=movie.get("thumbnail_id") # If the thumbnail is a photo file_id
        )
    else:
        await message.reply_text(f"Sorry, I couldn't find '{query}' in my database.")
        logger.info(f"No movie found for query: '{query}'")


# --- Callback Query Handler (for "Get Movie File" button) ---
@app.on_callback_query(filters.regex(r"^get_file_"))
async def get_file_callback(client, callback_query):
    imdb_id = callback_query.data.split("_")[2]
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.first_name
    logger.info(f"User {user_id} ({username}) requested file for IMDb ID: {imdb_id}")

    movie = db.movies_collection.find_one({"imdb_id": imdb_id})

    if movie and "file_id" in movie and movie["file_id"]:
        try:
            thumbnail = movie.get("thumbnail_id") # Get custom thumbnail if available
            await client.send_document(
                chat_id=callback_query.message.chat.id,
                document=movie["file_id"],
                caption=f"Here is **{movie['original_title']}**",
                thumbnail=thumbnail, # Pass the thumbnail file_id
                parse_mode="Markdown"
            )
            await callback_query.answer("Sending your movie!")
            logger.info(f"Sent movie {movie['original_title']} to user {user_id}.")
        except Exception as e:
            logger.error(f"Error sending document for movie {imdb_id} to user {user_id}: {e}")
            await callback_query.answer("Failed to send movie. The file might be corrupted or inaccessible. Please try again later.", show_alert=True)
    else:
        logger.warning(f"Movie file not found or an error for IMDb ID: {imdb_id} requested by user {user_id}.")
        await callback_query.answer("Movie file not found or an error occurred. It might have been removed.", show_alert=True)


# --- Inline Mode Search ---
@app.on_inline_query()
async def inline_search(client, inline_query):
    query = inline_query.query.strip()
    user_id = inline_query.from_user.id
    username = inline_query.from_user.username or inline_query.from_user.first_name
    logger.info(f"User {user_id} ({username}) used inline query: '{query}'")

    if not query:
        # Optionally show some trending movies or a hint
        await client.answer_inline_query(
            inline_query.id,
            results=[],
            switch_pm_text="Type a movie title to search!",
            switch_pm_parameter="start", # When user clicks, they go to PM with /start
            cache_time=5
        )
        return

    movies = db.get_movies_by_title_regex(query, limit=10) # Get up to 10 suggestions
    results = []

    for movie in movies:
        description = f"Year: {movie['year']}"
        if "imdb_id" in movie and movie["imdb_id"]:
            description += f" | IMDb: https://www.imdb.com/title/{movie['imdb_id']}"

        message_content = f"**{movie['original_title']}** ({movie['year']})\n"
        if "imdb_id" in movie and movie["imdb_id"]:
            message_content += f"IMDb: [Link](https://www.imdb.com/title/{movie['imdb_id']})"
        # Potentially add a placeholder for more details if you fetch them

        keyboard = []
        if "file_id" in movie and movie["file_id"]:
            keyboard.append([InlineKeyboardButton("Get Movie File", callback_data=f"get_file_{movie['imdb_id']}")])
        if "direct_link" in movie and movie["direct_link"]:
            keyboard.append([InlineKeyboardButton("Watch Online", url=movie["direct_link"])])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        results.append(
            InlineQueryResultArticle(
                id=str(movie["_id"]), # MongoDB ObjectId needs to be string
                title=f"{movie['original_title']} ({movie['year']})",
                input_message_content=InputTextMessageContent(
                    message_content,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                ),
                description=description,
                reply_markup=reply_markup,
                thumb_url="https://via.placeholder.com/48x48?text=Movie" # A generic placeholder thumbnail for inline results
                # Or a specific URL to a movie poster if you store them as URLs in DB
            )
        )
    try:
        await client.answer_inline_query(inline_query.id, results, cache_time=5)
    except QueryIdInvalid:
        logger.warning(f"Query ID Invalid for inline query '{query}', likely due to fast typing by user {user_id}.")
        # This error is common with fast typers, often safe to ignore or just log.


# --- Admin Commands (Example: Add a movie) ---
@app.on_message(filters.command("addmovie") & filters.user(ADMINS))
async def add_movie_command(client, message):
    if len(message.command) < 4: # Minimum for Title, Year, IMDb_ID
        await message.reply_text("Usage: `/addmovie Title | Year | IMDb_ID | File_ID | Thumbnail_ID | Direct_Link`\n"
                                 "Use 'None' for optional fields if not applicable.", parse_mode="Markdown")
        return

    try:
        # Example: /addmovie Interstellar | 2014 | tt0816692 | AgADq... | AgAD_thumb... | https://example.com/movie.mp4
        parts_str = message.text.split(" ", 1)[1] # Get everything after /addmovie
        parts = [p.strip() for p in parts_str.split(" | ")]

        title = parts[0]
        year = int(parts[1])
        imdb_id = parts[2]
        file_id = parts[3] if len(parts) > 3 and parts[3].strip() != "None" else None
        thumbnail_id = parts[4] if len(parts) > 4 and parts[4].strip() != "None" else None
        direct_link = parts[5] if len(parts) > 5 and parts[5].strip() != "None" else None

        db.add_movie(title, year, imdb_id, file_id, direct_link, thumbnail_id)
        await message.reply_text(f"Movie '{title}' added successfully with IMDb ID `{imdb_id}`!")
        logger.info(f"Admin {message.from_user.id} added movie: {title} ({imdb_id})")
    except ValueError:
        await message.reply_text("Error: Year must be a number. Check your format.")
    except IndexError:
        await message.reply_text("Error: Missing required fields. Usage: `/addmovie Title | Year | IMDb_ID | ...`", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in add_movie_command by admin {message.from_user.id}: {e}")
        await message.reply_text(f"An unexpected error occurred: {e}")

# --- Main bot run ---
if __name__ == "__main__":
    logger.info("Bot starting...")
    # This will block until the bot stops (e.g., Ctrl+C)
    app.run()
    logger.info("Bot stopped.")

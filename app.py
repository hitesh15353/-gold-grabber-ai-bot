import os
import asyncio
import logging

from aiohttp import web, ClientSession, ClientTimeout
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("goldgrabber")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


async def fetch_news():
    if not NEWS_API_KEY:
        return []

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": '(gold OR XAUUSD OR "Federal Reserve" OR inflation OR NFP)',
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 8,
        "apiKey": NEWS_API_KEY,
    }

    timeout = ClientTimeout(total=15)
    async with ClientSession(timeout=timeout) as session:
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("articles", [])


async def ai_analysis(news):
    if not client:
        return "AI analysis is not configured yet. Add OPENAI_API_KEY in Render Environment Variables."

    text = "\n".join(
        f"- {a.get('title', '')} | {a.get('description') or ''}"
        for a in news[:8]
    )

    prompt = f"""You are a gold/XAUUSD market intelligence assistant.
Analyze the following recent headlines. Do NOT claim certainty or guaranteed price direction.

Return:
1) Gold bias: Bullish/Bearish/Neutral
2) Confidence: 0-100
3) Top 3 drivers
4) What would invalidate the bias
5) Key upcoming risk

Keep it concise and decision-support oriented.

HEADLINES:
{text}"""

    response = await client.responses.create(
        model="gpt-5.6",
        input=prompt,
    )
    return response.output_text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🥇 GoldGrabber AI is online.\n\n"
        "/news - latest gold-related headlines\n"
        "/gold - AI bias from latest headlines\n"
        "/why - explain the current news drivers\n"
        "/full - full AI market-intelligence report"
    )


async def news_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        articles = await fetch_news()
    except Exception:
        logger.exception("News fetch failed")
        await update.message.reply_text("Unable to fetch news right now. Please try again.")
        return

    if not articles:
        await update.message.reply_text("News API is not configured yet.")
        return

    lines = ["📰 GOLD NEWS\n"]
    for article in articles[:6]:
        lines.append(
            f"• {article.get('title', 'Untitled')}\n"
            f"{article.get('url', '')}"
        )

    await update.message.reply_text(
        "\n\n".join(lines),
        disable_web_page_preview=True,
    )


async def analysis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        articles = await fetch_news()
    except Exception:
        logger.exception("News fetch failed")
        await update.message.reply_text("Unable to fetch news right now. Please try again.")
        return

    if not articles:
        await update.message.reply_text("News API is not configured yet.")
        return

    try:
        result = await ai_analysis(articles)
    except Exception:
        logger.exception("AI analysis failed")
        await update.message.reply_text("AI analysis is temporarily unavailable. Please try again.")
        return

    await update.message.reply_text("🥇 GOLD AI REPORT\n\n" + result)


async def health(request):
    return web.Response(text="GoldGrabber AI Bot is running", status=200)


async def run_web_server():
    port = int(os.environ.get("PORT", "10000"))
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("Health server listening on port %s", port)

    # Keep the HTTP server alive for the lifetime of the service.
    await asyncio.Event().wait()


async def main():
    bot = Application.builder().token(BOT_TOKEN).build()

    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("news", news_cmd))
    bot.add_handler(CommandHandler("gold", analysis_cmd))
    bot.add_handler(CommandHandler("why", analysis_cmd))
    bot.add_handler(CommandHandler("full", analysis_cmd))

    await bot.initialize()
    await bot.start()
    await bot.updater.start_polling()

    logger.info("GoldGrabber AI Telegram bot is running")

    try:
        await run_web_server()
    finally:
        await bot.updater.stop()
        await bot.stop()
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

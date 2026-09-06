import os, asyncio, logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import aiohttp
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)
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
        "language": "en", "sortBy": "publishedAt", "pageSize": 8,
        "apiKey": NEWS_API_KEY
    }
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params=params, timeout=15) as r:
            data = await r.json()
            return data.get("articles", [])

async def ai_analysis(news):
    if not client:
        return "AI analysis is not configured yet. Add OPENAI_API_KEY in Render Environment Variables."
    text="\n".join(f"- {a.get('title','')} | {a.get('description','') or ''}" for a in news[:8])
    prompt=f"""You are a gold/XAUUSD market intelligence assistant.
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
    resp=await client.responses.create(model="gpt-5.6", input=prompt)
    return resp.output_text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🥇 GoldGrabber AI is online.\n\n"
        "/news - latest gold-related headlines\n"
        "/gold - AI bias from latest headlines\n"
        "/why - explain the current news drivers\n"
        "/full - full AI market-intelligence report"
    )

async def news_cmd(update, context):
    articles=await fetch_news()
    if not articles:
        await update.message.reply_text("News API is not configured yet.")
        return
    lines=["📰 GOLD NEWS\n"]
    for a in articles[:6]:
        lines.append(f"• {a.get('title','Untitled')}\n{a.get('url','')}")
    await update.message.reply_text("\n\n".join(lines), disable_web_page_preview=True)

async def analysis_cmd(update, context):
    articles=await fetch_news()
    if not articles:
        await update.message.reply_text("News API is not configured yet.")
        return
    result=await ai_analysis(articles)
    await update.message.reply_text("🥇 GOLD AI REPORT\n\n"+result)

async def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news_cmd))
    app.add_handler(CommandHandler("gold", analysis_cmd))
    app.add_handler(CommandHandler("why", analysis_cmd))
    app.add_handler(CommandHandler("full", analysis_cmd))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    print("GoldGrabber AI bot running")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

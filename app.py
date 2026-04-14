import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from playwright.async_api import async_playwright
import asyncio, base64, os, time, json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("chatgpt-api")

app = FastAPI(title="ChatGPT Browser API")

_playwright = None
_browser    = None
_context    = None
_page       = None
_lock       = asyncio.Lock()

@app.on_event("startup")
async def startup():
    global _playwright, _browser, _context, _page
    logger.info("Starting up Playwright and Browser...")
    try:
        # Quick internet check
        import http.client
        try:
            c = http.client.HTTPSConnection("google.com", timeout=5)
            c.request("HEAD", "/")
            logger.info("Internet connection verified.")
            c.close()
        except Exception as e:
            logger.warning(f"Internet check failed: {e}. This might be expected in some environments.")

        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--disable-gpu"],
        )
        _context = await _browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        )
        
        # Load cookies
        cookies_path = os.getenv("COOKIES_PATH", "cookies.json")
        if os.path.exists(cookies_path):
            logger.info(f"Loading cookies from {cookies_path}")
            with open(cookies_path) as f:
                cookies = json.load(f)
            
            # Map domains comprehensively
            fixed = []
            for c in cookies:
                fixed.append(c)
                domain = c.get("domain", "")
                # Create copies for all related ChatGPT subdomains
                for alt_domain in [".chatgpt.com", ".openai.com", "backend.chatgpt.com", "chatgpt.com"]:
                    if domain and domain != alt_domain and (domain in alt_domain or alt_domain in domain):
                        alt = dict(c)
                        alt["domain"] = alt_domain
                        fixed.append(alt)
            
            try:
                await _context.add_cookies(fixed)
                logger.info("Cookies added successfully.")
            except Exception as e:
                logger.error(f"Failed to add fixed cookies: {e}. Trying original.")
                await _context.add_cookies(cookies)
        else:
            logger.warning(f"Cookies file not found at {cookies_path}")

        _page = await _context.new_page()
        logger.info("Navigating to ChatGPT...")
        await _page.goto("https://chatgpt.com", timeout=60000)
        await asyncio.sleep(5)
        logger.info("Startup complete.")
    except Exception as e:
        logger.critical(f"Startup failed: {e}")
        raise e

@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down...")
    if _browser: await _browser.close()
    if _playwright: await _playwright.stop()

@app.get("/health")
async def health():
    import http.client
    internet = "Unknown"
    try:
        conn = http.client.HTTPSConnection("chatgpt.com", timeout=3)
        conn.request("HEAD", "/")
        internet = "Connected (chatgpt.com)"
        conn.close()
    except Exception as e: 
        internet = f"Disconnected or Blocked: {str(e)}"
    
    return {
        "status": "healthy" if _page and not _page.is_closed() else "unhealthy",
        "internet_access": internet,
        "browser_url": _page.url if _page else "none"
    }

@app.get("/live", response_class=HTMLResponse)
async def live_view():
    try:
        buf = await _page.screenshot(type="png")
        img = base64.b64encode(buf).decode()
    except Exception as e:
        logger.error(f"Failed to take live screenshot: {e}")
        return f"Error taking screenshot: {e}"
        
    return f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"><title>ChatGPT Live</title>
<style>
  body{{font-family:Arial;background:#1a1a2e;color:#fff;text-align:center;padding:20px}}
  img{{max-width:100%;border:2px solid #444;border-radius:8px}}
  .btn{{background:#10a37f;color:#fff;border:none;padding:10px 20px;margin:5px;border-radius:6px;cursor:pointer;font-size:14px}}
  input{{padding:8px;width:60%;border-radius:6px;border:1px solid #444;background:#2d2d44;color:#fff}}
  .section{{background:#2d2d44;border-radius:10px;padding:15px;margin:10px auto;max-width:700px}}
</style></head><body>
<h2>🖥️ ChatGPT Live Browser</h2>
<div class="section">
  <img src="data:image/png;base64,{img}" id="screen"><br><br>
  <button class="btn" onclick="refresh()">🔄 تحديث</button>
  <button class="btn" onclick="newChat()">➕ محادثة جديدة</button>
  <button class="btn" onclick="saveCookies()">💾 حفظ الكوكيز</button>
</div>
<div class="section">
  <input id="selector" placeholder="CSS Selector"><br><br>
  <input id="txtInput" placeholder="النص...">
  <button class="btn" onclick="typeText()">✍️ اكتب</button>
  <button class="btn" onclick="clickEl()">👆 كليك</button>
</div>
<div class="section">
  <input id="urlInput" value="https://chatgpt.com" style="width:70%">
  <button class="btn" onclick="navigate()">اذهب</button>
</div>
<div id="msg" style="color:#10a37f;margin-top:10px"></div>
<script>
async function refresh(){{
  const r=await fetch('/screenshot');const d=await r.json();
  if(d.image) document.getElementById('screen').src='data:image/png;base64,'+d.image;
}}
async function newChat(){{await fetch('/new-chat',{{method:'POST'}});setTimeout(refresh,3000);msg('...');}}
async function saveCookies(){{const r=await fetch('/save-cookies',{{method:'POST'}});const d=await r.json();msg(d.status||d.error);}}
async function typeText(){{
  await fetch('/action',{{method:'POST',headers:{{'Content-Type':'application/json'}},
  body:JSON.stringify({{action:'type',selector:document.getElementById('selector').value,text:document.getElementById('txtInput').value}})}});
  setTimeout(refresh,1000);
}}
async function clickEl(){{
  await fetch('/action',{{method:'POST',headers:{{'Content-Type':'application/json'}},
  body:JSON.stringify({{action:'click',selector:document.getElementById('selector').value}})}});
  setTimeout(refresh,1000);
}}
async function navigate(){{
  await fetch('/action',{{method:'POST',headers:{{'Content-Type':'application/json'}},
  body:JSON.stringify({{action:'goto',url:document.getElementById('urlInput').value}})}});
  setTimeout(refresh,3000);msg('جاري التنقل...');
}}
function msg(t){{document.getElementById('msg').innerText=t;}}
setInterval(refresh,8000);
</script></body></html>"""

@app.get("/screenshot")
async def screenshot_api():
    try:
        buf = await _page.screenshot(type="png")
        return {"image": base64.b64encode(buf).decode()}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/new-chat")
async def new_chat():
    try:
        await _page.goto("https://chatgpt.com/?oai-dm=1", timeout=30000)
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/action")
async def action(payload: dict):
    try:
        act = payload.get("action")
        selector = payload.get("selector")
        if act == "click":
            await _page.click(selector, timeout=5000)
        elif act == "type":
            await _page.fill(selector, payload.get("text",""))
        elif act == "goto":
            await _page.goto(payload["url"], timeout=30000)
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/save-cookies")
async def save_cookies():
    try:
        cookies = await _context.cookies()
        path = os.getenv("COOKIES_PATH", "cookies.json")
        with open(path, "w") as f:
            json.dump(cookies, f)
        return {"status": f"✅ تم حفظ {len(cookies)} كوكي"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def send_and_wait(text: str, image_b64=None) -> str:
    full_reply = ""
    async for chunk in send_and_stream(text, image_b64):
        full_reply += chunk
    return full_reply or "لم يتم استلام رد."

async def send_and_stream(text: str, image_b64=None):
    page = _page
    if not page:
        logger.error("Page not initialized")
        yield "Error: Browser not initialized"
        return

    try:
        if "chatgpt.com" not in page.url:
            await page.goto("https://chatgpt.com", timeout=30000)

        stop_btn = page.locator('[data-testid="stop-button"]')
        composer = page.locator("#prompt-textarea")
        await composer.wait_for(state="visible", timeout=30000)
        await composer.click()
        
        # Human-like typing for the first few characters, then fill the rest
        if len(text) > 10:
            await composer.type(text[:5], delay=100)
            await composer.fill(text)
        else:
            await composer.type(text, delay=100)
            
        await composer.focus()
        await page.keyboard.press(" ")
        await page.keyboard.press("Backspace")
        await asyncio.sleep(0.5)

        if image_b64:
            img_bytes = base64.b64decode(image_b64)
            tmp_path = f"/tmp/upload_{int(time.time())}.png"
            with open(tmp_path, "wb") as f: f.write(img_bytes)
            await page.locator('input[type="file"]').first.set_input_files(tmp_path)
            await asyncio.sleep(2)
            if os.path.exists(tmp_path): os.remove(tmp_path)

        # Get initial count of assistant messages
        assistant_selector = '[data-message-author-role="assistant"], .agent-turn, .markdown'
        initial_count = await page.locator(assistant_selector).count()

        send_btn = page.locator('[data-testid="send-button"]')
        try:
            await send_btn.wait_for(state="visible", timeout=5000)
            await send_btn.click()
        except:
            await composer.press("Enter")

        logger.info("Message sent, waiting for response turn...")
        
        # 2. Wait for generation to start
        started = False
        for _ in range(20): # Increased to 20s
            if await page.locator('[data-testid="stop-button"]').is_visible():
                started = True
                break
            current_c = await page.locator(assistant_selector).count()
            if current_c > initial_count:
                started = True
                break
            
            # Check for error/blocked messages
            if await page.locator('text="Something went wrong", text="Too many requests", text="Verify you are human"').count():
                logger.warning("Error message or Captcha detected.")
                break
                
            await asyncio.sleep(1)
            
        if not started:
            logger.warning("Generation didn't start or was blocked. Refreshing page and returning error.")
            await page.reload(timeout=60000)
            yield "ChatGPT يبدو عالقاً أو يطلب التحقق. تم إعادة تحديث الصفحة، يرجى المحاولة مرة أخرى."
            return

        last_sent_len = 0
        start_time = time.time()
        timeout = 180
        
        while time.time() - start_time < timeout:
            msgs = page.locator(assistant_selector)
            c = await msgs.count()
            
            if c > initial_count:
                last_node = msgs.nth(c-1)
                try:
                    full_text = await last_node.inner_text()
                    if len(full_text) > last_sent_len:
                        yield full_text[last_sent_len:]
                        last_sent_len = len(full_text)
                        start_time = time.time()
                except: pass # Occasional detachment during typing
            
            if not await page.locator('[data-testid="stop-button"]').is_visible():
                if c > initial_count:
                    # Final check for text
                    full_text = await msgs.nth(c-1).inner_text()
                    if len(full_text) > last_sent_len:
                        yield full_text[last_sent_len:]
                    break
                # If stop button went away but no message, wait a bit more
                if time.time() - start_time > 15:
                    break
            
            await asyncio.sleep(0.5)
            
        if time.time() - start_time >= timeout:
            logger.warning("Stream timeout.")
            try: await page.locator('[data-testid="stop-button"]').click()
            except: pass

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"\n[Error: {str(e)}]"
        try: await page.reload(timeout=30000)
        except: pass

@app.get("/")
def root(): return {"status": "ok", "live_view": "/live", "streaming": True}

@app.post("/chat")
async def chat(payload: dict):
    message = (payload.get("message") or payload.get("prompt") or "").strip()
    stream = payload.get("stream", False)
    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)
    
    if stream:
        async def stream_generator():
            async with _lock:
                async for chunk in send_and_stream(message):
                    yield chunk
        return StreamingResponse(stream_generator(), media_type="text/plain")

    async with _lock:
        try:
            reply = await send_and_wait(message)
            return {"reply": reply}
        except Exception as e:
            return JSONResponse({"error":str(e)}, status_code=500)

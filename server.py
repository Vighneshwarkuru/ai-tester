import os
import asyncio
import queue
import threading
import urllib.request
import urllib.parse
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import Agent
from browser import BrowserManager
from brain import Brain

app = FastAPI(title="AI Browser Tester UI Backend")

# Mount directories for serving static reports and screenshots
os.makedirs("screenshots", exist_ok=True)
os.makedirs("reports", exist_ok=True)
app.mount("/screenshots", StaticFiles(directory="screenshots"), name="screenshots")
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

class ValidateRequest(BaseModel):
    url: str

class AnalyzeRequest(BaseModel):
    url: str
    ollama_url: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:7b"

@app.get("/", response_class=HTMLResponse)
def read_index():
    frontend_path = os.path.join("html", "frontend.html")
    if os.path.exists(frontend_path):
        with open(frontend_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h2>frontend.html not found</h2>"

@app.post("/api/validate")
def validate_url(req: ValidateRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    
    # support local file schema
    if url.startswith("file://"):
        file_path = url[7:]
        if os.path.exists(file_path):
            return {"valid": True, "type": "local_file"}
        else:
            raise HTTPException(status_code=400, detail="Local file does not exist")
            
    # parse web url
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or parsed.scheme not in ["http", "https"]:
        # Try prepending http://
        url = "http://" + url
        parsed = urllib.parse.urlparse(url)
        
    try:
        req_headers = {"User-Agent": "Mozilla/5.0"}
        request = urllib.request.Request(url, headers=req_headers)
        # 5 second timeout
        with urllib.request.urlopen(request, timeout=5.0) as response:
            return {"valid": True, "type": "web", "resolved_url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to reach URL: {str(e)}")

@app.post("/api/analyze")
def analyze_website(req: AnalyzeRequest):
    """
    Launch Playwright briefly to scrape the home page, then query Ollama to identify the site and suggest a goal.
    """
    url = req.url.strip()
    # Resolve local paths
    if os.path.exists(url) and not url.startswith("file://"):
        url = "file://" + os.path.abspath(url)
        
    browser = BrowserManager(headless=True)
    try:
        browser.start(url)
        elements = browser.get_interactive_elements()
        page_title = browser.page.title()
        
        # Build list of elements for context
        elements_summary = "\n".join([
            f"- {el['tagName']} '{el['text']}': selector='{el['selector']}'"
            for el in elements[:20]  # First 20 elements
        ])
        
        brain = Brain(ollama_url=req.ollama_url, model=req.model)
        
        system_prompt = (
            "You are an AI browser testing coordinator. Analyze the website details provided by the user "
            "and output a clean JSON describing the website and defining a smart testing goal. "
            "Do not include any markdown tags."
        )
        
        user_prompt = f"""Target URL: {url}
Page Title: {page_title}
Visible interactive elements:
{elements_summary}

Please respond with a valid JSON object matching this structure:
{{
  "purpose": "A concise 1-2 sentence description of what this website appears to be.",
  "suggested_goal": "A single logical testing goal string. E.g., 'Test the login flow with invalid credentials and find bugs', 'Explore the main features of the landing page and verify link navigation.'"
}}
"""
        analysis = brain.query(system_prompt, user_prompt)
        return {
            "purpose": analysis.get("purpose", "Unknown application/website."),
            "suggested_goal": analysis.get("suggested_goal", "Explore and verify the core elements of the website.")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        browser.close()

@app.websocket("/api/test-ws")
async def test_websocket(websocket: WebSocket):
    await websocket.accept()
    
    # Receive initial parameters
    try:
        params = await websocket.receive_json()
    except Exception:
        await websocket.close()
        return

    url = params.get("url")
    goal = params.get("goal")
    steps = params.get("steps", 10)
    ollama_url = params.get("ollama_url", "http://localhost:11434")
    model = params.get("model", "qwen2.5-coder:7b")
    headless = params.get("headless", True)
    copilot_mode = params.get("copilot_mode", False)
    
    # Resolve local path if it refers to a file on disk
    if os.path.exists(url) and not url.startswith("file://"):
        url = "file://" + os.path.abspath(url)

    msg_queue = queue.Queue()

    def step_callback(step_data):
        # Format screenshot path to be relative url
        if step_data.get("screenshot"):
            step_data["screenshot"] = f"/screenshots/{os.path.basename(step_data['screenshot'])}"
        
        # If it's a copilot query message, forward it directly as type copilot_query
        if isinstance(step_data, dict) and step_data.get("type") == "copilot_query":
            msg_queue.put(step_data)
        else:
            msg_queue.put({
                "type": "step",
                "data": step_data
            })

    agent = None

    def agent_worker():
        nonlocal agent
        try:
            agent = Agent(
                target_url=url,
                goal=goal,
                max_steps=steps,
                ollama_url=ollama_url,
                model=model,
                headless=headless,
                step_callback=step_callback,
                copilot_mode=copilot_mode
            )
            agent.run()
            # Feed final report details
            msg_queue.put({
                "type": "completed",
                "bugs": agent.reporter.bugs,
                "status": agent.reporter.status,
                "duration": round(agent.reporter.end_time - agent.reporter.start_time, 1) if agent.reporter.end_time else 0
            })
        except Exception as e:
            msg_queue.put({
                "type": "error",
                "message": str(e)
            })

    # Run in a background thread to prevent blocking FastAPI async loop
    worker_thread = threading.Thread(target=agent_worker, daemon=True)
    worker_thread.start()

    # Reader Task to read from WebSocket and feed into agent.action_queue
    async def websocket_reader():
        try:
            while worker_thread.is_alive():
                data = await websocket.receive_json()
                if agent:
                    agent.action_queue.put(data)
        except Exception:
            pass

    reader_task = asyncio.create_task(websocket_reader())

    # Stream loop
    while worker_thread.is_alive() or not msg_queue.empty():
        while not msg_queue.empty():
            msg = msg_queue.get_nowait()
            await websocket.send_json(msg)
            if msg["type"] in ["completed", "error"]:
                break
        await asyncio.sleep(0.2)
        
    reader_task.cancel()
    await websocket.close()

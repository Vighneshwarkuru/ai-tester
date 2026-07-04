import time
import traceback
import json
import queue
from browser import BrowserManager
from brain import Brain
from reporter import Reporter

COPILOT_SYSTEM_PROMPT = """You are an AI Browser Testing Copilot. Your job is to analyze the current website state and suggest the top 3-4 logical next actions for the user to choose from.

Expected JSON output format:
{
  "thought": "Your reasoning in very simple, plain English (keep it short, clear, and easy to understand)",
  "options": [
    {
      "label": "Brief description of this option (e.g. Click Login button)",
      "action": "click",
      "selector": "The CSS selector for this element",
      "value": ""
    },
    {
      "label": "Brief description of this option (e.g. Type password)",
      "action": "fill",
      "selector": "The CSS selector for this element",
      "value": "Value to type"
    }
  ]
}
"""

SYSTEM_PROMPT = """You are an Autonomous AI Browser Testing Agent. Your goal is to thoroughly test a website according to the user's instructions.
You have access to a simulated browser and can issue commands.

Every turn, you will receive the current state:
- Goal: The target test objective.
- Current URL: The page you are currently on.
- Visible Interactive Elements: A list of elements on the page with their tag, text/label, value, and CSS selector.
- Console logs and network issues.
- History: What actions you took in the previous steps.

Your task is to decide the NEXT single logical action.
You MUST respond with a valid, clean JSON object. Do not include any markdown format tags like ```json or any other text before/after the JSON.

Expected JSON output format:
{
  "thought": "Your reasoning in very simple, plain English (keep it short, clear, and easy to understand)",
  "action": "click" | "fill" | "navigate" | "wait" | "report_bug" | "finish",
  "selector": "The CSS selector from the interactive elements list (or a valid selector on the page)",
  "value": "The text to enter (for fill), the URL (for navigate), or the duration in seconds (for wait)",
  "severity": "Low" | "Medium" | "High" | "Critical" (Required ONLY if action is 'report_bug')",
  "simple_description": "What is the error in very simple, plain English (Required ONLY if action is 'report_bug')",
  "technical_description": "Technical terms describing the error, e.g. status codes, console error logs, network errors (Required ONLY if action is 'report_bug')"
}

Guidelines:
1. To click a button or link, use "action": "click" and provide the correct "selector".
2. To type into an input field, use "action": "fill", provide the "selector" and the "value".
3. If you see a bug (e.g., console errors, network failures, unexpected UI states), use "action": "report_bug" and provide the severity and description. You can continue testing after reporting a bug.
4. If you have completed the goal fully and verified the flows, use "action": "finish".
5. Keep your actions logical. If you just filled a login form, click the submit or login button next. Do not repeat the same action in an infinite loop.
6. CRITICAL: Write all thoughts, reasoning, and bug descriptions in very simple, plain English. Use short sentences and simple words so a non-technical person can understand it easily.
7. When filling in password fields, ALWAYS generate and use a strong password (at least 12 characters, including uppercase letters, lowercase letters, numbers, and special characters like 'SecurePass123!') to prevent website strength validation failures.
"""

class Agent:
    def __init__(self, target_url: str, goal: str, max_steps: int = 15, ollama_url: str = "http://localhost:11434", model: str = "qwen2.5-coder:7b", headless: bool = False, step_callback=None, copilot_mode: bool = False):
        self.target_url = target_url
        self.goal = goal
        self.max_steps = max_steps
        self.browser = BrowserManager(headless=headless)
        self.brain = Brain(ollama_url=ollama_url, model=model)
        self.reporter = Reporter(goal=goal, target_url=target_url)
        self.history = []
        self.step_callback = step_callback
        self.copilot_mode = copilot_mode
        self.action_queue = queue.Queue()

    def run(self):
        print(f"Starting Agent. Target: {self.target_url} | Goal: {self.goal}")
        self.browser.start(self.target_url)
        
        step = 1
        success = True
        termination_reason = ""
        
        try:
            while step <= self.max_steps:
                print(f"\n--- Step {step} of {self.max_steps} ---")
                
                # Observe
                current_url = self.browser.page.url
                elements = self.browser.get_interactive_elements()
                console_logs = list(self.browser.console_logs)
                network_errors = list(self.browser.network_errors)
                
                # Clear logs for the next step so we only report new ones
                self.browser.console_logs.clear()
                self.browser.network_errors.clear()

                # Build prompt
                elements_str = "\n".join([
                    f"- {el['tagName']} '{el['text']}': selector='{el['selector']}' (value='{el['value']}', disabled={el['disabled']})"
                    for el in elements
                ])
                
                history_str = "\n".join([
                    f"Step {h['step']}: {h['action']} -> {h['result']}"
                    for h in self.history
                ])

                user_prompt = f"""Goal: {self.goal}
Current URL: {current_url}

Visible Interactive Elements:
{elements_str if elements_str else "No visible interactive elements found."}

Recent Console Logs:
{json.dumps(console_logs) if console_logs else "No new console logs."}

Recent Network Errors:
{json.dumps(network_errors) if network_errors else "No new network errors."}

History of actions taken:
{history_str if history_str else "No actions taken yet."}

What should you do next? Return a single JSON object.
"""

                # Think
                try:
                    if self.copilot_mode:
                        # 1. Suggest options using Brain
                        decision = self.brain.query(COPILOT_SYSTEM_PROMPT, user_prompt)
                        print(f"Copilot Options Thought: {decision.get('thought')}")
                        
                        screenshot_path = self.browser.capture_screenshot()
                        
                        # 2. Invoke step callback with type: copilot_query
                        if self.step_callback:
                            self.step_callback({
                                "type": "copilot_query",
                                "step": step,
                                "url": current_url,
                                "screenshot": screenshot_path,
                                "logs": console_logs,
                                "net_errors": network_errors,
                                "options": decision.get("options", []),
                                "thought": decision.get("thought", "")
                            })
                        
                        # 3. Block waiting for input
                        print("Agent paused in Copilot Mode. Waiting for user input...")
                        user_decision = self.action_queue.get()
                        
                        if user_decision.get("type") == "custom":
                            command = user_decision.get("command")
                            print(f"Received custom command: '{command}'. Translating to action...")
                            
                            translation_prompt = f"""Target URL: {current_url}
Visible interactive elements:
{elements_str}

The user wants to perform this custom action: "{command}"
Translate this custom action into a single valid structured action.

Expected JSON output format:
{{
  "thought": "Brief explanation of how the custom command maps to the element",
  "action": "click" | "fill" | "navigate" | "wait" | "report_bug" | "finish",
  "selector": "The CSS selector for the element",
  "value": "Value to fill, navigate or wait"
}}
"""
                            decision = self.brain.query(SYSTEM_PROMPT, translation_prompt)
                        else:
                            decision = user_decision.get("action")
                        
                        print(f"Resolved Copilot Action: {decision.get('action')} | Selector: {decision.get('selector')} | Value: {decision.get('value')}")
                    else:
                        decision = self.brain.query(SYSTEM_PROMPT, user_prompt)
                        print(f"Brain Thought: {decision.get('thought')}")
                        print(f"Brain Decision: {decision.get('action')} | Selector: {decision.get('selector')} | Value: {decision.get('value')}")
                except Exception as e:
                    print(f"Error querying brain: {e}")
                    # Capture screenshot of failure
                    screenshot_path = self.browser.capture_screenshot()
                    self.reporter.add_step(
                        step_number=step,
                        url=current_url,
                        action={"action": "error"},
                        screenshot_path=screenshot_path,
                        logs=console_logs,
                        net_errors=network_errors,
                        explanation=f"Error querying Brain: {e}"
                    )
                    success = False
                    termination_reason = f"Brain failure: {e}"
                    break

                action = decision.get("action", "wait").lower()
                
                # Handle special agent actions
                if action == "finish":
                    print("Agent decided to finish the testing session.")
                    screenshot_path = self.browser.capture_screenshot()
                    self.reporter.add_step(
                        step_number=step,
                        url=current_url,
                        action=decision,
                        screenshot_path=screenshot_path,
                        logs=console_logs,
                        net_errors=network_errors,
                        explanation="Goal reached. Testing finished."
                    )
                    break
                
                if action == "report_bug":
                    severity = decision.get("severity", "Medium")
                    simple_desc = decision.get("simple_description", "No description provided.")
                    tech_desc = decision.get("technical_description", "No technical details provided.")
                    print(f"BUG REPORTED [{severity}]: {simple_desc} | Tech: {tech_desc}")
                    self.reporter.add_bug(severity, simple_desc, tech_desc, step)
                    
                    # Also take screenshot for this step
                    screenshot_path = self.browser.capture_screenshot()
                    self.reporter.add_step(
                        step_number=step,
                        url=current_url,
                        action=decision,
                        screenshot_path=screenshot_path,
                        logs=console_logs,
                        net_errors=network_errors,
                        explanation=f"Reported Bug: {simple_desc}"
                    )
                    self.history.append({
                        "step": step,
                        "action": f"report_bug ({severity})",
                        "result": f"Simple: {simple_desc} | Tech: {tech_desc}"
                    })
                    step += 1
                    continue

                # Act
                result_str = ""
                screenshot_path = None
                try:
                    result_str = self.browser.execute_action(
                        action=action,
                        selector=decision.get("selector"),
                        value=decision.get("value")
                    )
                    print(f"Hands Action: {result_str}")
                except Exception as e:
                    result_str = f"Action failed: {e}"
                    print(result_str)
                    # Let the brain know it failed by adding to history
                
                # Take screenshot after action execution
                try:
                    screenshot_path = self.browser.capture_screenshot()
                except Exception as e:
                    print(f"Failed to capture screenshot: {e}")

                # Log step
                self.reporter.add_step(
                    step_number=step,
                    url=current_url,
                    action=decision,
                    screenshot_path=screenshot_path,
                    logs=console_logs,
                    net_errors=network_errors,
                    explanation=decision.get("thought", "")
                )
                
                self.history.append({
                    "step": step,
                    "action": f"{action} (selector={decision.get('selector')}, value={decision.get('value')})",
                    "result": result_str
                })
                
                if self.step_callback:
                    self.step_callback({
                        "step": step,
                        "url": current_url,
                        "decision": decision,
                        "screenshot": screenshot_path,
                        "logs": console_logs,
                        "net_errors": network_errors,
                        "result": result_str
                    })
                
                step += 1
                
            if step > self.max_steps:
                success = False
                termination_reason = "Reached maximum execution steps limit."

        except Exception as e:
            print(f"Unhandled exception in agent loop: {e}")
            traceback.print_exc()
            success = False
            termination_reason = f"Exception: {e}"
        finally:
            self.browser.close()
            self.reporter.finalize(success, termination_reason)
            print(f"Agent finished. Reports generated in {self.reporter.output_dir}/")

import os
import time
from playwright.sync_api import sync_playwright, Page, Browser, Playwright

class BrowserManager:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright: Playwright = None
        self.browser: Browser = None
        self.page: Page = None
        self.console_logs = []
        self.network_errors = []

    def start(self, url: str):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        
        # Enable console and request monitoring
        self.page = self.browser.new_page()
        self.page.on("console", lambda msg: self.console_logs.append({
            "type": msg.type,
            "text": msg.text,
            "location": msg.location
        }))
        self.page.on("requestfailed", lambda req: self.network_errors.append({
            "url": req.url,
            "error": req.failure.error_text if req.failure else "Unknown failure"
        }))
        
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")
        # Let dynamic content load
        time.sleep(1)

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def capture_screenshot(self, output_dir="screenshots") -> str:
        os.makedirs(output_dir, exist_ok=True)
        filename = f"screenshot_{int(time.time())}.png"
        filepath = os.path.join(output_dir, filename)
        self.page.screenshot(path=filepath)
        return filepath

    def get_interactive_elements(self) -> list:
        """
        Executes JavaScript in the browser context to find visible interactive elements.
        """
        js_script = """
        () => {
            const elements = Array.from(document.querySelectorAll(
                'button, a, input, textarea, select, [role="button"], [role="link"], [role="checkbox"], [role="radio"], [role="tab"]'
            ));
            
            return elements.map((el, index) => {
                const rect = el.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0 && 
                                  window.getComputedStyle(el).display !== 'none' && 
                                  window.getComputedStyle(el).visibility !== 'hidden';
                
                if (!isVisible) return null;

                // Build a unique CSS selector if possible
                let selector = '';
                if (el.id) {
                    selector = `#${el.id}`;
                } else {
                    let path = [];
                    let current = el;
                    while (current && current.nodeType === Node.ELEMENT_NODE) {
                        let name = current.nodeName.toLowerCase();
                        if (current.id) {
                            path.unshift(`${name}#${current.id}`);
                            break;
                        } else {
                            let sib = current, sibIndex = 1;
                            while (sib = sib.previousElementSibling) {
                                if (sib.nodeName.toLowerCase() === name) sibIndex++;
                            }
                            path.unshift(`${name}:nth-of-type(${sibIndex})`);
                        }
                        current = current.parentNode;
                    }
                    selector = path.join(' > ');
                }

                return {
                    id: index,
                    tagName: el.tagName.toLowerCase(),
                    type: el.getAttribute('type') || '',
                    text: el.innerText.trim() || el.value || el.placeholder || el.getAttribute('aria-label') || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    value: el.value || '',
                    disabled: el.disabled || el.getAttribute('aria-disabled') === 'true',
                    selector: selector
                };
            }).filter(el => el !== null);
        }
        """
        try:
            return self.page.evaluate(js_script)
        except Exception as e:
            # Fallback if evaluation fails
            return []

    def execute_action(self, action: str, selector: str = None, value: str = None) -> str:
        """
        Executes a Hands action on the page and returns a confirmation string.
        """
        action = action.lower()
        if action == "click":
            if not selector:
                raise ValueError("Selector is required for click action")
            self.page.click(selector)
            self.page.wait_for_load_state("networkidle")
            time.sleep(1)
            return f"Clicked element with selector: {selector}"
        
        elif action == "fill":
            if not selector or value is None:
                raise ValueError("Selector and value are required for fill action")
            self.page.fill(selector, value)
            self.page.wait_for_load_state("networkidle")
            time.sleep(0.5)
            return f"Filled element {selector} with value: '{value}'"
        
        elif action == "navigate":
            if not value:
                raise ValueError("URL (value) is required for navigate action")
            self.page.goto(value)
            self.page.wait_for_load_state("networkidle")
            time.sleep(1)
            return f"Navigated to: {value}"
            
        elif action == "wait":
            duration = float(value) if value else 2.0
            time.sleep(duration)
            return f"Waited for {duration} seconds"
            
        else:
            raise ValueError(f"Unknown action: {action}")
import os
import time

class Reporter:
    def __init__(self, goal: str, target_url: str, output_dir: str = "reports"):
        self.goal = goal
        self.target_url = target_url
        self.output_dir = output_dir
        self.steps = []
        self.bugs = []
        self.status = "In Progress"
        self.start_time = time.time()
        self.end_time = None
        os.makedirs(self.output_dir, exist_ok=True)

    def add_step(self, step_number: int, url: str, action: dict, screenshot_path: str, logs: list, net_errors: list, explanation: str):
        # We store screenshot_path relative to output_dir to make the HTML/Markdown reference them properly
        rel_screenshot_path = os.path.relpath(screenshot_path, self.output_dir) if screenshot_path else None
        self.steps.append({
            "number": step_number,
            "url": url,
            "action": action,
            "screenshot": rel_screenshot_path,
            "logs": logs,
            "net_errors": net_errors,
            "explanation": explanation,
            "timestamp": time.strftime("%H:%M:%S")
        })

    def add_bug(self, severity: str, simple_description: str, technical_description: str, step_number: int):
        self.bugs.append({
            "severity": severity,
            "simple_description": simple_description,
            "technical_description": technical_description,
            "step": step_number
        })

    def finalize(self, success: bool, reason: str):
        self.status = "Completed Successfully" if success else f"Terminated: {reason}"
        self.end_time = time.time()
        self.generate_markdown_report()
        self.generate_html_report()
        self.generate_pdf_report()

    def generate_markdown_report(self):
        duration = round(self.end_time - self.start_time, 1) if self.end_time else 0
        md = f"""# Test Execution Report: {self.goal}

- **Target URL:** {self.target_url}
- **Status:** {self.status}
- **Duration:** {duration}s
- **Steps Executed:** {len(self.steps)}
- **Bugs Detected:** {len(self.bugs)}

## Detected Bugs
"""
        if not self.bugs:
            md += "No bugs detected.\n\n"
        else:
            for bug in self.bugs:
                md += f"- **[{bug['severity']}]** Step {bug['step']}:\n"
                md += f"  - **Error in simple English:** {bug['simple_description']}\n"
                md += f"  - **Technical terms:** {bug['technical_description']}\n"
            md += "\n"

        md += "## Execution History\n\n"
        for step in self.steps:
            md += f"### Step {step['number']}: {step['action'].get('action', 'Unknown').upper()}\n"
            md += f"- **Timestamp:** {step['timestamp']}\n"
            md += f"- **URL:** {step['url']}\n"
            md += f"- **Explanation:** {step['explanation']}\n"
            md += f"- **Action Details:** `{step['action']}`\n"
            if step['screenshot']:
                md += f"- **Visual:**\n\n![Step {step['number']}]({step['screenshot']})\n\n"
            if step['logs']:
                md += "- **Console Logs:**\n"
                for log in step['logs']:
                    md += f"  - `[{log['type']}]` {log['text']}\n"
            if step['net_errors']:
                md += "- **Network Errors:**\n"
                for err in step['net_errors']:
                    md += f"  - `{err['url']}`: {err['error']}\n"
            md += "---\n\n"

        with open(os.path.join(self.output_dir, "report.md"), "w", encoding="utf-8") as f:
            f.write(md)

    def generate_html_report(self):
        duration = round(self.end_time - self.start_time, 1) if self.end_time else 0
        
        # Build bug cards
        bugs_html = ""
        if self.bugs:
            for bug in self.bugs:
                badge_class = "badge-danger" if bug['severity'].lower() in ["high", "critical"] else "badge-warning"
                bugs_html += f"""
                <div class="bug-card">
                    <span class="badge {badge_class}">{bug['severity'].upper()}</span>
                    <strong>Step {bug['step']}:</strong><br>
                    <div style="margin-top: 6px;"><strong>Error in simple English:</strong> {bug['simple_description']}</div>
                    <div style="margin-top: 4px; color: var(--text-secondary); font-size: 0.85rem;"><strong>Technical terms:</strong> {bug['technical_description']}</div>
                </div>
                """
        else:
            bugs_html = "<p class='no-bugs'>No issues or bugs detected.</p>"

        # Build step timelines and details
        timeline_html = ""
        steps_detail_html = ""
        
        for step in self.steps:
            action_name = step['action'].get('action', 'Unknown').upper()
            action_desc = f"{action_name} - {step['action'].get('selector', '')}" if step['action'].get('selector') else action_name
            
            # Timeline entry
            timeline_html += f"""
            <div class="timeline-item" onclick="showStep({step['number']})">
                <div class="step-num">{step['number']}</div>
                <div class="step-summary">
                    <div class="step-action-title">{action_name}</div>
                    <div class="step-time">{step['timestamp']}</div>
                </div>
            </div>
            """
            
            # Console logs HTML
            console_html = ""
            if step['logs']:
                for log in step['logs']:
                    log_class = "log-error" if log['type'] in ["error", "exception"] else "log-warn" if log['type'] == "warning" else ""
                    console_html += f"<div class='log-entry {log_class}'>[{log['type'].upper()}] {log['text']}</div>"
            else:
                console_html = "<div class='log-empty'>No console logs.</div>"

            # Network errors HTML
            net_html = ""
            if step['net_errors']:
                for err in step['net_errors']:
                    net_html += f"<div class='log-entry log-error'>FAIL: {err['url']} ({err['error']})</div>"
            else:
                net_html = "<div class='log-empty'>No network errors.</div>"

            # Screenshot HTML
            screenshot_html = ""
            if step['screenshot']:
                screenshot_html = f"""
                <div class="screenshot-container">
                    <img src="{step['screenshot']}" alt="Step {step['number']} Screenshot" class="screenshot-img">
                </div>
                """

            steps_detail_html += f"""
            <div id="step-detail-{step['number']}" class="step-detail-card" style="display: none;">
                <div class="detail-header">
                    <h2>Step {step['number']}: {action_desc}</h2>
                    <span class="step-url">{step['url']}</span>
                </div>
                <div class="detail-body">
                    <div class="detail-info">
                        <div class="info-block">
                            <h3>Reasoning</h3>
                            <p>{step['explanation']}</p>
                        </div>
                        <div class="info-block">
                            <h3>Action Parameters</h3>
                            <pre><code>{self._to_pretty_json(step['action'])}</code></pre>
                        </div>
                        <div class="info-block">
                            <h3>Console Output</h3>
                            <div class="logs-pane">{console_html}</div>
                        </div>
                        <div class="info-block">
                            <h3>Network Issues</h3>
                            <div class="logs-pane">{net_html}</div>
                        </div>
                    </div>
                    {screenshot_html}
                </div>
            </div>
            """

        bug_color = 'var(--danger)' if self.bugs else 'var(--success)'
        
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Autonomous Browser Test Execution</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #000000;
            --bg-secondary: #111111;
            --bg-tertiary: #1c1c1c;
            --text-primary: #ffffff;
            --text-secondary: #888888;
            --accent: #ffffff;
            --accent-hover: #e5e5e5;
            --border: #2c2c2c;
            --danger: #ffffff;
            --warning: #ffffff;
            --success: #ffffff;
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        body {
            background: var(--bg-primary);
            color: var(--text-primary);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        /* Sidebar Styles */
        .sidebar {
            width: 320px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        .sidebar-header {
            padding: 24px;
            border-bottom: 1px solid var(--border);
        }
        .sidebar-header h1 {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 8px;
        }
        .meta-info {
            font-size: 0.85rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }
        .timeline {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }
        .timeline-item {
            display: flex;
            align-items: center;
            padding: 12px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            margin-bottom: 10px;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.2s ease;
        }
        .timeline-item:hover {
            border-color: var(--accent);
            transform: translateX(4px);
        }
        .timeline-item.active {
            background: var(--accent);
            color: #000000;
        }
        .timeline-item.active .step-time,
        .timeline-item.active .step-action-title {
            color: #000000;
        }
        .step-num {
            width: 32px;
            height: 32px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            margin-right: 12px;
            font-size: 0.9rem;
        }
        .step-summary {
            flex: 1;
        }
        .step-action-title {
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-primary);
        }
        .step-time {
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 2px;
        }
        /* Main Panel Styles */
        .main-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            height: 100%;
            overflow-y: auto;
            padding: 32px;
        }
        .overview-section {
            margin-bottom: 32px;
        }
        .overview-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }
        .metric-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        .metric-card h4 {
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        .metric-card p {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .metric-card .status-val {
            color: var(--text-primary);
            font-size: 1.1rem;
        }
        /* Bug Panel */
        .bugs-section {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 32px;
        }
        .bugs-section h3 {
            color: var(--text-primary);
            margin-bottom: 16px;
        }
        .bug-card {
            display: block;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 12px;
        }
        .badge {
            padding: 4px 8px;
            font-size: 0.75rem;
            font-weight: 700;
            border-radius: 4px;
            margin-right: 12px;
            display: inline-block;
        }
        .badge-danger {
            background: #ffffff;
            color: #000000;
            border: 1px solid #ffffff;
        }
        .badge-warning {
            background: transparent;
            color: #ffffff;
            border: 1px solid var(--border);
        }
        .no-bugs {
            color: var(--text-secondary);
            font-weight: 500;
        }
        /* Step Detail Styles */
        .step-detail-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            margin-top: 16px;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .detail-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        .step-url {
            font-size: 0.85rem;
            color: var(--text-primary);
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            padding: 4px 12px;
            border-radius: 100px;
        }
        .detail-body {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }
        .detail-info {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .info-block h3 {
            font-size: 0.95rem;
            color: var(--text-secondary);
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .info-block p {
            font-size: 1rem;
            line-height: 1.6;
        }
        pre {
            background: var(--bg-tertiary);
            padding: 12px;
            border-radius: 8px;
            overflow-x: auto;
            border: 1px solid var(--border);
        }
        code {
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.85rem;
        }
        .logs-pane {
            background: var(--bg-tertiary);
            border-radius: 8px;
            border: 1px solid var(--border);
            max-height: 150px;
            overflow-y: auto;
            padding: 10px;
        }
        .log-entry {
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.8rem;
            padding: 4px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            color: var(--text-secondary);
        }
        .log-error {
            color: #ffffff;
            font-weight: bold;
        }
        .log-warn {
            color: var(--text-secondary);
        }
        .log-empty {
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-style: italic;
        }
        .screenshot-container {
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-tertiary);
        }
        .screenshot-img {
            max-width: 100%;
            height: auto;
            display: block;
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-header">
            <h1>AI Agent Tester</h1>
            <div class="meta-info">
                <div>Goal: <strong>__GOAL__</strong></div>
                <div>Target: __TARGET__</div>
            </div>
        </div>
        <div class="timeline">
            __TIMELINE__
        </div>
    </div>
    <div class="main-panel">
        <div class="overview-section">
            <h2>Execution Overview</h2>
            <div class="overview-grid">
                <div class="metric-card">
                    <h4>Status</h4>
                    <p class="status-val">__STATUS__</p>
                </div>
                <div class="metric-card">
                    <h4>Duration</h4>
                    <p>__DURATION__s</p>
                </div>
                <div class="metric-card">
                    <h4>Steps Executed</h4>
                    <p>__STEPS_COUNT__</p>
                </div>
                <div class="metric-card">
                    <h4>Bugs Found</h4>
                    <p style="color: __BUG_COLOR__">__BUGS_COUNT__</p>
                </div>
            </div>
        </div>

        <div class="bugs-section">
            <h3>Bugs & Issues</h3>
            __BUGS_HTML__
        </div>

        <div class="details-section">
            <h3>Step Execution Details</h3>
            __DETAILS_HTML__
        </div>
    </div>

    <script>
        function showStep(stepNum) {
            // Hide all details
            const cards = document.querySelectorAll('.step-detail-card');
            cards.forEach(card => card.style.display = 'none');
            
            // Remove active class from timeline
            const items = document.querySelectorAll('.timeline-item');
            items.forEach(item => item.classList.remove('active'));
            
            // Show selected detail
            const targetCard = document.getElementById('step-detail-' + stepNum);
            if (targetCard) {
                targetCard.style.display = 'block';
            }
            
            // Highlight active timeline item
            const activeItem = document.querySelector('.timeline-item:nth-child(' + stepNum + ')');
            if (activeItem) {
                activeItem.classList.add('active');
            }
        }
        
        // Auto-show first step on load
        if (__STEPS_COUNT__ > 0) {
            showStep(1);
        }
    </script>
</body>
</html>
"""
        html = html.replace("__GOAL__", self.goal)
        html = html.replace("__TARGET__", self.target_url)
        html = html.replace("__TIMELINE__", timeline_html)
        html = html.replace("__STATUS__", self.status)
        html = html.replace("__DURATION__", str(duration))
        html = html.replace("__STEPS_COUNT__", str(len(self.steps)))
        html = html.replace("__BUG_COLOR__", bug_color)
        html = html.replace("__BUGS_COUNT__", str(len(self.bugs)))
        html = html.replace("__BUGS_HTML__", bugs_html)
        html = html.replace("__DETAILS_HTML__", steps_detail_html)

        with open(os.path.join(self.output_dir, "report.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def _to_pretty_json(self, d: dict) -> str:
        try:
            return json.dumps(d, indent=2)
        except Exception:
            return str(d)

    def generate_pdf_report(self):
        duration = round(self.end_time - self.start_time, 1) if self.end_time else 0
        
        # Build bugs HTML
        bugs_html = ""
        if self.bugs:
            for bug in self.bugs:
                bugs_html += f"""
                <div class="bug-card">
                    <strong>[{bug['severity'].upper()}] Step {bug['step']}:</strong><br>
                    <p style="margin: 4px 0 2px 0;"><strong>Error in simple English:</strong> {bug['simple_description']}</p>
                    <p style="margin: 0; color: #64748b; font-size: 13px;"><strong>Technical terms:</strong> {bug['technical_description']}</p>
                </div>
                """
        else:
            bugs_html = "<p style='color: #10b981; font-weight: 500;'>No bugs detected.</p>"

        # Build steps HTML
        steps_html = ""
        for step in self.steps:
            action_name = step['action'].get('action', 'Unknown').upper()
            action_desc = f"{action_name} - {step['action'].get('selector', '')}" if step['action'].get('selector') else action_name
            
            screenshot_html = ""
            if step['screenshot']:
                abs_screenshot = os.path.abspath(os.path.join(self.output_dir, step['screenshot']))
                screenshot_html = f'<img class="screenshot" src="file://{abs_screenshot}" alt="Step {step["number"]} Screenshot">'

            steps_html += f"""
            <div class="step-card">
                <div class="step-header">
                    <span class="step-num">Step {step['number']}: {action_desc}</span>
                    <span style="color: #64748b; font-size: 13px;">{step['timestamp']}</span>
                </div>
                <p><strong>Reasoning:</strong> {step['explanation']}</p>
                <p><strong>URL:</strong> <span style="color: #6366f1; font-size: 13px;">{step['url']}</span></p>
                {screenshot_html}
            </div>
            """

        pdf_html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Test Execution Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Plus Jakarta Sans', sans-serif;
            color: #1e293b;
            padding: 40px;
            background: #ffffff;
            line-height: 1.5;
        }}
        h1 {{
            font-size: 26px;
            color: #0b0f19;
            margin-bottom: 20px;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 12px;
        }}
        h2 {{
            font-size: 18px;
            color: #0b0f19;
            margin-top: 30px;
            margin-bottom: 15px;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 6px;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
            margin-bottom: 30px;
        }}
        .meta-item {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 12px;
            border-radius: 8px;
        }}
        .meta-item strong {{
            display: block;
            font-size: 11px;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }}
        .meta-item span {{
            font-size: 15px;
            font-weight: 600;
            color: #0b0f19;
        }}
        .bug-card {{
            background: #fef2f2;
            border: 1px solid #fee2e2;
            border-left: 4px solid #ef4444;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 14px;
        }}
        .step-card {{
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            page-break-inside: avoid;
            background: #ffffff;
        }}
        .step-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 10px;
            margin-bottom: 12px;
        }}
        .step-num {{
            font-weight: 700;
            color: #6366f1;
            font-size: 15px;
        }}
        .screenshot {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            margin-top: 16px;
            display: block;
        }}
    </style>
</head>
<body>
    <h1>Test Execution Report</h1>
    
    <div class="meta-grid">
        <div class="meta-item">
            <strong>Goal / Objective</strong>
            <span>{self.goal}</span>
        </div>
        <div class="meta-item">
            <strong>Target URL</strong>
            <span>{self.target_url}</span>
        </div>
        <div class="meta-item">
            <strong>Status</strong>
            <span>{self.status}</span>
        </div>
        <div class="meta-item">
            <strong>Execution Metrics</strong>
            <span>Duration: {duration}s | Steps: {len(self.steps)}</span>
        </div>
    </div>

    <h2>Bugs & Issues Detected</h2>
    {bugs_html}

    <h2>Execution Step Log</h2>
    {steps_html}
</body>
</html>
"""
        
        temp_html_path = os.path.join(self.output_dir, "report_pdf_temp.html")
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(pdf_html_content)

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(f"file://{os.path.abspath(temp_html_path)}")
                page.wait_for_load_state("networkidle")
                time.sleep(1.5)
                pdf_path = os.path.join(self.output_dir, "report.pdf")
                page.pdf(path=pdf_path, format="A4", print_background=True, margin={"top": "20px", "bottom": "20px", "left": "20px", "right": "20px"})
                browser.close()
        except Exception as e:
            print(f"Error printing PDF report with Playwright: {e}")
        finally:
            if os.path.exists(temp_html_path):
                os.remove(temp_html_path)

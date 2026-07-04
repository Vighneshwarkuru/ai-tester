import argparse
import os
from agent import Agent

def main():
    parser = argparse.ArgumentParser(description="Autonomous AI Browser Testing Agent")
    parser.add_argument("--url", type=str, default="https://example.com", help="Target URL (can be http/https or file:// absolute path)")
    parser.add_argument("--goal", type=str, default="Explore the homepage and verify the Learn More link works.", help="Testing goal for the agent")
    parser.add_argument("--steps", type=int, default=10, help="Maximum number of testing steps/actions")
    parser.add_argument("--model", type=str, default="qwen2.5-coder:7b", help="Local Ollama model name")
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434", help="Ollama instance API endpoint")
    parser.add_argument("--headless", action="store_true", help="Run the browser in headless mode")
    parser.add_argument("--ui", action="store_true", help="Run the web UI dashboard server")
    parser.add_argument("--port", type=int, default=8000, help="Port for the web UI server")

    args = parser.parse_args()

    if args.ui:
        import uvicorn
        print(f"Starting Web UI server on http://localhost:{args.port}...")
        uvicorn.run("server:app", host="0.0.0.0", port=args.port, reload=True)
        return

    # Convert relative paths to file:// schema if url refers to a local file
    url = args.url
    if os.path.exists(url):
        url = "file://" + os.path.abspath(url)

    agent = Agent(
        target_url=url,
        goal=args.goal,
        max_steps=args.steps,
        ollama_url=args.ollama_url,
        model=args.model,
        headless=args.headless
    )
    
    agent.run()

if __name__ == "__main__":
    main()
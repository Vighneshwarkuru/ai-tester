import json
import urllib.request
import urllib.error

class Brain:
    def __init__(self, ollama_url="http://localhost:11434", model="qwen2.5-coder:7b"):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model

    def query(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Sends a query to local Ollama and expects a JSON response.
        """
        url = f"{self.ollama_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "options": {
                "temperature": 0.1
            },
            "stream": False,
            "format": "json"
        }
        
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                res_data = response.read().decode("utf-8")
                res_json = json.loads(res_data)
                content = res_json["message"]["content"].strip()
                
                # Attempt to parse the content as JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # Clean up common LLM markdown formatting if any
                    if content.startswith("```json"):
                        content = content.split("```json", 1)[1]
                    if content.endswith("```"):
                        content = content.rsplit("```", 1)[0]
                    return json.loads(content.strip())
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to communicate with local Ollama at {self.ollama_url}: {e}. Make sure Ollama is running.")
        except Exception as e:
            raise RuntimeError(f"Error querying Brain model: {e}")

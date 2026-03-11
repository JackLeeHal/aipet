from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading

class SimpleHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get('content-length', 0))
        post_body = self.rfile.read(content_len)
        try:
            data = json.loads(post_body)
            with open('request_dump.json', 'w') as f:
                json.dump(data, f, indent=2)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{}')
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            print(f"Error: {e}")

def run_server():
    server = HTTPServer(('localhost', 8080), SimpleHandler)
    server.serve_forever()

if __name__ == '__main__':
    t = threading.Thread(target=run_server)
    t.daemon = True
    t.start()

    import asyncio
    import os
    import sys
    from openai import AsyncOpenAI

    sys.path.append(os.getcwd())

    from desktop_aipet.src.skills.loader import SkillLoader
    from desktop_aipet.src.bus.event_bus import EventBus
    from desktop_aipet.src.skills.registry import SkillRegistry

    async def main():
        bus = EventBus()
        loader = SkillLoader(bus)
        skills = loader.load_skills()

        registry = SkillRegistry()
        for s in skills:
            registry.register(s)

        schemas = registry.get_schemas()

        client = AsyncOpenAI(api_key="dummy", base_url="http://localhost:8080/v1")
        try:
            await client.chat.completions.create(
                model="test",
                messages=[{"role": "user", "content": "hi"}],
                tools=schemas
            )
        except Exception as e:
            print("API Call failed (expected because of mock server):", e)

    asyncio.run(main())

    with open('request_dump.json') as f:
        req = json.load(f)
        print("Tools sent to server:")
        for t in req.get('tools', []):
            print("Tool name:", t.get('function', {}).get('name', 'MISSING!'))

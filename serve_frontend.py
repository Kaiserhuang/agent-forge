"""AgentForge frontend static server - called by start.bat"""
import http.server
import socketserver
import os

os.chdir(os.path.join(os.path.dirname(__file__), "gui", "dist-web"))
PORT = 5183


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/assets/") or self.path in ("/", "/index.html"):
            super().do_GET()
        else:
            self.path = "/index.html"
            super().do_GET()


with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), SPAHandler) as s:
    print(f"Frontend: http://127.0.0.1:{PORT}")
    s.serve_forever()

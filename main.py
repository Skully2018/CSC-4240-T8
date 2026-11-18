"""Start the local-only RMR browser interface."""
import argparse
import errno
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Timer
import webbrowser

from recipe_agent import ProviderError, recommend

WEB = Path(__file__).resolve().parent / "web"


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/recommend":
            return self.reply(404, {"message": "Unknown endpoint."})
        if self.headers.get_content_type() != "application/json":
            return self.reply(415, {"message": "Send a JSON household request."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 196608:
                return self.reply(400, {"message": "Invalid request size."})
            result = recommend(json.loads(self.rfile.read(size)))
        except ValueError as exc:
            return self.reply(400, {"message": str(exc)})
        except ProviderError as exc:
            return self.reply(502, {"message": str(exc)})
        self.reply(200, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, help="Use an explicit port (default: first available starting at 8765)")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    ports = [args.port] if args.port is not None else range(8765, 8781)
    for port in ports:
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(WEB)))
            break
        except OSError as exc:
            if args.port is not None or exc.errno not in (errno.EADDRINUSE, 10048):
                parser.exit(1, f"Cannot start RMR on port {port}: {exc}\n")
    else:
        parser.exit(1, "Ports 8765 through 8780 are busy. Close a previous server or specify --port.\n")
    with server:
        url = f"http://127.0.0.1:{server.server_port}"
        if server.server_port != 8765:
            print("Household saves are specific to the port. For saves from port 8765, close the app using it and relaunch.")
        print(f"RMR is running at {url}. Press Ctrl+C to stop.", flush=True)
        if not args.no_browser:
            Timer(0.4, webbrowser.open, args=(url,)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

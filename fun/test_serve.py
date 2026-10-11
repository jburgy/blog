from http.server import HTTPServer
from threading import Thread
from urllib.request import urlopen

from fun.serve import CORSRequestHandler


def test_cors_headers():
    """Serving a single request should send the CORS headers end_headers adds."""
    server = HTTPServer(("127.0.0.1", 0), CORSRequestHandler)
    thread = Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=5) as response:
            assert response.headers["Access-Control-Allow-Origin"] == "*"
            assert response.headers["Access-Control-Allow-Methods"] == "GET"
            assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
            assert response.headers["Cross-Origin-Embedder-Policy"] == "require-corp"
    finally:
        thread.join(timeout=5)
        server.server_close()

from contextlib import suppress
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer, test
from socket import IPPROTO_IPV6, IPV6_V6ONLY


class HTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()


class DualStackServer(ThreadingHTTPServer):
    def server_bind(self):
        # suppress exception when protocol is IPv4
        with suppress(Exception):
            self.socket.setsockopt(IPPROTO_IPV6, IPV6_V6ONLY, 0)
        return super().server_bind()

    def finish_request(self, request, client_address):
        self.RequestHandlerClass(request, client_address, self)


if __name__ == "__main__":
    test(
        HandlerClass=HTTPRequestHandler,
        ServerClass=DualStackServer,
        port=8000,
        protocol="HTTP/1.0",
    )

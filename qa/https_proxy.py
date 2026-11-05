"""Proxy TLS tối giản giả lập Cloudflare Tunnel: nghe https://127.0.0.1:PORT, chuyển tới origin 127.0.0.1:8014,
giữ Host, ghi đè CF-Connecting-IP (như Cloudflare). Dùng: python https_proxy.py <cert> <key> <port> <origin_port>"""
import http.client
import ssl
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def forward(self):
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n) if n else None
        hdr = {k: v for k, v in self.headers.items() if k.lower() not in ("connection", "cf-connecting-ip", "accept-encoding")}
        hdr["CF-Connecting-IP"] = self.client_ip()
        hdr["X-Forwarded-Proto"] = "https"
        c = http.client.HTTPConnection("127.0.0.1", ORIGIN, timeout=30)
        c.request(self.command, self.path, body, hdr)
        r = c.getresponse()
        data = r.read()
        self.send_response(r.status)
        for k, v in r.getheaders():
            if k.lower() not in ("connection", "transfer-encoding", "content-length"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        c.close()

    def client_ip(self):
        return self.headers.get("X-Test-Real-IP") or "203.0.113.9"

    do_GET = do_POST = do_HEAD = forward

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    cert, key, port, ORIGIN = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    assert port != 8000 and ORIGIN != 8000
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    srv.serve_forever()

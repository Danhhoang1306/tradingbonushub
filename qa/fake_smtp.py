"""Bộ nhận SMTP tối giản chỉ cho QA: nghe localhost, hỗ trợ STARTTLS, lưu thư vào RAM, không chuyển tiếp đi đâu."""
import socket
import ssl
import threading


class FakeSMTP:
    def __init__(self, cert, key, port, refuse=()):
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(cert, key)
        self.port, self.refuse = port, set(refuse)
        self.msgs, self.tls, self.running = [], False, False

    def start(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.listen(16)
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        if self.running:
            self.running = False
            self.sock.close()

    def _loop(self):
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        send = lambda c, s: c.sendall(s.encode() + b"\r\n")
        send(conn, "220 qa ESMTP")
        f = conn.makefile("rb")
        try:
            while True:
                line = f.readline().decode("utf-8", "replace").strip()
                if not line:
                    return
                cmd = line.upper()
                if cmd.startswith("EHLO") or cmd.startswith("HELO"):
                    conn.sendall(b"250-qa\r\n250-STARTTLS\r\n250-SMTPUTF8\r\n250 8BITMIME\r\n")
                elif cmd == "STARTTLS":
                    send(conn, "220 go")
                    conn = self.ctx.wrap_socket(conn, server_side=True)
                    f = conn.makefile("rb")
                    self.tls = True
                elif cmd.startswith("RCPT"):
                    addr = line.split("<")[-1].split(">")[0].lower()
                    send(conn, "550 refused" if addr in self.refuse else "250 ok")
                elif cmd == "DATA":
                    send(conn, "354 go")
                    buf = []
                    while (d := f.readline()) not in (b".\r\n", b""):
                        buf.append(d)
                    self.msgs.append(b"".join(buf).decode("utf-8", "replace"))
                    send(conn, "250 ok")
                elif cmd == "QUIT":
                    send(conn, "221 bye")
                    return
                else:
                    send(conn, "250 ok")
        except (OSError, ssl.SSLError):
            pass
        finally:
            conn.close()

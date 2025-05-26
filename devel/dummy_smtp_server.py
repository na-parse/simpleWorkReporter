#!/usr/bin/python3
import socket
import threading

class DummySMTPServer:
    def __init__(self, host='127.0.0.1', port=25):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def handle_client(self, client_socket, address):
        print(f"Connection from {address}")
        
        # Send greeting
        client_socket.send(b"220 localhost SMTP Ready\r\n")
        
        while True:
            try:
                data = client_socket.recv(1024).decode('utf-8').strip()
                if not data:
                    break
                
                print(f"Received: {data}")
                
                if data.upper().startswith('HELO') or data.upper().startswith('EHLO'):
                    client_socket.send(b"250 localhost\r\n")
                elif data.upper().startswith('MAIL FROM:'):
                    client_socket.send(b"250 OK\r\n")
                elif data.upper().startswith('RCPT TO:'):
                    client_socket.send(b"250 OK\r\n")
                elif data.upper() == 'DATA':
                    client_socket.send(b"354 Start mail input; end with <CRLF>.<CRLF>\r\n")
                elif data == '.':
                    client_socket.send(b"250 OK: Message accepted\r\n")
                elif data.upper() == 'QUIT':
                    client_socket.send(b"221 Bye\r\n")
                    break
                else:
                    client_socket.send(b"250 OK\r\n")
                    
            except Exception as e:
                print(f"Error: {e}")
                break
        
        client_socket.close()
        print(f"Connection closed: {address}")

    def start(self):
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        print(f"SMTP server listening on {self.host}:{self.port}")
        
        try:
            while True:
                client_socket, address = self.socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("Stopping SMTP server")
        finally:
            self.socket.close()

if __name__ == '__main__':
    server = DummySMTPServer(host='0.0.0.0')
    server.start()

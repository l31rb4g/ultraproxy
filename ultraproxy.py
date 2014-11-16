#!/usr/bin/python
#v0.1
import os
import re
import sys
import socket
import zlib
import threading


class UltraProxy:

    debug = False

    def __init__(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', 8081))
        self.sock.listen(10)

        self.listen()

    def listen(self):
        if self.debug:
            print('Listening on port 8081...\n')

        while True:
            newconn = self.sock.accept()
            th = threading.Thread(target=UltraConnection, args=(self.debug, newconn))
            th.start()


class UltraConnection:

    debug = False
    request_headers = {}
    response_headers = {}
    dest_host = None
    dest_port = 80
    client_request = ''
    server_response = ''
    client_connection = None
    method = None
    addr = None

    def __init__(self, debug, sock):
        self.debug = debug
        self.sock = sock
        self.client_connection = sock[0]
        self.addr = sock[1]

        self.read_client()
        self.request_server()
        self.forward()

    def read_client(self):
        if self.debug:
            print('>>> Client connected ' + str(self.addr) + '\n')

        self.client_request = self.client_connection.recv(4096)

        _headers = self.client_request.replace('\r', '').split('\n')
        self.method = _headers.pop(0)

        for header in _headers:
            h = header.split(': ')
            if len(h) == 2:
                self.request_headers[h[0].lower()] = h[1]

        if 'cookie' in self.request_headers:
            del(self.request_headers['cookie'])

        if 'host' in self.request_headers:
            dest = self.request_headers['host'].split(':')
            self.dest_host = dest[0]
            if len(dest) == 2:
                self.dest_port = int(dest[1])
            else:
                self.dest_port = 80

    def request_server(self):
        if not self.dest_host:
            return

        if self.debug:
            print('>>> Requesting server ' + self.dest_host + ':' + str(self.dest_port) + ' ...'),

        is_gzip = False
        conn2 = socket.socket()
        conn2.settimeout(3)
        conn2.connect((self.dest_host, self.dest_port))
        out = self.method + '\n'
        for h in self.request_headers:
            out += h.title() + ': ' + self.request_headers[h] + '\n'
        out += '\n'

        if self.debug:
            print('OK\n')
            print(out)
            print('-------------------')

        conn2.send(out)

        _r = conn2.recv(4096)
        content = _r.split('\r\n\r\n')
        raw_response_headers = content[0]
        _headers = content.pop(0).split('\n')
        _body = '\n\n'.join(content)

        for header in _headers:
            h = header.split(': ')
            if len(h) == 2:
                self.response_headers[h[0].lower()] = h[1]

        if 'content-length' in self.response_headers:
            if len(_body) < int(self.response_headers['content-length']):
                while True:
                    try:
                        _r = conn2.recv(4096)
                    except:
                        conn2.close()
                        break

                    if not _r:
                        break

                    _body += _r

                    if 'content-length' in self.response_headers:
                        if len(_body) >= int(self.response_headers['content-length']):
                            break

        if 'content-encoding' in self.response_headers:
            encs = self.response_headers['content-encoding'].split(',')
            for enc in encs:
                if enc.strip() == 'gzip':
                    is_gzip = True

        if self.debug:
            print(raw_response_headers)

        if _body:
            if self.debug:
                print('\n>>> Response body:\n----------------------\n')

            if is_gzip:
                try:
                    _body = zlib.decompress(_body, 16+zlib.MAX_WBITS)
                except:
                    pass
            if self.debug:
                print(_body)
                print('----------------------')

            self.server_response = _body
        else:
            if self.debug:
                print('\n-- No body in the response --')
            self.server_response = ''

    def forward(self):
        if self.debug:
            print('\n\n>>> Forwarding...'),

        try:
            self.client_connection.send(self.server_response)
            self.client_connection.close()
        except IOError:
            if self.debug:
                print('Client gone')

        if self.debug:
            print('OK')
            print(('=' * 30) + '\n\n')

        sys.exit()


if __name__ == '__main__':
    UltraProxy()
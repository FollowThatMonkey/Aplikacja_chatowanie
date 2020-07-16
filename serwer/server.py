import sqlite3
import socket
import re
import os
import threading
import logging
import traceback

DB_PATH = os.path.dirname(os.path.abspath(__file__)) + '/users.db'
BUFF_SIZE = 1024
ENCODING = 'utf-8'

DB_ERROR = 1
SOCKET_ERROR = 2
KEYBOARD_ERROR = 3


class Message:
    def __init__(self):
        pass


class Client:
    def __init__(self, client_sock: socket.socket, username: str):
        pass


class Server:
    REGISTER_REGEX = re.compile(r'REGISTER\s+(\w+)\s+(\S+)\s*')
    LOGIN_REGEX = re.compile(r'LOGIN\s+(\w+)\s+(\S+)\s*')
    HELP_REGEX = re.compile(r'HELP\s*')
    EXIT_REGEX = re.compile(r'EXIT\s*')

    def __init__(self, PORT: int, nConnections: int):
        self.PORT = PORT
        self.nConnections = nConnections

        self.logging_init()
        self.db_init()
        self.server_socket = self.socket_init()

        try:
            self.accept_conn()

        except KeyboardInterrupt:
            logging.error('Keyboard interrupt detected...\nShutting down...')
            self.close_server()

        finally:
            os.sys.exit(KEYBOARD_ERROR)

    def close_server(self, ERROR_CODE=None):
        logging.info('Closing socket...')
        self.server_socket.close()

    def logging_init(self) -> None:
        logging.basicConfig(format='[{asctime}] {levelname} - {message}',
                            datefmt='%d/%m/%Y %H:%M:%S', style='{', level=0)

    def db_init(self) -> None:
        try:
            logging.info('Initializing database...')
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """ CREATE TABLE IF NOT EXISTS users(
                        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL,
                        password TEXT NOT NULL,
                        CONSTRAINT username_constraint UNIQUE (username)
                    ); """
                )
                cursor.execute(
                    """ CREATE TABLE IF NOT EXISTS firends(
                        user1 INTEGER,
                        user2 INTEGER,
                        CONSTRAINT fk_column
                            FOREIGN KEY (user1, user2)
                            REFERENCES users (user_id, user_id)
                    ); """
                )
                cursor.execute(
                    """ CREATE TABLE IF NOT EXISTS messages(
                        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        body TEXT,
                        addressee INTEGER,
                        CONSTRAINT fk_column
                            FOREIGN KEY (addressee)
                            REFERENCES users (user_id)
                    ); """
                )
                conn.commit()
            logging.info('Database initialized...')

        except Exception as e:
            traceback.print_exc()
            logging.error(
                f'Database initialization error: {e}\nShutting down...')
            os.sys.exit(DB_ERROR)

    def socket_init(self) -> socket.socket:
        try:
            logging.info('Initializing server socket...')
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('localhost', self.PORT))
            server_socket.listen(self.nConnections)

            logging.info('Server socket initialized...')
            return server_socket

        except Exception as e:
            traceback.print_exc()
            logging.error(
                f'Error while initializing server socket...\nShutting down...')
            os.sys.exit(SOCKET_ERROR)

    def accept_conn(self) -> None:
        while True:
            client_sock, client_addr = self.server_socket.accept()

            logging.info(f"{client_addr} has connected...")
            th = threading.Thread(target=self.handle_conn, args=(client_sock,))
            th.start()

    def handle_conn(self, client_sock: socket.socket) -> None:
        try:
            client = self.client_init(client_sock)

            if client:
                th_send = threading.Thread()
                th_recv = threading.Thread()
                th_send.start()
                th_recv.start()
                th_send.join()
                th_recv.join()

        finally:
            client_sock.close()

    def client_init(self, client_sock: socket.socket) -> Client:
        greeting_msg = ("Welcome to the server!\n"
                        "Register by typing 'REGISTER username password' or log in by typing 'LOGIN username password'.\n"
                        "Antype you need help, just type 'HELP' :)\n").encode(ENCODING)
        client_sock.sendall(greeting_msg)

        while True:
            msg = client_sock.recv(BUFF_SIZE).decode(ENCODING)

            # case register
            match = self.REGISTER_REGEX.fullmatch(msg)
            if match:
                username, password = match.groups()
                client = self.register_client(client_sock, username, password)

                if client:
                    return client
                else:
                    continue

            # case login
            match = self.LOGIN_REGEX.fullmatch(msg)
            if match:
                username, password = match.groups()
                client = self.login_client(client_sock, username, password)

                if client:
                    return client
                else:
                    continue

            # case help
            match = self.HELP_REGEX.fullmatch(msg)
            if match:
                self.send_help(client_sock)
                continue

            # case exit
            match = self.EXIT_REGEX.fullmatch(msg)
            if match:
                self.exit_client(client_sock)
                return None

            msg = "Unknown command. Try again!\nType 'HELP' to show avaiable commands!\n".encode(
                ENCODING)
            client_sock.sendall(msg)

    def register_client(self, client_sock: socket.socket, username: str, password: str) -> Client:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """ INSERT INTO users(username, password) VALUES (
                        ?, ?
                    ); """, (username, password)
                )
                conn.commit()
                logging.info(f'Registered {username}')
                return None

        except sqlite3.IntegrityError as e:
            traceback.print_exc()
            logging.error(f"Error while registering new client: {e}")
            return None

    def login_client(self, client_sock: socket.socket, username: str, password: str) -> Client:
        pass

    def send_help(self, client_sock: socket.socket) -> None:
        pass

    def exit_client(self, client_sock: socket.socket) -> None:
        exit_mgs = "You're being disconnected from server...\n".encode(
            ENCODING)
        client_sock.sendall(exit_mgs)
        client_sock.close()


if __name__ == '__main__':
    Server(40123, 10)

# local imports
import user
# std imports
import threading
import logging
import socket
import sqlite3
import os
import sys
import re

ERROR_CODE = 1
DATABASE_LOC = os.path.dirname(os.path.realpath(__file__)) + '/users.db'
BUFF_SIZE = 1024
ENCODING = 'utf-8'


class Server:
    LOGIN_REGEX = re.compile(r'LOGIN\s+(\w+)\s+(\w+)')
    REGISTER_REGEX = re.compile(r'REGISTER\s+(\w+)\s+(\w+)')
    HELP_REGEX = re.compile(r'HELP')
    EXIT_REGEX = re.compile(r'EXIT')

    def __init__(self, PORT: int, nCONNECTIONS: int):
        self.PORT = PORT
        self.nCONNECTIONS = nCONNECTIONS

        self.logging_init()
        self.database_init()
        self.serv_sock = self.socket_init()

        try:
            self.accept_connections()

        except KeyboardInterrupt:
            logging.error('Keyboard Interrupt detected...')
            sys.exit(ERROR_CODE)

        finally:
            self.close_server()

    def logging_init(self) -> None:
        logging.basicConfig(format='[{asctime}] {levelname} - {message}',
                            datefmt='%d/%m/%Y %H:%M:%S', style='{', level=0)

    def database_init(self) -> None:
        try:
            with sqlite3.connect(DATABASE_LOC) as db_conn:
                db_cursor = db_conn.cursor()
                db_cursor.execute(
                    '''CREATE TABLE IF NOT EXISTS User(
                        IDuser INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        username TEXT TYPE UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        status INTEGER
                        );'''
                )
                db_cursor.execute(
                    '''CREATE TABLE IF NOT EXISTS Friend(
                        IDuser INTEGER,
                        IDfriend INTEGER,
                        FOREIGN KEY(IDuser, IDfriend) REFERENCES User(IDuser, IDuser)
                    );'''
                )
                db_cursor.execute(
                    '''CREATE TABLE IF NOT EXISTS Message(
                        IDmessage INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        message TEXT,
                        sender INTEGER,
                        addressee INTEGER,
                        FOREIGN KEY(sender, addressee) REFERENCES User(IDuser, IDuser)
                    );'''
                )
                db_conn.commit()
                logging.info('Database loaded correctly...')

        except Exception as e:
            logging.error(f'Database error {e}. Shutting down...')
            sys.exit(ERROR_CODE)

    def socket_init(self):
        try:
            serv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            serv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            serv_sock.bind(('localhost', self.PORT))
            serv_sock.listen(self.nCONNECTIONS)
            logging.info('Socket set correctly...')

        except Exception as e:
            logging.error('Error while setting socket. Shutting down...')
            logging.error(f'{e}')
            sys.exit(ERROR_CODE)

        return serv_sock

    def accept_connections(self) -> None:
        while True:
            client_socket, client_address = self.serv_sock.accept()

            logging.info(f'{client_address} has connected...')
            th = threading.Thread(
                target=self.handle_connection, args=(client_socket,))
            th.start()

    def close_server(self) -> None:
        logging.info('Shutting down...')
        self.serv_sock.close()

    def handle_connection(self, client_socket: socket.socket) -> None:
        try:
            client = self.login_user(client_socket)
            if client:
                th_send = threading.Thread(target=client.send_msg)
                th_recv = threading.Thread(target=client.recv_msg)
                th_send.start()
                th_recv.start()
                th_send.join()
                th_recv.join()

        finally:
            logging.info(f'{client_socket.getsockname()} has disconnected...')
            client_socket.close()

    def login_user(self, client_socket: socket.socket) -> user.User:
        welcome_msg = ("Welcome to server!\n"
                       "If you want to log in type 'LOGIN USERNAME PASSWORD', or if you want to register in type 'REGISTER USERNAME PASSWORD'.\n"
                       "Anytime you need help, type 'HELP'.\n"
                       ).encode(ENCODING)
        client_socket.sendall(welcome_msg)

        finish_loop = False
        while False:
            msg = client_socket.recv(BUFF_SIZE).decode(ENCODING)

            # case login
            match = re.fullmatch(self.LOGIN_REGEX, msg)
            if match:
                username, password = match.groups()
                client = self.login_client(username, password)

                if client:
                    return client

            # case register
            match = re.fullmatch(self.REGISTER_REGEX, msg)
            if match:
                username, password = match.groups()
                client = self.register_client(username, password)

                if client:
                    return client

            # case help
            match = re.fullmatch(self.HELP_REGEX, msg)
            if match:
                client_socket.sendall(HELP_MSG)

            # case exit
            match = re.fullmatch(self.EXIT_REGEX)
            if match:
                return None

        def login_client(self, username: str, password: str) -> user.User:
            with sqlite3.connect(DATABASE_LOC) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """ SELECT username, password FROM User WHERE username=?; """,
                    (username,)
                )
                user_search = cursor.fetchall()

        def register_client(self, username: str, password: str) -> user.User:
            pass


if __name__ == '__main__':
    Server(40123, 1)

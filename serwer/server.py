import sqlite3
import socket
import queue
import re
import os
import threading
import logging
import traceback

DB_PATH = os.path.dirname(os.path.abspath(__file__)) + '/users.db'
BUFF_SIZE = 1024
QUEUE_SIZE = 1000
ENCODING = 'utf-8'

DB_ERROR = 1
SOCKET_ERROR = 2
KEYBOARD_ERROR = 3


class Message:
    def __init__(self, msg_body: str, final_msg: bool = False):
        self.msg_body = (msg_body + '\n').encode(ENCODING)
        self.final_msg = final_msg

    def get_body(self):
        return self.msg_body

    def is_final(self):
        return self.final_msg


class Client:
    HELP_MSG = ("Avaiable commands:\n"
                "* 'USERNAME: text' - to send message,\n"
                "* 'ADD username' - to add user to friends list,\n"
                "* 'DELETE username' - to remove user from friends list,\n"
                "* 'STATUS' - to show online users,\n"
                "* 'HELP' - to show avaiable commands,\n"
                "* 'EXIT' - to exit from the server.\n")

    SEND_REGEX = re.compile(r'(\w+):\s+(.*)', re.DOTALL)
    ADD_FRIEND_REGEX = re.compile(r'ADD\s+(\w+)\s*')
    DELETE_FRIEND_REGEX = re.compile(r'DELETE\s+(\w+)\s*')
    STATUS_REGEX = re.compile(r'STATUS\s*')
    HELP_REGEX = re.compile(r'HELP\s*')
    EXIT_REGEX = re.compile(r'EXIT\s*')

    def __init__(self, online_dict: dict, client_sock: socket.socket, username: str):
        self.online_dict = online_dict
        self.client_sock = client_sock
        self.username = username
        self.msg_queue = queue.Queue(QUEUE_SIZE)

        self.load_msg()

    def load_msg(self) -> None:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """ SELECT body
                        FROM messages
                        WHERE addressee = (
                            SELECT user_id FROM users WHERE username = (?)
                        )
                        ORDER BY message_id ASC; """,
                    (self.username,)
                )
                query_result = cursor.fetchall()

                for msg in query_result:
                    msg_body, = msg
                    self.msg_queue.put(Message(msg_body))

                cursor.execute(
                    """ DELETE FROM messages
                        WHERE addressee = (
                            SELECT user_id FROM users WHERE username = (?)
                        ); """,
                    (self.username,)
                )
                conn.commit()

        except Exception as e:
            traceback.print_exc()
            logging.error(
                f'Cannot put msg to queue in user {self.username}. Error: {e}')

    def send_msg(self, msg_body: str, final_msg: bool = False) -> None:
        self.msg_queue.put(Message(msg_body, final_msg))

    def _sending_thread(self) -> None:
        try:
            msg = self.msg_queue.get()

            while not msg.is_final():
                self.client_sock.sendall(msg.get_body())
                msg = self.msg_queue.get()

        except Exception as e:
            traceback.print_exc()
            logging.error(
                f'Error in sending thread of {self.username}. Error: {e}')

        finally:
            self.client_sock.close()

    def _receiving_thread(self) -> None:
        try:
            finish = False
            while not finish:
                msg = self.client_sock.recv(BUFF_SIZE).decode(ENCODING)

                if msg == '':
                    raise RuntimeError('Socket connection broken')

                finish = self._handle_msg(msg.rstrip())

        except Exception as e:
            traceback.print_exc()
            logging.error(
                f'Error in recv thread of {self.username}. Error: {e}')
            self.msg_queue.put(Message('', True))
            self.client_sock.close()

    def _handle_msg(self, msg: str) -> bool:
        # send msg to user
        match = self.SEND_REGEX.fullmatch(msg)
        if match:
            addressee, msg = match.groups()
            self._send_msg_to(addressee, msg)
            return False

        # add friend
        match = self.ADD_FRIEND_REGEX.fullmatch(msg)
        if match:
            friend_name, = match.groups()
            self._add_friend(friend_name)
            return False

        # delete friend
        match = self.DELETE_FRIEND_REGEX.fullmatch(msg)
        if match:
            friend_name, = match.groups()
            self._delete_friend(friend_name)
            return False

        # check status (are firends online)
        match = self.STATUS_REGEX.fullmatch(msg)
        if match:
            self._check_status()
            return False

        # help
        match = self.HELP_REGEX.fullmatch(msg)
        if match:
            self._send_help()
            return False

        # exit
        match = self.EXIT_REGEX.fullmatch(msg)
        if match:
            self._exit()
            return True

        # unknown command
        msg = "Unknown command. Type 'HELP' to show avaiable commands!"
        self.send_msg(msg)
        return False

    def _send_msg_to(self, addressee: str, msg_body: str) -> None:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """ SELECT user_id FROM users 
                        WHERE username = (?); """,
                    (addressee,)
                )
                query_result = cursor.fetchall()

                if query_result:
                    addressee_id, = query_result[0]
                    cursor.execute(
                        """ SELECT user_id FROM users
                            WHERE username = (?); """,
                        (self.username,)
                    )
                    user_id, = cursor.fetchall()[0]

                    cursor.execute(
                        """ SELECT user1 FROM friends
                            WHERE user1 = (?)
                            AND user2 = (?); """,
                        (user_id, addressee_id)
                    )
                    query_result = cursor.fetchall()

                    if query_result:
                        cursor.execute(
                            """ SELECT user1 FROM friends
                                WHERE user1 = (?)
                                AND user2 = (?); """,
                            (addressee_id, user_id)
                        )
                        query_result = cursor.fetchall()

                        if query_result:
                            # check if addressee is online and send msg
                            msg = self.username + ': ' + msg_body
                            if addressee in self.online_dict:
                                # send msg
                                self.online_dict[addressee].send_msg(msg)
                                logging.info(
                                    f"{self.username} sent message to {addressee}...")

                            else:
                                # addressee is offline
                                self.send_msg(
                                    f"{addressee} is offline. Adding msg to his queue!")
                                # add msg to his queue
                                cursor.execute(
                                    """ INSERT INTO messages(body, addressee) VALUES (
                                        (?), (?)
                                    ); """,
                                    (msg, addressee_id)
                                )
                                conn.commit()

                        else:
                            # addressee doesnt have you in friends list
                            self.send_msg(
                                f"{addressee} doesn't have you in his friends list! Cannot send message!")

                    else:
                        # you don't have addressee in friends list
                        self.send_msg(
                            f"You don't have {addressee} in your friends list! Cannot send message!")

                else:
                    # addressee doesn't exist
                    self.send_msg(
                        f"User {addressee} doesn't exist! Try again!")

        except Exception as e:
            traceback.print_exc()
            logging.error(
                f"Error while sending message from {self.username} to {addressee}. Error: {e}")

    def _add_friend(self, friend_name: str) -> None:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """ SELECT user_id FROM users
                        WHERE username = (?); """,
                    (friend_name,)
                )
                query_result = cursor.fetchall()
                if query_result:
                    friend_id, = query_result[0]
                    cursor.execute(
                        """ SELECT user_id FROM users
                            WHERE username = (?); """,
                        (self.username,)
                    )
                    user_id, = cursor.fetchall()[0]

                    cursor.execute(
                        """ SELECT user1 FROM friends
                            WHERE user1 = (?)
                            AND user2 = (?); """,
                        (user_id, friend_id)
                    )
                    query_result = cursor.fetchall()

                    if not query_result:
                        cursor.execute(
                            """ INSERT INTO friends(user1, user2) VALUES (
                                (?), (?)
                            ); """,
                            (user_id, friend_id)
                        )
                        conn.commit()
                        msg = f"Added {friend_name} to friends list!"
                    else:
                        # you already have friends in your friends list
                        msg = f"You already have {friend_name} in your friends list!"

                else:
                    # user 'friend' doesnt exist
                    msg = f"User {friend_name} doesn't exist!"

                self.send_msg(msg)

        except Exception as e:
            traceback.print_exc()
            logging.error(
                f"Error while adding new friend to {self.username} friends list. Error: {e}")

    def _delete_friend(self, friend_name: str) -> None:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """ SELECT username FROM users
                        WHERE user_id = (
                            SELECT user2 FROM friends
                            WHERE user1 = (
                                SELECT user_id FROM users WHERE username = (?)
                            )
                            AND user2 = (
                                SELECT user_id FROM users WHERE username = (?)
                            )
                        ); """,
                    (self.username, friend_name)
                )
                query_result = cursor.fetchall()

                if query_result:
                    cursor.execute(
                        """ DELETE FROM friends
                            WHERE user1 = (
                                SELECT user_id FROM users WHERE username = (?)
                            )
                            AND user2 = (
                                SELECT user_id FROM users WHERE username = (?)
                            ); """,
                        (self.username, friend_name)
                    )
                    conn.commit()
                    msg = f"Deleted {friend_name} from friends."

                else:
                    msg = f"You don't have {friend_name} in your friends list."

                self.send_msg(msg)

        except Exception as e:
            traceback.print_exc()
            logging.error(
                f"Error while deleting friend of {self.username}. Error: {e}")

    def _check_status(self) -> None:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """ SELECT username FROM users 
                        WHERE user_id = (
                            SELECT user2 FROM friends
                            WHERE user1 = (
                                SELECT user_id FROM users WHERE username = (?)
                            )
                        ); """,
                    (self.username,)
                )
                query_result = cursor.fetchall()

                msg = 'Friends statuses:\n'
                for result in query_result:
                    friend, = result
                    if friend in self.online_dict:
                        msg += '*\t' + friend + '\tSTATUS: ONLINE\n'
                    else:
                        msg += '*\t' + friend + '\tSTATUS: OFFLINE\n'

                self.send_msg(msg)

        except Exception as e:
            traceback.print_exc()
            logging.error(
                f'Error while sending statuses to {self.username}. Error: {e}')

    def _send_help(self) -> None:
        try:
            self.send_msg(self.HELP_MSG)

        except Exception as e:
            traceback.print_exc()
            logging.error(
                f'Error while sending help msg to {self.username}. Error: {e}')

    def _exit(self) -> None:
        try:
            msg = 'Exiting from the server.\n'
            self.send_msg(msg)
            self.send_msg('', True)

        except Exception as e:
            traceback.print_exc()
            logging.error(f'Error while exiting {self.username}. Error: {e}')

            self.client_sock.close()

        finally:
            if self.username in self.online_dict:
                del self.online_dict[self.username]


class Server:
    HELP_MSG = ("Avaiable commands:\n"
                "* 'REGISTER username password' - to register to the server,\n"
                "* 'LOGIN username password' - to log in to the server,\n"
                "* 'HELP' - to show avaiable commands,\n"
                "* 'EXIT' - to exit from the server.\n").encode(ENCODING)

    REGISTER_REGEX = re.compile(r'REGISTER\s+(\w+)\s+(\S+)\s*')
    LOGIN_REGEX = re.compile(r'LOGIN\s+(\w+)\s+(\S+)\s*')
    HELP_REGEX = re.compile(r'HELP\s*')
    EXIT_REGEX = re.compile(r'EXIT\s*')

    def __init__(self, PORT: int, nConnections: int):
        self.PORT = PORT
        self.nConnections = nConnections
        self.online = {}

        self.logging_init()
        self.db_init()
        self.server_socket = self.socket_init()

        try:
            self.accept_conn()

        except KeyboardInterrupt:
            logging.error('Keyboard interrupt detected... Shutting down...')

        finally:
            self.close_server()

    def close_server(self):
        logging.info('Closing socket...')
        self.server_socket.shutdown(socket.SHUT_RDWR)
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
                    """ CREATE TABLE IF NOT EXISTS friends(
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
            client_address = client_sock.getsockname()
            client = self.client_init(client_sock)

            if client:
                self.online[client.username] = client
                th_send = threading.Thread(target=client._sending_thread)
                th_recv = threading.Thread(target=client._receiving_thread)
                th_send.start()
                th_recv.start()
                th_send.join()
                th_recv.join()

                if client.username in self.online:
                    del self.online[client.username]

        except Exception as e:
            traceback.print_exc()
            logging.error(f'Error occured: {e}')

        finally:
            if client:
                logging.info(
                    f'{client_address} has been disconnected...')
                if client.username in self.online:
                    del self.online[client.username]
            client_sock.close()

    def client_init(self, client_sock: socket.socket) -> Client:
        greeting_msg = ("Welcome to the server!\n"
                        "Register by typing 'REGISTER username password' or log in by typing 'LOGIN username password'.\n"
                        "Antime you need help, just type 'HELP' :)\n").encode(ENCODING)
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

                msg = "You've been successfully registered and logged in!\n".encode(
                    ENCODING)
                client_sock.sendall(msg)
                return Client(self.online, client_sock, username)

        except sqlite3.IntegrityError as e:
            msg = "Username already in use. Try different one.".encode(
                ENCODING)
            client_sock.sendall(msg)
            return None

    def login_client(self, client_sock: socket.socket, username: str, password: str) -> Client:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """ SELECT password FROM users 
                        WHERE username = (?); """,
                    (username,)
                )
                query_result = cursor.fetchall()

                if query_result:
                    query_password, = query_result[0]
                    if password == query_password:
                        # correct login
                        msg = "You've been logged in\n".encode(ENCODING)
                        client_sock.sendall(msg)
                        return Client(self.online, client_sock, username)

                    else:
                        # wrong pass
                        msg = "Wrong password! Try again!\n".encode(ENCODING)
                        client_sock.sendall(msg)

                else:
                    # unknow user
                    msg = "Wrong username! Try again!\n".encode(ENCODING)
                    client_sock.sendall(msg)

                return None

        except Exception as e:
            traceback.print_exc()
            logging.error('Error: {e}')
            return None

    def send_help(self, client_sock: socket.socket) -> None:
        client_sock.sendall(self.HELP_MSG)

    def exit_client(self, client_sock: socket.socket) -> None:
        exit_mgs = "You're being disconnected from server...\n".encode(
            ENCODING)
        client_sock.sendall(exit_mgs)
        client_sock.close()


if __name__ == '__main__':
    Server(40123, 10)

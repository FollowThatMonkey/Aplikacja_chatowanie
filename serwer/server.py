import logging
import socket
import sys
import sqlite3
import threading
import time


class Server:
    def __init__(self, PORT: int, nConnections: int):
        self.setLogging()  # Set basic logging format

        self.PORT = PORT
        self.nConnections = nConnections
        self.connections_semaphore = threading.BoundedSemaphore(nConnections)
        self.current_nConnections = 0

        self.serversocket = self.initSocket(PORT, nConnections)
        self.initDatabase()

        try:
            self.accept_connections()
        except KeyboardInterrupt:
            logging.error('Keyboard Interrupt detected')
        finally:
            logging.info('Shutting down the server...')
            self.closeServer()

    def setLogging(self) -> None:
        logging.basicConfig(format='[{asctime}] {levelname} - {message}',
                            datefmt='%d/%m/%Y %H:%M:%S', style='{', level=0)

    def initSocket(self, PORT: int, nConnections: int) -> socket.socket:
        try:
            serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            logging.info('Socket created...')
            serversocket.bind(('127.0.0.1', PORT))
            serversocket.listen()
            logging.info('Socket binded...')
        except PermissionError as e:
            logging.error('Cannot bind to this port: {}'.format(e))
            serversocket.close()
            logging.error('Server is shutting down...')
            sys.exit(1)
        except OSError as e:
            logging.error(f"Cannot bind to this port! It's in use: {e}")
            logging.info('Server is shutting down...')
            sys.exit(1)

        return serversocket

    def initDatabase(self) -> None:
        try:
            self.conn = sqlite3.connect('./users.db')
            logging.info('Connected to database')
            self.cursor = self.conn.cursor()
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS User(
                              IDuser INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                              username TEXT, 
                              password TEXT
                              );''')
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS Friends(
                              IDfriend INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                              IDuser INTEGER,
                              FOREIGN KEY(IDuser) REFERENCES User(IDuser)
                              );''')
            self.conn.commit()

        except Exception as e:
            logging.error('SQL error: {}'.format(e))
            self.closeServer()

    def closeServer(self) -> None:
        logging.info('Socket is closing...')
        self.serversocket.close()
        logging.info('Closing connection to database...')
        self.conn.close()
        logging.info('Server is shutting down...')

    def accept_connections(self) -> None:
        while True:
            client_socket, client_address = self.serversocket.accept()
            if self.connections_semaphore.acquire(False):
                logging.info(f"{client_address} has connected...")
                self.current_nConnections += 1
                th = threading.Thread(target=self.client_thread,
                                      args=(client_socket,))
                th.start()
            else:
                logging.warning(
                    f"Too many connections ({self.current_nConnections}/{self.nConnections})! {client_address} tried to connect...")
                client_socket.close()

    def client_thread(self, client_sock: socket.socket) -> None:
        try:
            pass
        finally:
            client_sock.close()
            self.connections_semaphore.release()


if __name__ == '__main__':
    Server(40123, 1)

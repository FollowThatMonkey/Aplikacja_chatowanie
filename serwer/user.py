# local imports
import message
# std imports
import socket
import queue
import re

ERROR_CODE = 1
BUFF_SIZE = 1024
ENCODING = 'utf-8'
QUEUE_SIZE = 1000


class User:
    def __init__(self, client_socket: socket.socket):
        self.client_socket = client_socket
        self.msg_queue = queue.Queue(QUEUE_SIZE)

    def send_msg(self) -> None:
        try:
            while True:
                msg = self.msg_queue.get().encode(ENCODING)

                if msg.final_msg():
                    break

                msg_text = msg.get_body().encode(ENCODING)
                self.client_socket.sendall(msg_text)

        except Exception as e:
            logging.error(f'Exception occurred {e}')

        finally:
            self.client_socket.close()

    def recv_msg(self) -> None:
        try:
            while True:
                msg = self.client_socket.recv(BUFF_SIZE).decode(ENCODING)

                if msg == '':
                    raise RuntimeError('Socket connection broken')

                self.handle_msg(msg)

        except Exception as e:
            logging.error(f'Exception occurred {e}')

        finally:
            self.client_socket.close()

    def handle_msg(self, msg: str) -> None:
        """ Function to interprete received msg """
        pass

import re

REGISTER_REGEX = re.compile(r'REGISTER\s+(\w+)\s+(\S+)\s*')
LOGIN_REGEX = re.compile(r'LOGIN\s+(\w+)\s+(\S+)\s*')
HELP_REGEX = re.compile(r'HELP\s*')
EXIT_REGEX = re.compile(r'EXIT\s*')

while True:
    msg = input('Waiting for input:\n')

    match = REGISTER_REGEX.fullmatch(msg)
    if match:
        user, pasw = match.groups()
        print(f'REGISTER_REGEX: {msg}')
        print(f'User and pass: {user}, {pasw}')

    match = LOGIN_REGEX.fullmatch(msg)
    if match:
        user, pasw = match.groups()
        print(f'LOGIN_REGEX: {msg}')
        print(f'User and pass: {user}, {pasw}')

    match = HELP_REGEX.fullmatch(msg)
    if match:
        print(f'HELP_REGEX: {msg}')

    match = EXIT_REGEX.fullmatch(msg)
    if match:
        print(f'EXIT_REGEX: {msg}')

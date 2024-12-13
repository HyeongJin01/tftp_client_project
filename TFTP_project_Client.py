import os
import sys
import socket
import argparse
from struct import pack

DEFAULT_PORT = 69
BLOCK_SIZE = 512
DEFAULT_TRANSFER_MODE = 'octet'

OPCODE = {'RRQ': 1, 'WRQ': 2, 'DATA': 3, 'ACK': 4, 'ERROR': 5}
MODE = {'netascii': 1, 'octet': 2, 'mail': 3}

ERROR_CODE = {
    0: "Not defined, see error message (if any).",
    1: "File not found.",
    2: "Access violation.",
    3: "Disk full or allocation exceeded.",
    4: "Illegal TFTP operation.",
    5: "Unknown transfer ID.",
    6: "File already exists.",
    7: "No such user."
}


def send_wrq(filename, mode):
    format = f'>h{len(filename)}sB{len(mode)}sB'
    wrq_message = pack(format, OPCODE['WRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(wrq_message, server_address)
    print(f"Sent WRQ for {filename} in {mode} mode.")


def send_rrq(filename, mode):
    format = f'>h{len(filename)}sB{len(mode)}sB'
    rrq_message = pack(format, OPCODE['RRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(rrq_message, server_address)
    print(f"Sent RRQ for {filename} in {mode} mode.")


def send_ack(seq_num, server):
    format = f'>hh'
    ack_message = pack(format, OPCODE['ACK'], seq_num)
    sock.sendto(ack_message, server)
    print(f"Sent ACK for block number {seq_num}")


parser = argparse.ArgumentParser(description='TFTP client program')
parser.add_argument(dest="host", help="Server IP address", type=str)
parser.add_argument(dest="operation", help="get or put a file", type=str)
parser.add_argument(dest="filename", help="name of file to transfer", type=str)
parser.add_argument("-p", "--port", dest="port", type=int)
args = parser.parse_args()

server_ip = args.host
server_port = args.port if args.port else DEFAULT_PORT
server_address = (server_ip, server_port)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

mode = DEFAULT_TRANSFER_MODE
operation = args.operation
filename = args.filename

if operation == "get":
    send_rrq(filename, mode)
    file = open(filename, 'wb')
    expected_block_number = 1

    while True:
        data, server_new_socket = sock.recvfrom(516)
        opcode = int.from_bytes(data[:2], 'big')

        if opcode == OPCODE['DATA']:
            block_number = int.from_bytes(data[2:4], 'big')
            if block_number == expected_block_number:
                send_ack(block_number, server_new_socket)
                file_block = data[4:]
                file.write(file_block)
                expected_block_number += 1
            else:
                send_ack(block_number, server_new_socket)


        elif opcode == OPCODE['ERROR']:
            error_code = int.from_bytes(data[2:4], byteorder='big')
            print(ERROR_CODE[error_code])
            file.close()
            os.remove(filename)
            break

        if len(data[4:]) < BLOCK_SIZE:
            file.close()
            print("File transfer completed")
            break


elif operation == "put":
    send_wrq(filename, mode)

    try:
        file = open(filename, 'rb')
    except FileNotFoundError:
        print(f"File {filename} not found.")
        sys.exit(1)

    block_number = 1
    while True:
        data = file.read(BLOCK_SIZE)
        if not data:
            break

        data_packet = pack(f'>hh{len(data)}s', OPCODE['DATA'], block_number, data)
        sock.sendto(data_packet, server_address)
        print(f"Sent DATA block {block_number}")

        sock.settimeout(2)
        try:
            response, server_address = sock.recvfrom(4)
            if int.from_bytes(response[:2], 'big') == OPCODE['ACK']:
                ack_block_number = int.from_bytes(response[2:], 'big')
                if ack_block_number == block_number:
                    print(f"Received ACK for block {block_number}")
                    block_number += 1
                else:
                    print(f"An error occurred. Retrying")
                    sock.sendto(data_packet, server_address)
            else:
                print("Unexpected response.")
        except socket.timeout:
            print(f"Timeout. Retrying.")
            sock.sendto(data_packet, server_address)

    file.close()
    print("File upload completed.")


else:
    print("Invalid operation. Use 'get' or 'put' ")
    sys.exit(1)

sys.exit(0)
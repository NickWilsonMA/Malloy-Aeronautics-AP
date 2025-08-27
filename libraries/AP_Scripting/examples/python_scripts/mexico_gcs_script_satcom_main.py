#!/usr/bin/env python3
'''
A MAVLink gateway for the RockBlock SBD satellite modems.

It will allow limited communications between a MAVLink GCS and
SBD modem fitted to an ArduPilot vehicle.

Requires:
-RockBlock modem
-Active Cloudloop account
-Cloudloop is the source of the data tx/rx (see https://learn.adafruit.com/using-the-rockblock-iridium-modem/forwarding-messages)

Written by Stephen Dade (stephen_dade@hotmail.com)

MAVProxy cmd to use to connect:
mavproxy.py --master=udpout:127.0.0.1:16000 --streamrate=1 --console --mav10 --map

'''
#from argparse import ArgumentParser
from argparse import Namespace
from datetime import datetime, timedelta, timezone
import json
import sys
import time
import requests
from urllib.parse import quote

# from Adafruit_IO import Client, errors
import pymavlink.mavutil as mavutil
from pymavlink.dialects.v10 import ardupilotmega as mavlink1


# Parameters for the script::

# To send the json data to Cloudlloop the API URL is
TX_DATA_CLOUD_LOOP_URL = 'https://api.cloudloop.com/Data/DoSendSbdMessage'

# To Recieve the data from Cloudloop the API URL is
RX_DATA_CLOUD_LOOP_URL = 'https://api.cloudloop.com/Data/GetMessageRecordsForThing'

# Getting the time at the start of the script
script_start_time = datetime.now().replace(tzinfo=timezone.utc)

# https://docs.rockblock.rock7.com/reference/testinput
ROCK7_TX_ERRORS = {'10': 'Invalid login credentials',
                   '11': 'No RockBLOCK with this IMEI found on your account',
                   '12': 'RockBLOCK has no line rental',
                   '13': 'Your account has insufficient credit',
                   '14': 'Could not decode hex data',
                   '15': 'Data too long',
                   '16': 'No Data',
                   '99': 'System Error'}

# Note command_long and command_int are allowed, but only certain commands
ALLOWABLE_MESSAGES = ["MISSION_ITEM_INT",
                      "SET_POSITION_TARGET_GLOBAL_INT",
                      "MISSION_SET_CURRENT",
                      "SET_MODE"]

# Only send these MAVLink commands, to save bandwidth
ALLOWABLE_CMDS = [20,    # MAV_CMD_NAV_RETURN_TO_LAUNCH
                  21,    # MAV_CMD_NAV_LAND
                  22,    # MAV_CMD_NAV_TAKEOFF
                  84,    # MAV_CMD_NAV_VTOL_TAKEOFF
                  85,    # MAV_CMD_NAV_VTOL_LAND
                  176,   # MAV_CMD_DO_SET_MODE
                  178,   # MAV_CMD_DO_CHANGE_SPEED
                  183,   # MAV_CMD_DO_SET_SERVO
                  208,   # MAV_CMD_DO_PARACHUTE
                  300,   # MAV_CMD_MISSION_START
                  400,   # MAV_CMD_COMPONENT_ARM_DISARM
                  192,   # MAV_CMD_DO_REPOSITION
                  2600]  # MAV_CMD_CONTROL_HIGH_LATENCY

UDP_MAX_PACKET_LEN = 65535

# Log file name
LOG_FILE = datetime.now().strftime("%Y%m%d%H%M%S") + "_log.txt"  # Log file name

# Time delay for the script to run
TIME_DELAY = 3  # Time delay in seconds

# Functions for the script::

# Adding Custom Print Function


def c_print(message, output_file=LOG_FILE):
    'To Print to console and record to the file'
    print(f"\n{message}")
    with open(output_file, "a") as f:
        f.write(f"{message}\n")
    f.close()

# Function to get data from the Cloudloop


def get_data_from_cloudloop(thing, token, time_from, time_to):
    'Get the data from the cloudloop'
    url = RX_DATA_CLOUD_LOOP_URL
    params = {
        "token": token,
        "thing": thing,
        "from": time_from,
        "to": time_to,
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error getting data from Cloudloop")
        return None


def send_data_to_cloudloop(thing, token, data):
    'Send the data to the cloudloop'
    url = TX_DATA_CLOUD_LOOP_URL
    params = {
        "thing": thing,
        "message": data,
        "token": token
    }
    response = requests.post(url, params=params, headers={
        "Accept": "text/plain"})
    responseSplit = response.text.split(',')
    if len(data)/2 > 50:
        c_print("Warning, messages greater than 50 bytes")
    if responseSplit[0] != 'OK' and len(responseSplit) > 1:
        if responseSplit[1] in ROCK7_TX_ERRORS.keys():
            c_print("Error sending command: " +
                    ROCK7_TX_ERRORS[responseSplit[1]])
        else:
            c_print("Unknown error: " + response)
    else:
        c_print("Sent {0} bytes OK".format(len(data)/2))


#if __name__ == '__main__':
def main():
    'The main function to run the script'
    # Parse the command line arguments
    '''
    parser = ArgumentParser(description='RockBlock SBD to MAVLink gateway')
    parser.add_argument("-imei", help="Iridium Modem IMEI")
    parser.add_argument("-out", default="udpout:127.0.0.1:16000",
                        help="MAVLink connection to GCS")
    parser.add_argument("-debug", default="udpin:127.0.0.1:17000",
                        help="Debugging port to view messages sent from GCS to vehicle")
    parser.add_argument("-token", default="9d142a84-5274-49f5-9afc-706362bfa7fa",
                        help="cloudloop token for the apis")
    parser.add_argument(
        "-thing", default="QzagvADYwKoPeBQzOPnlMrXJpVORdjyZ", help="Satcom Thing ID")
    parser.add_argument("-mav20", action='store_false',
                        default=False, help="Use MAVLink 2.0 on -out")

    args = parser.parse_args()
    '''

    # Reading parameters from json file instead of parsing command line arguments
    with open("config.json") as f:
        config_dict = json.load(f)

    args = Namespace(**config_dict)

    # previous packet time stamp
    lastpacket_time = script_start_time.replace(hour=0, minute=0, second=0)

    # previous packet as a record
    lastpacket = None
    # Mavlink for the Cloudloop data interpretation
    mavCloudLoop = mavlink1.MAVLink(255, 0, use_native=False)
    # Mavlink for the Vehicle data interpretation
    mavGCS = mavutil.mavlink_connection(args.out)  # Sends packets vehicle -> GCS
    # Mavlink for the GCS data interpretation
    mavUAV = mavutil.mavlink_connection(
        args.debug)   # Repacks packets GCS -> vehicle
    mavUAV.WIRE_PROTOCOL_VERSION = "1.0"
    if args.mav20:
        mavGCS.WIRE_PROTOCOL_VERSION = "2.0"
    else:
        mavGCS.WIRE_PROTOCOL_VERSION = "1.0"

    # Running Infinite loop
    while True:
        # Get the data from the Cloudloop
        try:
            # Getting the timestamp from and to for the Cloudloop API
            # time_from = (lastpacket_time + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
            # mavGCS.input = False
            time_from = (lastpacket_time).strftime("%Y-%m-%d %H:%M:%S")
            time_to = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Testing URL for the Cloudloop API
            # data = get_data_from_cloudloop(args.thing, args.token, "2025-05-12 00:00:00", "2025-05-12 14:50:19")
            # Calling the function to get the data from the Cloudloop API
            print(f"Getting data from Cloudloop API: {time_from} to {time_to}")
            data = get_data_from_cloudloop(args.thing, args.token, time_from, time_to)
            # print(f"Data from Cloudloop API: {data}")

            # This is to recieve the data from the Cloudloop API Vehicle -> GCS
            if data is not None and lastpacket != data:
                # setting the last packet to the current data
                # lastpacket = data
                # Check the data for the first record
                if data['messageRecords']:
                    # Get the first record
                    first_record = data['messageRecords'][0]
                    # Get the Hex data for the first record
                    hex_data = first_record['snippet']
                    if hex_data:
                        # Decode the hex data to bytes
                        try:
                            # Decoded data from mavlink
                            mavlink_msg_hl = mavCloudLoop.parse_buffer(
                                bytes.fromhex(hex_data))
                            # c_print(f"Decoded data: {mavlink_msg_hl.msgtype}")
                            # Decode the data
                            for msg in mavlink_msg_hl:
                                # Check if the message is High Latency
                                c_print(f"Message: {msg}")
                                c_print(f"Message ID: {msg.id}")
                                # c_print(f"Message fields: {msg.get_fieldnames()}")

                                # Setting the packet headers

                                mavGCS.mav.srcSystem = msg.get_srcSystem()
                                mavGCS.mav.srcComponent = msg.get_srcComponent()
                                mavGCS.mav.seq = msg.get_seq()

                                # Check if the message is High Latency
                                if msg.get_type() == "HIGH_LATENCY2":
                                    # Send the data to the QGC Server:
                                    # mavGCS.mavfile.set_mode_apm()
                                    mavGCS.mav.send(msg, force_mavlink1=True)
                                    c_print(
                                        f"Sent message to GCS: {msg.get_type()}")
                                    # Updating the last packet time
                                    lastpacket_time = datetime.strptime(
                                        first_record['at'], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)

                                    # lastpacket_time = datetime.now().replace(tzinfo=timezone.utc)
                                    print(f"Last packet time: {lastpacket_time}")
                                if msg.get_type() == "MISSION_ITEM_INT":
                                    c_print("MISSION_ITEM_INT message received!!!")
                                    mavGCS.mav.send(msg, force_mavlink1=True)
                                    c_print(f"Sent message to GCS: {msg.get_type()}")
                                    lastpacket_time = datetime.strptime(
                                        first_record['at'], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                        except Exception as e:
                            c_print(f"Error decoding hex data: {e}")

            # This is to check the msg list buffer and send from GCS -> Vehicle
            # Get the data from the GCS
            check_msg_for_tx_buffer = True
            tx_buffer = ''
            # This is to check the UDP port in the -out argument
            while check_msg_for_tx_buffer:
                c_print(
                    f"Checking for messages in the -out {args.out} port tx buffer")
                # mavGCS.input = True
                msgGCS = mavGCS.recv_match()
                c_print(
                    f"Checking msgGCS {msgGCS} port tx buffer")
                # filter according to msg properties and send buffer to Rock7
                if msgGCS:
                    # convert to mavlink1 if needed. Get buffer of hex bytes too
                    msgbuf = None
                    if args.mav20:
                        mavUAV.mav.srcSystem = msgGCS.get_srcSystem()
                        mavUAV.mav.srcComponent = msgGCS.get_srcComponent()
                        mavUAV.mav.seq = msgGCS.get_seq()
                        # repack in MAVLink1 format
                        msgbuf = msgGCS.pack(mavUAV.mav, force_mavlink1=True)
                    else:
                        msgbuf = msgGCS.get_msgbuf()
                    c_print(f"\n Abhi :: MsgBuf :: {msgbuf}")
                    # Filter by acceptable messages and commands
                    if msgbuf[0] == 0xFD:
                        print(
                            "Error: MAVLink2 packet detected. Please use -mav20 for conversion to MAVLink1")
                    else:
                        if msgGCS.get_type() in ['COMMAND_LONG', 'COMMAND_INT'] and int(msgGCS.command) in ALLOWABLE_CMDS and len(tx_buffer) <= 50:
                            print("Adding to send queue: " + str(msgGCS))
                            tx_buffer += "".join("%02x" % b for b in msgbuf)
                            print(
                                "Message buffer length: {0}/50".format(len(tx_buffer)/2))
                        elif msgGCS.get_type() in ALLOWABLE_MESSAGES and len(tx_buffer) <= 50:
                            tx_buffer += "".join("%02x" % b for b in msgbuf)
                            print("Adding to send queue: " + str(msgGCS))
                            print(
                                "Message buffer length: {0}/50".format(len(tx_buffer)/2))
                else:
                    # We've gotten all bytes from the GCS
                    check_msg_for_tx_buffer = False

            # send bytes to Rockblock, if any
            if tx_buffer != '':
                # Check if the buffer is greater than 50 bytes
                if len(tx_buffer) > 50:
                    c_print("Warning, messages greater than 50 bytes")
                # Send the data to the Cloudloop API
                send_data_to_cloudloop(args.thing, args.token, tx_buffer)
                # Reset the buffer
                tx_buffer = ''
        except KeyboardInterrupt:
            c_print("Keyboard Interrupt, exiting...")
            sys.exit(0)
        except Exception as e:
            c_print(f"Error getting and sending data to Cloudloop: {e}")

        print(f"Sleeping time delay :: {TIME_DELAY} seconds")
        time.sleep(TIME_DELAY)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        c_print("Keyboard interrupt, exiting...")
        sys.exit(0)
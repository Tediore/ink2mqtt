import sys
import json
import logging
import subprocess
from time import sleep
import paho.mqtt.client as mqtt
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('--host')
parser.add_argument('--port', default=1883)
parser.add_argument('--user')
parser.add_argument('--passwd')
parser.add_argument('--client', default='ink2mqtt')
parser.add_argument('--basetopic', default='ink2mqtt/')
parser.add_argument('--topic', default='printer')
parser.add_argument('--interval', default=10)
parser.add_argument('--parameters', default='desc,health-desc,level,status-desc')
parser.add_argument('--loglevel', default='info', type=str.upper)
args = parser.parse_args()

if args.loglevel not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
    logging.basicConfig(level='INFO', format='%(asctime)s %(levelname)s: %(message)s')
    logging.warning(f"Selected log level '{args.loglevel}' is not valid; using default")
else:
    logging.basicConfig(level=args.loglevel, format='%(asctime)s %(levelname)s: %(message)s')

parameters = args.parameters.split(',')
mqtt_connected = False
client = mqtt.Client(args.client)
full_topic = str(args.basetopic + args.topic)
output_dict = {}
prev_payload = {}

def mqtt_connect():
    # Connect to MQTT broker, set LWT, and start loop
    global mqtt_connected
    try:
        client.username_pw_set(args.user, args.passwd)
        client.will_set(full_topic + '/status', 'offline', 0, True)
        client.connect(args.host, args.port)
        client.loop_start()
        client.publish(full_topic + '/status', 'online', 0, True)
        logging.info('Connected to MQTT broker.')
        mqtt_connected = True
    except Exception as e:
        logging.error(f'Unable to connect to MQTT broker: {e}')
        sys.exit()

def check_params():
    # Check that the user-selected parameters are valid and warn if not
    valid_params = []
    try:
        output = subprocess.check_output('sudo hp-info -i', shell=True, text=True)
        output = output.replace('\n',',').split(',')
    except Exception as e:
        logging.error(f'Command failed: {e}')
        sys.exit()

    for line in output:
        if 'agent' in line:
            valid_params.append(line[line.find('-')+1:30].strip())
        else:
            valid_params.append(line[:30].strip())

    for item in parameters:
        if item in valid_params:
            if args.loglevel == 'DEBUG':
                logging.debug(f'Parameter "{item}" found.')
        else:
            logging.warning(f'Parameter "{item}" not found; ignoring.')

def get_info():
    # Run hp-info and parse output
    global output_dict
    try:
        output = subprocess.check_output('sudo hp-info -i', shell=True, text=True)
        output = output.replace('\n',',').split(',')
        for line in output:
            if line[line.find('-')+1:30].strip() in parameters:
                k = line[:line.find('   ')].strip()
                v = line.strip()[30:]
                output_dict[k] = v
    except Exception as e:
        logging.error(f'Unable to connect to MQTT broker: {e}')

def send_payload():
    # Send parsed output to MQTT
    global output_dict
    global prev_payload
    payload = json.dumps(output_dict)
    if payload != prev_payload:
        try:
            client.publish(full_topic, payload, 0, True)
            prev_payload = payload
            if args.loglevel == 'DEBUG':
                logging.debug('Sending MQTT payload: ' + str(payload))
        except Exception as e:
            logging.error(f'Message send failed: {e}')

    # MQTT heartbeat
    try:
        client.publish(full_topic + '/status', 'online', 0, True)
    except Exception as e:
        logging.error(f'Message send failed: {e}')

check_params()
mqtt_connect()

while mqtt_connected:
    get_info()
    send_payload()
    sleep(args.interval)
import random
import time
import json
import asyncio
import config

from paho.mqtt import client as mqtt_client
from icmplib import async_ping

from types import SimpleNamespace


broker = config.mqtt['broker']
port = config.mqtt['port']
topic = "devices/sensor"
#username = ''
#password = ''

# generate client ID with pub prefix randomly
client_id = f'sensor-mqtt-{random.randint(0, 1000)}'

device_list = []

cloud_latency = 0

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    client = mqtt_client.Client(client_id)
    #client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client


def publish(client):
    msgs = []
    for x in range(1, 4):
        for y in range(0, 10):
            msgs.append(get_data(x))

    while len(device_list) == 0:
        time.sleep(1)

    global cloud_latency
    for msg in msgs:
        cloud_latency = asyncio.run(ping(config.cloud_ip))
        print(str(select_best_node(msg)))

        result = client.publish(topic, msg)
        # result: [0, 1]
        status = result[0]
        if status == 0:
            pass
            #print(f"Send `{msg}` to topic `{topic}`")
        else:
            print(f"Failed to send message to topic {topic}")

        time.sleep(0.2)


def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        if (msg.topic == "devices/edge"):
            # Add device information to the list of devices
            # print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
            add_device(msg.payload.decode())

    client.subscribe("devices/edge")
    client.on_message = on_message


def add_device(msg):
    # transforms the json into a python object
    device = json.loads(msg, object_hook=lambda d: SimpleNamespace(**d))

    # Inserts the device if not in list
    if not any(x.client_id == device.client_id for x in device_list):
        device_list.append(device)
        print("Device added to the list: " + str(device.client_id))

    # Updates the device data
    else:
        devices = device_list
        for index, item in enumerate(devices):
            if item.client_id == device.client_id:
                device_list[index] = device


# Based on the data of all devices, it returns the best node to process the data
def select_best_node(sensor_data):
    sensor = json.loads(
        sensor_data, object_hook=lambda d: SimpleNamespace(**d))
    global device_list
    devices = device_list

    selected_node = None

    filtered_devices = []

    msg = ""

    # Tablet -> Datacenter -> Cloud
    # Aplicação -> Dispositivo -> Rede

    # Verifica primeiro o tipo de aplicação
    for device in devices:
        if int(device.application_type) == int(sensor.application_type):
            filtered_devices.append(device)

    # Se tiver dispositivos com o mesmo tipo de aplicação, filtra a lista
    if filtered_devices:
        # Nova lista para salvar a média dos devices
        final_devices = []

        # Verifica os dados da máquina e da rede
        for device in filtered_devices:
            cpu = device.cpu_percentage
            memory = device.memory_percentage
            cloud = device.cloud_latency
            # battery = device.battery_level
            
            #average = ( ((cpu * 0.5) + (memory * 0.3) + (battery * 0.2)) / 1)
            average = ((cpu * 0.4) + (memory * 0.4) + (cloud * 0.2 )/ 1)

            d = (device.client_id, device.network_ip_address, average)
            
            final_devices.append(d)

        least_average = 100

        # Escolhe o melhor device na categoria
        for device in final_devices:
            if device[2] < least_average:
                least_average = device[2]
                selected_node = device
        
        ping_selected_node = asyncio.run(ping(selected_node[1]))
        
        

        if ping_selected_node < cloud_latency:
            msg = "Application Type: " + str(sensor.application_type) + " - " + str(selected_node[1]) + " - " + str(ping_selected_node) + "ms"
        else:
            msg = "Application Type: " + str(sensor.application_type) + " - " + str(config.cloud_ip) + " - " + str(cloud_latency) + "ms"

    else:
        msg = "Application Type: " + str(sensor.application_type) + " - " + str(config.cloud_ip) + " - " + str(cloud_latency) + "ms"

    return msg
    

# Function that checks latency
async def ping(ip):
    host = await async_ping(ip, count=1, interval=0.2)
    return host.avg_rtt

def get_data(application_type):
    data = {}
    data['application_type'] = application_type
    data['data_1'] = random.randint(0, 10000000)
    data['data_2'] = random.randint(0, 10000000)
    data['data_3'] = random.randint(0, 10000000)
    data['client_id'] = client_id

    msg = json.dumps(data)
    return msg


def run():
    client = connect_mqtt()
    subscribe(client)
    client.loop_start()
    publish(client)


if __name__ == '__main__':
    run()

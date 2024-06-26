import machine
import os
import utime
import binascii
import time

# using pin defined
led_pin = 25  # onboard LED
pwr_en = 14  # pin to control the power of the module
uart_port = 0
uart_baute = 115200
adcpin = 4  # ADC pin for temperature sensor
sensor = machine.ADC(adcpin)

sensor_temp = machine.ADC(4)
conversion_factor = 3.3 / (65535)

APN = "internet.econet"

# UART setting
uart = machine.UART(uart_port, uart_baute)
print(os.uname())

# LED indicator on Raspberry Pi Pico
led_onboard = machine.Pin(led_pin, machine.Pin.OUT)

# Define the phone number for the SMS
phone_number = "+263784488466"  # Replace with your desired phone number

def led_blink():
    led_onboard.value(1)
    utime.sleep(3)
    led_onboard.value(0)
    utime.sleep(3)
    led_onboard.value(1)
    utime.sleep(3)
    led_onboard.value(0)

# Power on/off the module
def power_on_off():
    pwr_key = machine.Pin(pwr_en, machine.Pin.OUT)
    pwr_key.value(1)
    utime.sleep(2)
    pwr_key.value(0)

def hexstr_to_str(hex_str):
    hex_data = hex_str.encode('utf-8')
    str_bin = binascii.unhexlify(hex_data)
    return str_bin.decode('utf-8')

def str_to_hexstr(string):
    str_bin = string.encode('utf-8')
    return binascii.hexlify(str_bin).decode('utf-8')

def wait_resp_info(timeout=2000):
    prvmills = utime.ticks_ms()
    info = b""
    while (utime.ticks_ms() - prvmills) < timeout:
        if uart.any():
            info = b"".join([info, uart.read(1)])
    print(info.decode())
    return info

# Send AT command
def send_at(cmd, back, timeout=2000):
    rec_buff = b''
    uart.write((cmd + '\r\n').encode())
    prvmills = utime.ticks_ms()
    while (utime.ticks_ms() - prvmills) < timeout:
        if uart.any():
            rec_buff = b"".join([rec_buff, uart.read(1)])
    if rec_buff != '':
        if back not in rec_buff.decode():
            print(cmd + ' back:\t' + rec_buff.decode())
            return 0
        else:
            print(rec_buff.decode())
            return 1
    else:
        print(cmd + ' no response')

# Module startup detection
def check_start():
    while True:
        uart.write(bytearray(b'ATE1\r\n'))
        utime.sleep(2)
        uart.write(bytearray(b'AT\r\n'))
        rec_temp = wait_resp_info()
        if 'OK' in rec_temp.decode():
            print('SIM868 is ready\r\n' + rec_temp.decode())
            break
        else:
            power_on_off()
            print('SIM868 is starting up, please wait...\r\n')
            utime.sleep(8)

# Check the network status
def check_network():
    for i in range(1, 3):
        if send_at("AT+CGREG?", "0,1") == 1:
            print('SIM868 is online\r\n')
            break
        else:
            print('SIM868 is offline, please wait...\r\n')
            utime.sleep(5)
            continue
    send_at("AT+CPIN?", "OK")
    send_at("AT+CSQ", "OK")
    send_at("AT+COPS?", "OK")
    send_at("AT+CGATT?", "OK")
    send_at("AT+CGDCONT?", "OK")
    send_at("AT+CSTT?", "OK")
    send_at("AT+CSTT=\"" + APN + "\"", "OK")
    send_at("AT+CIICR", "OK")
    send_at("AT+CIFSR", "OK")

# Get the GPS info
def get_gps_info():
    print('Retrieving GPS coordinates...')
    send_at('AT+CGNSPWR=1', 'OK')
    utime.sleep(2)
    for i in range(5):  # Try up to 5 times to get a valid GPS fix
        uart.write(bytearray(b'AT+CGNSINF\r\n'))
        rec_buff = wait_resp_info()
        gps_data = rec_buff.decode()
        if ',,,,' in gps_data:
            print('GPS is not ready')
            if i >= 4:
                print('GPS positioning failed, please check the GPS antenna.\r\n')
                send_at('AT+CGNSPWR=0', 'OK')
                return None
            else:
                utime.sleep(2)
                continue
        else:
            print('GPS info:')
            print(gps_data)
            # Extract GPS data
            data_parts = gps_data.split(',')
            if len(data_parts) >= 4:
                latitude = data_parts[3]
                longitude = data_parts[4]
                timestamp = data_parts[2]
                send_at('AT+CGNSPWR=0', 'OK')  # Turn off GPS after getting info
                return latitude, longitude, timestamp
            else:
                print('Failed to parse GPS data.')
    return None

# Function to read temperature
def ReadTemperature():
    reading = sensor_temp.read_u16() * conversion_factor 
    temperature = 27 - (reading - 0.706)/0.001721
    print("Temperature: {}".format(temperature))

# Function to send SMS
def send_sms(gps_data):
    print("Sending SMS...")
    temperature = ReadTemperature()  # Read temperature from the onboard sensor
    
    if gps_data:
        latitude, longitude, timestamp = gps_data
        sms_message = f"Temperature: {temperature} °C\nGPS Coordinates:\nLatitude: {latitude}\nLongitude: {longitude}\nTimestamp: {timestamp}"
    else:
        # Get the current time if GPS data is not available
        current_time = utime.localtime()
        formatted_time = "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(
            current_time[0], current_time[1], current_time[2],
            current_time[3], current_time[4], current_time[5]
        )
        sms_message = f"Temperature: {temperature} °C\nFailed to obtain GPS data. Time: {formatted_time}\nRetrying in 5 minutes"

    if send_at('AT+CMGF=1', 'OK'):  # Set SMS format to text mode
        if send_at(f'AT+CMGS="{phone_number}"', '>'):  # Start SMS sending
            uart.write((sms_message + chr(26)).encode())  # Write SMS message and send Ctrl+Z
            print("SMS sent successfully!")
        else:
            print("Failed to enter SMS sending mode.")
    else:
        print("Failed to set SMS mode.")

# Main program
check_start()
check_network()
gps_data = get_gps_info()
send_sms(gps_data)
ReadTemperature()
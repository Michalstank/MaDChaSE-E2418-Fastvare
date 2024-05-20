#Socket.io Library
import socketio

#Random ID Generation
import random

#Serial Communication Libraries
import serial
from time import sleep

#Terminal Access Library
import os

#Node Class Definition, going to hold all important information about the node
class Node:
	node_unique_id 	= 0
	node_network_id = 0
	node_mode 	= 0
	node_data	= 0
	node_max_rand	= 100_000_000

#Creates node_info, main variable used to keep track of node information
node_info = Node()

#Variable to keep track if data is expected to be sent back to the server
node_data_expected = False

#Generate "Unique" ID for this node
node_info.node_unique_id = random.randrange(0, node_info.node_max_rand)

def node_update_role(mode):
	if  (mode == "I" or mode == "i" or mode == "T" or mode == "t" or mode == 2):
		node_info.node_mode = "Init."
	elif(mode == "R" or mode == "r" or mode == 1):
		node_info.node_mode = "Refl."
	elif(mode == "O" or mode == "o" or mode == "N" or mode == "n" or mode == 0):
		node_info.node_mode = "None."

#Init Serial Reading
port = serial.Serial("/dev/ttyACM0" , baudrate = 115200, parity=serial.PARITY_NONE, stopbits = serial.STOPBITS_ONE)

##############################################################
###							   ###
###		     SERVER COMMUNICATION         	   ###
###							   ###
##############################################################

#Connection Init
sio = socketio.Client()

#On Connect
@sio.event
def connect():
	#Inform That Successfully Connected to Server
	print('Connected To Server')

	#Emit Message To The Server, Attaching unique ID for it to register the Node
	sio.emit("SVR_NODE_INIT", node_info.node_unique_id)

#On Disconnect
@sio.event
def disconnect():
	print('Disconnected From Server')

#On RPI_NODE_DATA recive, configure rest of the Node based on the info from the server
@sio.event
def RPI_NODE_DATA(svr_data):
	#Check if this is the node to be updated
	if(svr_data["node_unique_id"] == node_info.node_unique_id):
		print(svr_data)
		#Assign new mode and new id of the node
		node_info.node_network_id = svr_data["node_network_id"]
		node_update_role(svr_data["node_mode"])
		port.write(node_info.node_mode.encode())

#On RPI_NODE_RESET, meaning reset the mode to nothing
@sio.event
def RPI_NODE_RESET(svr_data):
	#Universal Command, ID check Not Needed
	node_info.node_mode = "None"
	#print(node_info.node_mode)
	global node_data_expected
	node_data_expected = False

#On RPI_ROLE_UPDATE, update the role of a node with matching ID
@sio.event
def RPI_ROLE_UPDATE(svr_data):

	#If ID match update role
	if(node_info.node_network_id == svr_data["node_network_id"]):

		#Update Node Role
		node_update_role(svr_data["node_mode"])

		print(node_info.node_mode)

		#Transmit New Mode Over UART
		port.write(node_info.node_mode.encode())

#On RPI_DATA_REQUEST, check if valid node and transmit data
@sio.event
def RPI_DATA_REQUEST(svr_data):
	if(node_info.node_network_id == svr_data["node_network_id"]):

		print("Data Request")
		#Since data might not be ready, set one of variables to true
		#Then transmit data once its ready and clear the variable
		global node_data_expected
		node_data_expected = True

#On RPI_NODE_REFLASH, tell the node to reset itself
@sio.event
def RPI_NODE_REFLASH(svr_data):
	port.write("None.".encode());
	os.system('sudo reboot');

#Connect to the server, IP = TEAM LAPTOP IP when on NTNU NET
sio.connect('http://192.168.0.161:3000', retry = True)

first_char = True
header_char = ""
output = []

#Needs To be reworked for better uart communication, allowing for smooth 2 way communication
while True:

	#Read input from port
	var = port.read();

	#Decode to normal character
	char = var.decode('latin');

	#Check and update if it is the first character in the message
	if(first_char == True and (char == "C" or char == "J")):
		header_char = char
		first_char = False

	#Check if char is equal to the header char and that it is not one of the blacklisted chars
	if(  header_char == 'C' and char != "" and char != '\x00' and char != '\n' and char != '\r'):
		#Add character to char array
		output.append(char)

		#Assuems End of Transmit
		if(char == "."):
			#Remove Message Identifier
			output.pop(0)

			#Compress UART data into string
			uart_msg = "".join(output)

			#Print Message to terminal
			print(uart_msg)

			#Reset Output array
			output = []

			#Reset waiting for char
			first_char = True
	elif(header_char == 'J' and char != "" and char != '\x00' and char != '\n' and char != '\r'):
		#Add character to char array
		output.append(char)

		#Assumes end of JSON file
		if(char == "}"):

			#Remove the J character at the start
			output.pop(0)

			#Create json packet by converting character array to string
			json_packet = "".join(output)

			#Print and save json data locally
			print(json_packet)
			node_info.node_data = json_packet

			#Reset Output
			output = []

			#Check is server expects data
			if(node_data_expected == True):

				#Send JSON file to the server
				sio.emit("SVR_DATA_CONTENT", json_packet)

				#Stop Waiting For Data
				node_data_expected = False

				#Reset waiting for char
				first_char = True

#"Infinite" Loop ish
sio.wait()

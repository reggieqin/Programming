import asyncore
import socket
import sys
import copy
import struct
import time
import thread
import os

import protocol_pb2
import xxtea

import serverMock

local_address = 'localhost'
center_address = "dev-ui.xmoshou.com"
port = 8080

application_server = None
application_serverAddress = None
application_serverPort = 0
key = "gQAeF1ORngIMTlO6ssuXnsCVcno=" 
lastModifiedTime = os.path.getmtime("serverMock.py")

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Utility functions
def decrypt(raw_bodydata):
	prefix = raw_bodydata[1]
	data = xxtea.decrypt(raw_bodydata[1:], key)
	return (prefix, data)

def parseRequest(data):
	request = protocol_pb2.Request()
	(prefix, normalData) = decrypt(data)
	request.ParseFromString(normalData)

	return request

def buildResponse(prefix, response):
	try:
		data = response.SerializeToString()
		raw_data = xxtea.encrypt(data, key)
		raw_data = prefix + raw_data
		new_size = len(raw_data)
		sizeData2 = struct.pack('>i', new_size)

		return sizeData2 + raw_data
	except Exception as e:
		print >> sys.stderr, bcolors.ERROR + "Error -", e, bcolors.ENDC

def req_mock(request):
	mock = serverMock.mock_api.get(request.api)
	if mock != None and mock[0] == 1:
		if mock[1] != None:
			print bcolors.OKGREEN + "Mock request api -", protocol_pb2.Request.API.Name(request.api) + bcolors.ENDC

			try:
				response = protocol_pb2.Response()
				response.error = protocol_pb2.Response.NO_ERROR
				response.key = request.key
				response.api = request.api
				response = mock[1](request, response)

				data = buildResponse(chr(100), response)
				return data
			except Exception as e:
				print >> sys.stderr, bcolors.ERROR + "Error -", e, bcolors.ENDC

def res_mock(response):
	mock = serverMock.mock_api.get(response.api)
	if mock != None and mock[0] == 1:
		if mock[2] != None:
			print bcolors.OKGREEN + "Mock response api -", protocol_pb2.Request.API.Name(response.api) + bcolors.ENDC

			try:
				response = mock[2](response)
				data = buildResponse(chr(101), response)
				return data
			except Exception as e:
				print >> sys.stderr, bcolors.ERROR + "Error -", e, bcolors.ENDC

def mockWatcher(interval):
	global lastModifiedTime
	global serverMock

	while True:
		lmt = os.path.getmtime("serverMock.py")
		if lmt != lastModifiedTime:
			lastModifiedTime = lmt
			reload(serverMock)
			print bcolors.OKBLUE + "Reload serverMock..." + bcolors.ENDC
		time.sleep(interval)

# This handle is to maintain the connection with real server
class ProxyToServer(asyncore.dispatcher):
	def __init__(self, host, port, proxyToClient, clientAddress):
		asyncore.dispatcher.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connect((host, port))
		self.proxyToClient = proxyToClient
		self.clientAddress = clientAddress
		return

	def handle_connect(self):
		print "A new proxy to server connection is established"

	def senddata(self, data):
		self.data = data

	def handle_write(self):
		if self.data != None:
			self.sendall(self.data)
			self.data = None
	
	def handle_read(self):
		global application_server

		# read package size from server
		sizeData = self.recv(4)
		if sizeData:
			size = ord(sizeData[1])*256*256 + ord(sizeData[2]) * 256 + ord(sizeData[3])
			receivedLen = 0
			bodyData = ""
			while receivedLen < size:
				small_data = ""
				try:
					small_data = self.recv(size - receivedLen)
				except Exception as e:
					print "proxy to server receive message exception", e
					time.sleep(1)
				receivedLen = receivedLen + len(small_data)
				bodyData = bodyData + small_data

			# parse response
			responsePro = protocol_pb2.Response()
			(prefix, normalData) = decrypt(bodyData)
			responsePro.ParseFromString(normalData)

			# send data back to client
			print "Receive response %s from server(%s) - size %d"%(protocol_pb2.Request.API.Name(responsePro.api), self.clientAddress, len(bodyData))
			if responsePro.api == protocol_pb2.Request.CT_USER_LOGIN:
				application_server = copy.deepcopy(responsePro.serverInfos)
				for serverInfo in responsePro.serverInfos:
					# print "Change address %s to %s" % (serverInfo.address.ipAddress, local_address)
					serverInfo.address.ipAddress = local_address
					serverInfo.address.port = port

				response = buildResponse(prefix, responsePro)
				self.proxyToClient.sendall(response)
			else:
				mock_response = res_mock(responsePro)
				if mock_response == None:
					self.proxyToClient.sendall(sizeData + bodyData)
				else:
					self.proxyToClient.sendall(mock_response)

	def handle_close(self):
		self.close()
		if self.proxyToClient != None:
			self.proxyToClient.close()
			self.proxyToClient = None
		print bcolors.WARNING + "Server connection is closed -", self.clientAddress + bcolors.ENDC

# this handler is to maintain the connection to client
class ProxyToClient(asyncore.dispatcher):
	def __init__(self, sock, clientAddress):
		asyncore.dispatcher.__init__(self, sock = sock)
		self.clientAddress = clientAddress

	def handle_read(self):
		# Read package size from client
		sizeData = self.recv(4)
		if sizeData:
			size = ord(sizeData[1])*256*256 + ord(sizeData[2]) * 256 + ord(sizeData[3])
			receivedLen = 0
			bodyData = ""
			while receivedLen < size:
				small_data = ""
				try:
					small_data = self.recv(size - receivedLen)
				except Exception as e:
					print "proxy to client receive message exception", e
					time.sleep(1)
				receivedLen = receivedLen + len(small_data)
				bodyData = bodyData + small_data

			# parse request
			request = parseRequest(bodyData)
			print "Get request %s from client(%s) - size %d"%(protocol_pb2.Request.API.Name(request.api), self.clientAddress, len(bodyData))

			if request.api == protocol_pb2.Request.CT_USER_LOGIN:
				self.proxyToServer = ProxyToServer(center_address, port, self, self.clientAddress)
				self.proxyToServer.senddata(sizeData + bodyData)
			elif request.api == protocol_pb2.Request.USER_LOGIN:		
				global application_serverAddress
				global application_serverPort
				for serverInfo in application_server:
					if serverInfo.serverId == request.userLoginRequest.env:
						application_serverAddress = serverInfo.address.ipAddress
						application_serverPort = serverInfo.address.port
						break
				# print "Connect to application server", application_serverAddress, " ", application_serverPort

				self.proxyToServer = ProxyToServer(application_serverAddress, application_serverPort, self, self.clientAddress)
				self.proxyToServer.senddata(sizeData + bodyData)
			elif request.api == protocol_pb2.Request.USER_AUTH:
				if application_serverAddress != None and application_serverPort != None:
					self.proxyToServer = ProxyToServer(application_serverAddress, application_serverPort, self, self.clientAddress)
					self.proxyToServer.senddata(sizeData + bodyData)
			else:
				if self.proxyToServer != None:
					mock_response = req_mock(request)
					if mock_response == None:
						self.proxyToServer.senddata(sizeData + bodyData)
					else:
						self.sendall(mock_response)

	def handle_close(self):
		self.close()
		if self.proxyToServer != None:
			self.proxyToServer.close()
			self.proxyToServer = None
		print bcolors.WARNING + "Client connection is closed -", self.clientAddress + bcolors.ENDC
		print "Waiting for client...."

class ProxyServer(asyncore.dispatcher):
	def __init__(self, host, port):
		asyncore.dispatcher.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.set_reuse_addr()
		self.bind((host, port))
		self.listen(5)
		print "Waiting for client...."

	def handle_accept(self):
		pair = self.accept()
		if pair is not None:
			sock, addr = pair
			print bcolors.OKGREEN + 'Incoming connection from %s' % repr(addr) + bcolors.ENDC

			proxyToClient = ProxyToClient(sock, addr[0])

if __name__ == "__main__":
	thread.start_new_thread( mockWatcher, (1,))

	server = ProxyServer(local_address, 8080)
	asyncore.loop()
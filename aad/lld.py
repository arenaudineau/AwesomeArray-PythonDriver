import serial
import serial.tools.list_ports

WLE = 0x00
WLO = 0x01
SL  = 0x02
BL  = 0x03
BLB = 0x04

SET   = 1
RESET = 0

ACK_NONE   = 0x00
ACK_SET_SR = 0x01
ACK_CLK    = 0x02
ACK_ALL    = ACK_SET_SR | ACK_CLK

class LLDriver():
	"""
	Low-Level driver for the Awesome Array Python Driver.

	
	...
	Attributes
	-----------
	ser : serial.Serial
		serial port associated with the µc
	
	"""

	DEFAULT_PID = 22336

	_opDic = {
		'SET_SR'  : b'\x02',
		'CLK'     : b'\x03',
		'GET_CTL' : b'\x04',
		'ACK_MODE': b'\x05',

		'DBG:PING': b'\x10',
		'DBG:LED' : b'\x11',
	}

	def __init__(self, pid = DEFAULT_PID):
		"""
		Creates the driver.

		Details:
			It will search for the µc using the PID value 'DEFAULT_PID' or the one provided in argument.
			Takes the first found if many have the same PID.
			RAISE if not found.

		Arguments:
			pid: optional, the pid to search for.
		"""
		self.ser = serial.Serial()
		self.ser.baudrate = 921600

		ports = serial.tools.list_ports.comports()
		st_port = None

		for port in ports:
			# If there are multiple serial ports with the same PID, we just use the first one
			if port.pid == pid:
				st_port = port.device
				break

		if st_port is None:
			raise Exception("µc not found, please verify its connection or specify its PID")

		self.ser.port = st_port
		self.ser.open()

	def __del__(self):
		"""Closes the serial port if still open."""
		if self.ser.is_open:
			self.ser.close()
	
	def list_ports():
		"""[STATIC] Returns a list of all the serial ports recognized by the OS."""
		return serial.tools.list_ports.comports()

	def print_ports():
		"""[STATIC] Prints out the useful info about the serial ports recognized by the OS."""
		ports = serial.tools.list_ports.comports()
		if len(ports) == 0:
			print("❌ No serial ports found")
		else:
			for port in serial.tools.list_ports.comports():
				print(port, "| PID: ", port.pid)

	def commands(name = None):
		"""[STATIC] Returns a list of the available µc commands or its hex code if a name is provided."""
		if name is None:
			return list(LLDriver._opDic.keys())
		else:
			return LLDriver._opDic[name]

	def send_command(self, command, *kwargs, wait_for_ack=False):
		"""
		Sends a command to the µc with the optionnaly provided arguments.

		Parameters:
			command: The command to send (see LLDriver.commands())
			*kwargs: The provided arguments, which will be converted to bytes

		Returns:
			The actual number of bytes sent.

		"""
		if command not in LLDriver._opDic:
			raise Exception("Command not found")
		if not self.ser.is_open:
			raise Exception("Serial port not open")

		cmd = b'\xAA' + LLDriver._opDic[command]
		for arg in kwargs:
			if isinstance(arg, int):
				cmd += arg.to_bytes(1, byteorder='big')
			else:
				cmd += bytes(arg)
		cmd += b'\xAA'
		
		res = self.ser.write(cmd)

		if wait_for_ack:
			ack = self.read(2, flush_rest=False)
			if ack != b'\xAA' + LLDriver._opDic[command]:
				raise Exception(f"Expected ack for command '{command}', got '{ack}'")

		return res

	def read(self, size=None, flush_rest=True):
		"""
		Reads from the µc.

		Parameters:
			size:       The number of bytes to read. If None, reads everything.
			flush_rest: If True, flushes the input buffer if non-empty after {size} bytes have been read.
		
		Returns:
			The bytes read.
		"""
		if size is None:
			out = b'';

			# Block until something is in
			while not self.ser.in_waiting:
				pass

			# Read everything until the buffer is empty
			while self.ser.in_waiting:
				out += self.ser.read()
			return out
		
		# else
		out = self.ser.read(size)
		if flush_rest:
			while self.ser.in_waiting:
				self.set.read()
		return out
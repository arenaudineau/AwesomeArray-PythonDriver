import serial
import serial.tools.list_ports

from enum import EnumMeta, IntEnum, IntFlag

# Shift Registers + useful constants
class SR(IntEnum):
	WLE = 0x00
	WLO = 0x01
	SL  = 0x02
	BL  = 0x03
	BLB = 0x04

SR_COUNT = 5
SR_WORD_SIZE = 64
SR_LIST = list(SR.__members__.values())

# Shift Register state code
class State(IntEnum):
	SET   = 0x01
	RESET = 0x00

	def __eq__(self, other):
		if other == b'\x01' or other == True:
			return int(self) == 1
		elif other == b'\x00' or other == False:
			return int(self) == 0
		
		raise ValueError(f"Invalid comparaison between a state and an unknown value '{other}'")

# Command list
class CMD(IntEnum):
	SET_SR   = 0x02
	CLK      = 0x03
	GET_CTL  = 0x04
	ACK_MODE = 0x05
	DBG_ECHO = 0x10
	DBG_LED  = 0x11

CMD_COUNT = 12
CMD_LIST = list(CMD.__members__.values())

# Acknowledge Mode Flags
class ACK(IntFlag):
	NONE   = 0x00
	SET_SR = 0x01
	CLK    = 0x02

	ALL   = SET_SR | CLK
ACK_LIST = list(ACK.__members__.values())

#################
# Driver class
class MCDriver():
	"""
	µc driver for the Awesome Array Python Driver.

	
	...
	Attributes
	-----------
	ser : serial.Serial
		serial port associated with the µc
	
	"""
	DEFAULT_PID = 22336

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
	
	@staticmethod
	def list_ports():
		"""Returns a list of all the serial ports recognized by the OS."""
		return serial.tools.list_ports.comports()

	@staticmethod
	def print_ports():
		"""Prints out the useful info about the serial ports recognized by the OS."""
		ports = serial.tools.list_ports.comports()
		if len(ports) == 0:
			print("❌ No serial ports found")
		else:
			for port in serial.tools.list_ports.comports():
				print(port, "| PID: ", port.pid)

	def send_command(self, command, *kwargs, wait_for_ack=False):
		"""
		Sends a command to the µc with the optionnaly provided arguments.

		Parameters:
			command: The command to send (see CMD_LIST)
			*kwargs: The provided arguments, which will be converted to bytes

		Returns:
			The actual number of bytes sent.

		"""
		if not self.ser.is_open:
			raise Exception("Serial port not open")

		command_bytes = command.to_bytes(1, byteorder='big')
		cmd = b'\xAA' + command_bytes
		for arg in kwargs:
			if isinstance(arg, int):
				cmd += arg.to_bytes(1, byteorder='big')
			else:
				cmd += bytes(arg)
		cmd += b'\xAA'
		
		res = self.ser.write(cmd)

		if wait_for_ack:
			ack = self.read(2, flush_rest=False)
			if ack != b'\xAA' + command_bytes:
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
		if not self.ser.is_open:
			raise Exception("Serial port not open")

		if size is None:
			out = b''

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
			self.flush_input()
		return out

	def flush_input(self):
		"""Flushes the input buffer."""
		while self.ser.in_waiting:
				self.ser.read()
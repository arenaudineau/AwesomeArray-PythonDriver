import serial
import serial.tools.list_ports

from enum import IntEnum, IntFlag
from enum import auto as en_auto
from functools import reduce
from operator import or_

###################
# C enums and flags

# Shift Registers
class SR(IntEnum):
	WLE = 0
	WLO = en_auto()
	SL  = en_auto()
	BL  = en_auto()
	BLB = en_auto()

SR_WORD_SIZE = 64
SR_LIST  = list(SR.__members__.values())
SR_COUNT = len(SR_LIST)

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
	SET_SR     = 0
	SET_CS     = en_auto()
	SET_ADR_R  = en_auto()
	SET_ADR_C  = en_auto()

	GET_CTL    = en_auto()

	CLK        = en_auto()
	CLK_SR     = en_auto()
	CLK_XNOR   = en_auto()

	ACK_MODE   = en_auto()

	DEBUG_ECHO = en_auto()
	DEBUG_LED  = en_auto()

CMD_LIST  = list(CMD.__members__.values())
CMD_COUNT = len(CMD_LIST)

# Acknowledge Mode Flags
class ACK(IntFlag):
	NONE      = 0x00
	SET_SR    = 1 << 1
	SET_CS    = 1 << 2
	SET_ADR_R = 1 << 3
	SET_ADR_C = 1 << 4
	CLK       = 1 << 5
	CLK_SR    = 1 << 6
	CLK_XNOR  = 1 << 7

ACK_LIST = list(ACK.__members__.values())
ACK_ALL = reduce(or_, ACK_LIST)

# Control Signals
class CS(IntEnum):
	CARAC_EN      = 0
	CSL           = en_auto()
	CBLEN         = en_auto()
	ACTIVATE_XNOR = en_auto()
	SR_XNOR       = en_auto()
	CBL           = en_auto()
	CWL           = en_auto()
	READ          = en_auto()
	READ_OUT      = en_auto()
CS_LIST  = list(CS.__members__.values())
CS_COUNT = len(CS_LIST)

#################
# Utils function
def as_int(b: bytes) -> int:
	return int.from_bytes(b, 'big')

def as_bytes(i: int) -> bytes:
	return i.to_bytes(max((i.bit_length() + 7) // 8, 1), 'big')

#################
# Driver class
class MCDriver:
	"""
	µc driver for the Awesome Array Python Driver.

	
	...
	Attributes
	-----------
	ser : serial.Serial
		serial port associated with the µc

	uc_ack_mode : ACK
		stores the actual ack_mode of the µc
	
	"""
	DEFAULT_PID = 22336

	def __new__(cls, *args, **kwargs):
		self = super().__new__(cls)  

		def gen_command_fn(command):
			return lambda *c_args: self.call_command(command, *c_args)

		for cmd in CMD.__members__:
			setattr(self, cmd.lower(), gen_command_fn(CMD.__members__[cmd]))

		return self

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
		self.uc_ack_mode = ACK.NONE

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

	def send_command(self, command, *args, wait_for_ack=False):
		"""
		Sends a command to the µc with the optionnaly provided arguments.

		Parameters:
			command: The command to send (see CMD_LIST)
			*args: The provided arguments, which will be converted to bytes

		Returns:
			The actual number of bytes sent.
		"""
		if not self.ser.is_open:
			raise Exception("Serial port not open")

		if command == CMD.ACK_MODE:
			self.uc_ack_mode = args[0]
	
		command_bytes = as_bytes(command)
		cmd = b'\xAA' + command_bytes
		for arg in args:
			if isinstance(arg, int):
				cmd += as_bytes(arg)
			else:
				cmd += bytes(arg)
		cmd += b'\xAA'
		
		res = self.ser.write(cmd)

		if wait_for_ack:
			ack = self.read(2, flush_rest=False)
			if ack != b'\xAA' + command_bytes:
				raise Exception(f"Expected ack for command '{command}', got '{ack}'")

		return res

	def read(self, size=None, wait_for=True, flush_rest=True):
		"""
		Reads from the µc.

		Parameters:
			size:       The number of bytes to read. If None, reads everything.
			wait_for:   When size=None, if True, waits for input ; When size!=None, wait_for is True
			flush_rest: If True, flushes the input buffer if non-empty after {size} bytes have been read.
		
		Returns:
			The bytes read.
		"""
		if not self.ser.is_open:
			raise Exception("Serial port not open")

		if size is None:
			out = b''

			# Block or not until something is in
			while wait_for and not self.ser.in_waiting:
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

	def call_command(self, command, *args):
		"""
		Send a command and waits for a return value if needed

		Parameters:
			command: The command to send (see CMD_LIST)
			*args: The provided arguments, which will be converted to bytes

		Returns:
			The return value of the corresponding command or None

		Details:
			Will expect an ack if set with the corresponding 'action' command (driver.ack_mode(ACK.XXX)) (RAISE if expected and not received)
			Will return the value received if the command is a 'get' command
		"""

		cmd_name = str(command)[4:] # str(command) == CMD.XXX => str(command)[4:] == XXX
		wait_for_ack = (cmd_name in str(self.uc_ack_mode)) 
		cmd_returns = (cmd_name not in str(ACK_ALL)) # If the commands does not have an associated ack, it is because it returns something
		
		self.send_command(command, *args, wait_for_ack=wait_for_ack)

		return self.read() if cmd_returns else None

	def flush_input(self):
		"""Flushes the input buffer."""
		while self.ser.in_waiting:
				self.ser.read()
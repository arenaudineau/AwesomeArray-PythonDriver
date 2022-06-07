import serial
import serial.tools.list_ports

class LLDriver():
	DEFAULT_PID = 22336

	_opDic = {
		'SET_SR' :  b'\x02',
		'CLK'    :  b'\x03',
		'GET_CTL':  b'\x04',

		'DBG:PING': b'\x10',
		'DBG:LED' : b'\x11',
	}

	def __init__(self, pid = DEFAULT_PID):
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
		if self.ser.is_open:
			self.ser.close()

	def list_ports():
		return serial.tools.list_ports.comports()

	def print_ports():
		for port in serial.tools.list_ports.comports():
			print(port, "| PID: ", port.pid)

	def commands(name = None):
		if name is None:
			return list(LLDriver._opDic.keys())
		else:
			return LLDriver._opDic[name]

	def send_command(self, command, *kwargs):
		if command not in LLDriver._opDic:
			raise Exception("Command not found")
		if not self.ser.is_open:
			raise Exception("Serial port not open")

		cmd = b'\xAA' + LLDriver._opDic[command]
		for arg in kwargs:
			cmd += bytes(arg)
		cmd += b'\xAA'
		return self.ser.write(cmd)

	def read(self, size=None, wait_for=False, flush_rest=True):
		"""
		Reads from the µc.

		Parameters:
			size: The number of bytes to read. If None, reads everything.
			flush: If True, flushes the input buffer if non-empty after {size} bytes have been read.
		
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
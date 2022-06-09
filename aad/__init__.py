import aad.lld

print_ports = lld.LLDriver.print_ports

def get_sr_name(sr_id):
	return {
		0x00: 'WLE',
		0x01: 'WLO',
		0x02: 'SL' ,
		0x03: 'BL' ,
		0x04: 'BLB',
	}[sr_id]


class AwesomeArrayDriver():
	"""
		Awesome Array Driver

		...
		Attributes
		----------
		_lld: lld.LLDriver
			The low-level driver used for the µc
	"""

	def __init__(self, pin = lld.LLDriver.DEFAULT_PID):
		"""
		Creates the driver.

		Details:
			It will search for the µc using the PID value 'DEFAULT_PID' or the one provided in argument.
			Takes the first found if many have the same PID.
			RAISE if not found.

		Arguments:
			pid: optional, the pid to search for.
		"""

		self._lld = lld.LLDriver(pin)
		self.reset_state()

		# Also needs lab driver

	def test_sr_sanity(self, col: int, row: int, bar: bool, set: bool):
		"""
		Tests the shift registers sanity for the given configuration of memristor location and state.

		Parameters:
			col: int, row: int, bar: bool : Memristor location
			set: bool : Memristor state

		Returns:
			A 2D array containing the sanity of the shift register's bits.
			Details:
				sanity[shitreg_id][bit_id] = True if sane, False otherwise
		"""
		rs = self.configure_sr(col, row, bar, set)

		WORD_SIZE = 64		
		sanity = [[None for _ in range(WORD_SIZE)] for _ in range(5)]

		for bit_id in reversed(range(WORD_SIZE)):
			for sr_id, sr_word in enumerate(rs):
				self._lld.send_command('GET_CTL', sr_id)

				set_val = (((sr_word >> bit_id) & 1) == 1);
				sr_val = (self._lld.read() == lld.SET)

				sanity[sr_id][bit_id] = (set_val == sr_val)

		return sanity
    
	def configure_sr(self, col: int, row: int, bar: bool, set: bool):
		"""
		Configure the shift registers for the given memristor location and state.

		Parameters:
			col: int, row: int, bar: bool : Memristor location
			set: bool : Memristor state

		Returns:
			An array containing the shift registers configuration set.
		"""

		sr = [0, 0, 0, 0, 0] # Indices are the same as lld.WLE/WLO/...

		# Dispatch the WL bits between the Odd and Even registers
		if row % 2 == 0:
			sr[lld.WLE] = (True << (row // 2))
		else:
			sr[lld.WLO] = (True << ((row - 1) // 2))

		sr[lld.SL]  = (set << col)
		sr[lld.BL]  = ((bar == set) << col)
		sr[lld.BLB] = ((bar != set) << col)

		WORD_SIZE = 64
		for bit_id in reversed(range(WORD_SIZE)):
			for sr_id, sr_word in enumerate(sr):
				self._lld.send_command('SET_SR', sr_id, (sr_word >> bit_id) & 1, wait_for_ack=True)

			# As all the sr share the same clk, we pulse after setting every individual inputs
			self._lld.send_command('CLK', wait_for_ack=True)

		# Reset every inputs afterward
		for sr_id in range(len(sr)):
				self._lld.send_command('SET_SR', sr_id, lld.RESET, wait_for_ack=True)

		return sr

	def reset_state(self):
		"""
		Resets the state of the driver, to run after exception catching for example.
		"""
		self._lld.flush_input()
		self._lld.send_command('ACK_MODE', lld.ACK_ALL, wait_for_ack=True)
		self._lld.flush_input()

	def set(self, col, row, bar=False):
		"""
		Sets the memristor at the given address.

		Parameters:
			col: Address of the column
			row: Address of the row
			bar: If True, sets the memristor Rb instead of R
		"""
		self.configure_sr(col, row, bar, set=True)

	def reset(self, col, row, bar=False):
		"""
		Resets the memristor at the given address.

		Parameters:
			col: Address of the column
			row: Address of the row
			bar: If True, resets the memristor Rb instead of R
		"""
		self.configure_sr(col, row, bar, set=False)

	def form(self, col, row, bar=False):
		"""
		Forms the memristor at the given address.

		Parameters:
			col: Address of the column
			row: Address of the row
			bar: If True, forms the memristor Rb instead of R
		"""
		self.configure_sr(col, row, bar, set=True)
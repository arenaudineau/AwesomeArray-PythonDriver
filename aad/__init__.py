import aad.lld

print_ports = lld.LLDriver.print_ports

class AwesomeArrayDriver():
	"""
		Awesome Array Driver
	"""

	def __init__(self, pin = lld.LLDriver.DEFAULT_PID):
		self._lld = lld.LLDriver(pin)
		self.reset_state()

		# Also needs lab driver

	def test_sr_sanity(self, col: int, row: int, bis: bool, set: bool):
		"""
		Tests the shift registers sanity for the given configuration of memristor location and state.

		Parameters:
			col: int, row: int, bis: bool : Memristor location
			set: bool : Memristor state

		Returns:
			A 2D array containing the sanity of the shift register's bits.
			Details:
				sanity[shitreg_id][bit_id] = True if sane, False otherwise
		"""
		rs = self.configure_sr(col, row, bis, set)

		WORD_SIZE = 64		
		sanity = [[None for _ in range(WORD_SIZE)] for _ in range(5)]

		for bit_id in reversed(range(WORD_SIZE)):
			for sr_id, sr_word in enumerate(rs):
				self._lld.send_command('GET_CTL', sr_id)

				set_val = (((sr_word >> bit_id) & 1) == 1);
				sr_val = (self._lld.read() == lld.SET)

				sanity[sr_id][bit_id] = (set_val == sr_val)

		return sanity
    
	def configure_sr(self, col: int, row: int, bis: bool, set: bool):

		sr = [0, 0, 0, 0, 0] # Indices are the same as lld.WLE/WLO/...

		# Dispatch the WL bits between the Odd and Even registers
		if row % 2 == 0:
			sr[lld.WLE] = (True << (row // 2))
		else:
			sr[lld.WLO] = (True << ((row - 1) // 2))

		sr[lld.SL]  = (set << col)
		sr[lld.BL]  = ((bis == set) << col)
		sr[lld.BLB] = ((bis != set) << col)

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

	def set(self, col, row, bis=False):
		"""
		Sets the memristor at the given address.

		Parameters:
			col: Address of the column
			row: Address of the row
			bis: If True, sets the memristor Rb instead of R
		"""
		self.configure_sr(col, row, bis, set=True)

	def reset(self, col, row, bis=False):
		"""
		Resets the memristor at the given address.

		Parameters:
			col: Address of the column
			row: Address of the row
			bis: If True, resets the memristor Rb instead of R
		"""
		self.configure_sr(col, row, bis, set=False)

	def form(self, col, row, bis=False):
		"""
		Forms the memristor at the given address.

		Parameters:
			col: Address of the column
			row: Address of the row
			bis: If True, forms the memristor Rb instead of R
		"""
		self.configure_sr(col, row, bis, set=True)
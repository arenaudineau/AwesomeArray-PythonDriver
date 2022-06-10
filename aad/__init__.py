from typing import List

import aad.mcd

# Utils export from mcd
print_ports = mcd.MCDriver.print_ports

from aad.mcd import WLE, WLO, SL, BL, BLB

SR_LIST      = [mcd.WLE, mcd.WLO, mcd.SL, mcd.BL, mcd.BLB]
SR_COUNT     = len(SR_LIST)
SR_WORD_SIZE = 64

def get_sr_name(sr_id):
	"""
	Returns the name of the SR with the given ID.
	"""

	return {
		mcd.WLE: 'WLE',
		mcd.WLO: 'WLO',
		mcd.SL : 'SL' ,
		mcd.BL : 'BL' ,
		mcd.BLB: 'BLB',
	}[sr_id]


class AwesomeArrayDriver():
	"""
		Awesome Array Driver

		...
		Attributes
		----------
		_mcd: mcd.MCDriver
			The low-level driver used for the µc
	"""

	def __init__(self, pid = mcd.MCDriver.DEFAULT_PID):
		"""
		Creates the driver.

		Details:
			It will search for the µc using the PID value 'DEFAULT_PID' or the one provided in argument.
			Takes the first found if many have the same PID.
			RAISE Exception if not found.

		Arguments:
			pid: optional, the pid to search for.
		"""
		self._mcd = mcd.MCDriver(pid)
		self.reset_state()

		# Also needs lab driver

	def reset_state(self):
		"""
		Resets the state of the driver, to run after exception catching for example.
		"""
		self._mcd.flush_input()
		self._mcd.send_command('ACK_MODE', mcd.ACK_ALL, wait_for_ack=True)
		self._mcd.flush_input()

	##### µC-RELATED METHODS #####
	def get_sr_configuration(self, col: int, row: int, bar: bool, set: bool):
		"""
		Gives the shift registers words for the given memristor location and state.

		Parameters:
			col: int, row: int, bar: bool : Memristor location
			set: bool : Memristor state

		Returns:
			An array containing the computed shift registers words
		"""
		sr_words = [0, 0, 0, 0, 0] # Indices are the same as mcd.WLE/WLO/...

		# Dispatch the WL bits between the Odd and Even registers
		if row % 2 == 0:
			sr_words[mcd.WLE] = (True << (row // 2))
		else:
			sr_words[mcd.WLO] = (True << ((row - 1) // 2))

		sr_words[mcd.SL]  = (set << col)
		sr_words[mcd.BL]  = ((bar == set) << col)
		sr_words[mcd.BLB] = ((bar != set) << col)

		return sr_words

	def configure_sr_words(self, sr_words: List[int]):
		"""
		Configure the shift registers with the given words.

		Parameters:
			sr_words: List[int] : The words to configure the shift registers with.
		"""
		for bit_id in reversed(range(SR_WORD_SIZE)):
			for sr_id, sr_word in enumerate(sr_words):
				self._mcd.send_command('SET_SR', sr_id, (sr_word >> bit_id) & 1, wait_for_ack=True)

			# As all the sr share the same clk, we pulse after setting every individual inputs
			self._mcd.send_command('CLK', wait_for_ack=True)

		# Reset every inputs afterward
		for sr_id in SR_LIST:
				self._mcd.send_command('SET_SR', sr_id, mcd.RESET, wait_for_ack=True)

	def configure_sr(self, col: int, row: int, bar: bool, set: bool):
		"""
		Configure the shift registers for the given memristor location and state.

		Parameters:
			col: int, row: int, bar: bool : Memristor location
			set: bool : Memristor state

		Returns:
			An array containing the shift registers words set.
		"""		
		sr_words = self.get_sr_configuration(col, row, bar, set)
		self.configure_sr_words(sr_words)

		return sr_words

	def test_sr_words_sanity(self, sr_words: List[int]):
		"""
		Tests the shift registers sanity for the given words.

		Parameters:
			sr_words: List[int] : The words to configure the shift registers with.

		Returns:
			A 2D array containing the sanity of the shift register's bits.
			Details:
				sanity[shitreg_id][bit_id] = True if sane, False otherwise
		"""
		self.configure_sr_words(sr_words)

		sanity = [[None for _ in range(SR_WORD_SIZE)] for _ in range(SR_COUNT)]

		for bit_id in reversed(range(SR_WORD_SIZE)):
			for sr_id, sr_word in enumerate(sr_words):
				self._mcd.send_command('GET_CTL', sr_id)

				set_val = (((sr_word >> bit_id) & 1) == 1)
				sr_val = (self._mcd.read() == mcd.SET)

				sanity[sr_id][bit_id] = (set_val == sr_val)

		return sanity

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
		sr_words = self.get_sr_configuration(col, row, bar, set)
		return self.test_sr_words_sanity(sr_words)

	##### B1530-RELATED METHODS #####
	# Empty

	##### HIGH-LEVEL MEMRISTOR MANIPULATION METHODS #####
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
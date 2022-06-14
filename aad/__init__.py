from typing import List

import aad.mcd, aad.B1530Lib
from aad.mcd import SR, SR_COUNT, SR_WORD_SIZE, SR_LIST, State

# Utils export from mcd
print_ports = mcd.MCDriver.print_ports

class AwesomeArrayDriver:
	"""
		Awesome Array Driver

		...
		Attributes
		----------
		_mcd: mcd.MCDriver
			The low-level driver used for the µc

		_b1530: B1530Lib.B1530
			The driver used to control the B1530
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
		self._b1530 = B1530Lib.B1530(1e-5, 1e-5)
		
		self.reset_state()

	def reset_state(self):
		"""
		Resets the state of the driver, to run after exception catching for example.
		"""
		self._mcd.flush_input()
		self._mcd.ack_mode(mcd.ACK_ALL)

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
		sr_words = [0, 0, 0, 0, 0] # Indices are the same as SR.WLE/WLO/...

		# Dispatch the WL bits between the Odd and Even registers
		if row % 2 == 0:
			sr_words[SR.WLE] = (True << (row // 2))
		else:
			sr_words[SR.WLO] = (True << ((row - 1) // 2))

		sr_words[SR.SL]  = (set << col)
		sr_words[SR.BL]  = ((bar == set) << col)
		sr_words[SR.BLB] = ((bar != set) << col)

		return sr_words

	def configure_sr_words(self, sr_words: List[int]):
		"""
		Configure the shift registers with the given words.

		Parameters:
			sr_words: List[int] : The words to configure the shift registers with.
		"""
		for bit_id in reversed(range(SR_WORD_SIZE)):
			for sr_id, sr_word in enumerate(sr_words):
				self._mcd.set_sr(sr_id, (sr_word >> bit_id) & 1)

			# As all the sr share the same clk, we pulse after setting every individual inputs
			self._mcd.clk_sr()

		# Reset every inputs afterward
		for sr_id in SR_LIST:
				self._mcd.set_sr(sr_id, State.RESET)

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
				set_val = (((sr_word >> bit_id) & 1) == 1)
				sr_val = self._mcd.get_ctl(sr_id)

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

		pulse = B1530Lib.Pulse()
		pulse.name = 'VA'
		pulse.meas  = 'voltage'
		pulse.range = '5V'
		pulse.pattern_voltage = [0, 1, 1, 0, 0]
		pulse.trail = 100e-5
		pulse.lead  = 100e-5
		pulse.wait_time = 0.1e-6
		pulse.length = 0.5

		self._b1530.apply_pulses([None, pulse, None, None])

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
from typing import List

from aad import mcd, B1530Lib
from aad.mcd import SR, SR_COUNT, SR_WORD_SIZE, SR_LIST, State

# Utils export from mcd
print_ports = mcd.MCDriver.print_ports
print_visa_dev = B1530Lib.print_devices

###############################
# WGFMU Configuration Constants
WGFMU_CONFIG_SET  = 0 # Set or Reset operation
WGFMU_CONFIG_FORM = 1 # Form operation
WGFMU_CONFIG_READ = 2 # Read operation

##########################
# class AwesomeArrayDriver
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

		_last_operation: int
			Stores the last operation performed, not to reconfigure everything if it is the same
			(-1 = None, 0 = set, 1 = reset, 2 = form, 3 = read)
	"""

	def __init__(self, uc_pid = mcd.MCDriver.DEFAULT_PID, visa_addr = B1530Lib.B1530.DEFAULT_ADDR):
		"""
		Creates the driver.

		Details:
			It will search for the µc using the PID value 'DEFAULT_PID' or the one provided in argument.
			Takes the first found if many have the same PID.
			RAISE Exception if not found.

		Arguments:
			pid: optional, the pid to search for.
		"""
		self._mcd = mcd.MCDriver(uc_pid)
		self._b1530 = B1530Lib.B1530(addr=visa_addr)

		self._last_wgfu_config = -1
		
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
		args = []
		for word in sr_words:
			args.extend(word.to_bytes(8, 'little')) # Little endiannes: bit at pos 0 will be sent first

		self._mcd.fill_srs(*args)

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
	def configure_wgfmu(self, config):
		"""
		Configures the WGFMUs with the configuration provided
		
		Parameters:
			config: The configuration to apply:
				* WGFMU_CONFIG_SET:  Configures pulses for memristor Set/Reset ;
				* WGFMU_CONFIG_FORM: Configures pulses for memristor forming ;
				* WGFMU_CONFIG_READ: Configures pulses and meas. for memristor value reading ;
				
		Details:
			b1530.chan[1] = Vin1_row (= GND) ;
			b1530.chan[2] = Vin1_col (= GND or measure) ;
			b1530.chan[3] = Vin2_row (= transistor Pulse) ;
			b1530.chan[4] = Vin2_col (= memristor Pulse) ;
		"""
		if self._last_wgfu_config == config:
			return
		
		self._last_wgfu_config = config

		#self._b1530.reset_configuration()
		chan = self._b1530.chan

		# TODO: make this a list/dict?
		if config == WGFMU_CONFIG_SET:			
			voltage        = 2
			mosfet_voltage = 5

			length     = 1e-5
			interval   = length / 10
			edges      = length / 50
		
		elif config == WGFMU_CONFIG_FORM:
			voltage         = 3
			mosfet_voltage  = 5

			length     = 1e-5
			interval   = length / 10
			edges      = length / 50

		elif config == WGFMU_CONFIG_READ:
			voltage        = 1
			mosfet_voltage = 5

			length     = 1e-5
			interval   = length / 10
			edges      = length / 50

		else:
			raise ValueError("Unknown WGFMU config")
			
		chan[3].wave = B1530Lib.Pulse(voltage = mosfet_voltage, interval = interval, edges = edges, length = length * 2)
			
		# TMP: should be chan[4]
		chan[1].wave = B1530Lib.Pulse(voltage = voltage, interval = interval + length, edges = edges, length = length)

		duration = chan[3].wave.get_total_duration()
		#chan[1].wave = B1530Lib.Waveform([[duration, 0]]) 
			
		# chan[2]: Either measure and/or force to gnd
		if config == WGFMU_CONFIG_READ:
			chan[1].name = 'V'
			chan[1].measure_self(sample_interval=interval, average_time=interval, ignore_gnd=True)
			chan[2].name = 'I'
			chan[2].meas = chan[1].measure(mode='current', range='10mA', sample_interval=interval, average_time=interval, ignore_gnd=True) # Do not measure current when the pulse is at GND
		else:
			chan[2].wave = B1530Lib.Waveform([[0, 0], [duration, 0]]) # Force to GND
			

		self._b1530.configure()

	##### HIGH-LEVEL MEMRISTOR MANIPULATION METHODS #####
	def set(self, col, row, bar=False):
		"""
		Sets the memristor at the given address.

		Parameters:
			col: Address of the column
			row: Address of the row
			bar: If True, sets the complementary memristor
		"""
		self.configure_sr(col, row, bar, set=True)
		self.configure_wgfmu(WGFMU_CONFIG_SET)
		self._b1530.exec()
		

	def reset(self, col, row, bar=False):
		"""
		Resets the memristor at the given address.

		Parameters:
			col: Address of the column
			row: Address of the row
			bar: If True, resets the complementary memristor
		"""
		self.configure_sr(col, row, bar, set=False)
		self.configure_wgfmu(WGFMU_CONFIG_SET)
		self._b1530.exec()
		

	def form(self, col, row, bar=False):
		"""
		Forms the memristor at the given address.

		Parameters:
			col: Address of the column
			row: Address of the row
			bar: If True, forms the complementary memristor
		"""
		self.configure_sr(col, row, bar, set=True)
		self.configure_wgfmu(WGFMU_CONFIG_FORM)
		self._b1530.exec()
		

	def read(self, col, row, bar=False):
		"""
		Reads the memrisator value at the given address.
		
		Parameters:
			col: Address of the column
			row: Address of the row
			bar: If True, reads the complementary memristor

		Returns:
			The memristor value
		"""
		self.configure_sr(col, row, bar, set=True)
		self.configure_wgfmu(WGFMU_CONFIG_READ)
		self._b1530.exec()
		
		data = self._b1530.get_result(1, 2) #todo: 4, 2
		res = abs(data.V / data.I)
		return res.mean()
		



from ctypes.wintypes import WORD
import aad.lld

from bitarray.util import zeros as bitarray

class AwesomeArrayDriver():
	def __init__(self, pin = lld.LLDriver.DEFAULT_PID):
		self._lld = lld.LLDriver(pin)

		# Also needs lab driver

	def __configure_sr(self, col: int, row: int, bis: bool, set: bool):
		#* Bit manipulation magic ✨

		sr = [0, 0, 0, 0, 0] # Indices are the same as lld.WLE/WLO/...

		# Dispatch the WL bits between the Odd and Even registers
		if row % 2 == 0:
			sr[lld.WLE] = (True << (row // 2))
		else:
			sr[lld.WLO] = (True << ((row - 1) // 2))

		sr[lld.SL]  = (set << col)
		sr[lld.BL]  = ((bis == set) << col)
		sr[lld.BLB] = ((bis != set) << col)

		words_set = ['','','','',''] #* TMP For debug purpose

		WORD_SIZE = 64
		for bit_id in reversed(range(WORD_SIZE)):
			for sr_id, sr_word in enumerate(sr):
				self._lld.send_command('SET_SR', sr_id, (sr_word >> bit_id) & 1)
				words_set[sr_id] += str((sr_word >> bit_id) & 1) 

			# As all the sr share the same clk, we pulse after setting every individual inputs
			self._lld.send_command('CLK')

		print(words_set)

	def set(self, col, row, bis=False):
		self.__configure_sr(col, row, bis, set=True)

	def reset(self, col, row, bis=False):
		self.__configure_sr(col, row, bis, set=False)

	def form(self, col, row, bis=False):
		self.__configure_sr(col, row, bis, set=True)
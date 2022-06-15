from aad.extlibs import B1530Driver
import pyvisa as visa

from typing import List
from copy import deepcopy

def device_list():
	return visa.ResourceManager('@ivi').list_resources('?*')

def print_devices():
	for device in device_list():
		print(device)

class Pulse:
	name:  str
	meas:  str
	range: str
	#save:  bool
	pattern_voltage: List[float]

	wait_time: float
	length:    float
	lead:      float
	trail:     float

	@property
	def voltage(self):
		assert False, "Pulse.voltage should not be get"
	@voltage.setter
	def voltage(self, value):
		self.pattern_voltage = [0, value, value, 0, 0]

	@property
	def edges(self):
		assert False, "Pulse.edges should not be get"
	@edges.setter
	def edges(self, value):
		self.lead  = value
		self.trail = value

	def get_time_pattern(self):
		"""Returns the time pattern of the pulse in the expected format of the underlying driver"""
		return [self.wait_time, self.lead, self.length, self.trail, self.wait_time]

	def as_model(self):
		"""Returns the pulse as a model that can be used to create other pulses with the same parameters"""
		class Model:
			def __new__(cls):
				return deepcopy(self)
		return Model

class B1530:
	DEFAULT_ADDR = r'GPIB0::18::INSTR'

	WGFMU_chans = {
		1: 101,
		2: 102,
		3: 201,
		4: 202,
	}

	def __init__(self, sampling_interval, average_time, addr=DEFAULT_ADDR):
		self.meas_start_delay = [0] * 4
		self.pulse_count = 1

		if isinstance(sampling_interval, List):
			self.sampling_interval = sampling_interval
		else:
			self.sampling_interval = [sampling_interval] * 4
		
		if isinstance(average_time, List):
			self.average_time = average_time
		else:
			self.average_time = [average_time] * 4

		self.__err_msg = "Failed to connect to B1530."
		self._error_buffer = []
		self.__handled_error(B1530Driver.openSession, addr)

	def __del__(self):
		self.__handled_error(B1530Driver.closeSession)

	def __print_placeholder(self, *args):
		self._error_buffer.append(map(str, args))

	def __handle_error(self, err):
		if err[0] != 0:
			except_msg = "BF1530 Driver error occured" if self.__err_msg is None else self.__err_msg
			if len(self._error_buffer) != 0:
				except_msg += "\nDetails:\n" + "\n".join(map(lambda e: " ".join(e), self._error_buffer))
			else:
				except_msg += ": " + err[1]
			self._error_buffer = []
			
			raise Exception(except_msg)
		self.__err_msg = None

	def __handled_error(self, fn, *args, **kwargs):
		__builtins__['print_backup'] = __builtins__['print']
		__builtins__['print'] = self.__print_placeholder
		self.__handle_error(fn(*args, **kwargs))
		__builtins__['print'] = __builtins__['print_backup']

	def wgfmu_conf(self, wgfmu_id, measure_mode, measure_range, range_force='auto'):
		self.__handled_error(B1530Driver.setMeasureMode, self.WGFMU_chans[wgfmu_id], B1530Driver._measureMode[measure_mode])
		if measure_mode=="current":
			self.__handled_error(B1530Driver.setMeasureCurrentRange, self.WGFMU_chans[wgfmu_id], B1530Driver._measureCurrentRange[measure_range])
		elif measure_mode=="voltage":
			self.__handled_error(B1530Driver.setForceVoltageRange, self.WGFMU_chans[wgfmu_id], B1530Driver._forceVoltageRange[range_force])
			self.__handled_error(B1530Driver.setMeasureVoltageRange, self.WGFMU_chans[wgfmu_id], B1530Driver._measureVoltageRange[measure_range])
		else:
			raise ValueError(f"Unknown measure mode '{measure_mode}'")

		self.__handled_error(B1530Driver.connect, self.WGFMU_chans[wgfmu_id])
		self.__handled_error(B1530Driver.clear) #clear software
	
	def wgfmu_conf_mode(self, wgfmu_id, op_mode):
		self.__handle_error(B1530Driver.setOperationMode(self.WGFMU_chans[wgfmu_id], B1530Driver._operationMode[op_mode]))
		
	def wgfmu_conf_pattern(self, wgfmu_id, pattern_name, measure_count, pattern_voltage, time_pattern, event_name, rdata='averaged'):
		if len(pattern_voltage) <= 1:
			self.__handled_error(B1530Driver.createPattern, pattern_name, pattern_voltage)
			self.__handled_error(B1530Driver.addVector, pattern_name, time_pattern, pattern_voltage)
		else:
			self.__handled_error(B1530Driver.createPattern, pattern_name, pattern_voltage[0])
			self.__handled_error(B1530Driver.addVectors, pattern_name, time_pattern, pattern_voltage, len(pattern_voltage))
		

		self.__handled_error(
			B1530Driver.setMeasureEvent,
				pattern_name,
				event_name,
				self.meas_start_delay[wgfmu_id-1],
				measure_count,
				self.sampling_interval[wgfmu_id-1],
				self.average_time[wgfmu_id-1],
				B1530Driver._measureEventData[rdata]
			)
		self.__handled_error(B1530Driver.addSequence, self.WGFMU_chans[wgfmu_id], pattern_name, self.pulse_count)

	def apply_pulses(self, pulses: List[Pulse]):
		if len(pulses) > 4:
			raise Exception(f"Too many pulses. 4 max, got {len(pulses)}")

		pattern_names = ["WaveA", "WaveB", "WaveC", "WaveD"]

		measure_count = -1 # To set
		for wgfmu_id in range(1, 5):
			pulse = pulses[wgfmu_id - 1]
			if pulse is None:
				continue

			pat_measure_count = 1 #sum(pulse.get_time_pattern() - self.meas_start_delay[0]) / self.sampling_interval[0]

			self.wgfmu_conf_mode(wgfmu_id, 'fastiv')
			self.wgfmu_conf(wgfmu_id, pulse.meas, pulse.range)
			self.wgfmu_conf_pattern(wgfmu_id, pattern_names[wgfmu_id-1], pat_measure_count, pulse.pattern_voltage, pulse.get_time_pattern(), pulse.name)

		self.__handled_error(B1530Driver.execute)
		status = 0
		while status != 10000:
			error, status, _, _ = B1530Driver.getStatus()
			self.__handle_error(error)
from aad.extlibs import B1530Driver
from aad.extlibs.stderr_redirect import stderr_redirector
import pyvisa as visa

import pandas as pd

import io
from copy import deepcopy
from functools import reduce

################
# Utils function
def device_list():
	return visa.ResourceManager('@ivi').list_resources('?*')

def print_devices():
	for device in device_list():
		print(device)

################
# Waveform class
class Waveform:
	def __init__(self, pattern = [[0,0]]):
		# Pattern: [[Time (s), Voltage (V)], ...]
		self.pattern = pattern
	
	def append(self, other):
		self.pattern.extend(deepcopy(other.pattern))
		return self # To chain

	def repeat(self, count):
		pattern_copy = deepcopy(self.pattern)
		for _ in range(count):
			self.pattern.extend(deepcopy(pattern_copy))
		return self # To chain
	
	def measure(self, **kwargs):
		kwargs.setdefault('duration', -1)

		meas = Measurement(**kwargs)
		if meas.duration == -1:
			meas.duration = self.get_total_duration() - meas.start_delay
		
		return meas

	def get_time_pattern(self):
		return [p[0] for p in self.pattern]
	
	def get_voltage_pattern(self):
		return [p[1] for p in self.pattern]

	def get_total_duration(self):
		return sum(self.get_time_pattern())

	def get_max_voltage(self):
		return reduce(lambda a, b: a if a[1] > b[1] else b, self.pattern)[1]

	def get_min_voltage(self):
		return reduce(lambda a, b: a if a[1] < b[1] else b, self.pattern)[1]

	def get_max_abs_voltage(self):
		return reduce(lambda a, b: a if abs(a[1]) > abs(b[1]) else b, self.pattern)[1]

	def get_min_abs_voltage(self):
		return reduce(lambda a, b: a if abs(a[1]) < abs(b[1]) else b, self.pattern)[1]

class Pulse(Waveform):
	def __init__(self, **kwargs):
		self.pattern = [[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]
		for key in kwargs:
			setattr(self, key, kwargs[key])

	@property
	def interval(self):
		wait_beg = self.pattern[0][0]
		wait_end = self.pattern[4][0]
		if wait_beg == wait_end:
			return wait_beg * 2
		else:
			return wait_beg, wait_end

	@interval.setter
	def interval(self, value):
		self.pattern[0][0] = value / 2
		self.pattern[4][0] = value / 2

	@property
	def length(self):
		return self.pattern[2][0]

	@length.setter
	def length(self, value):
		self.pattern[2][0] = value

	@property
	def edges(self):
		lead  = self.pattern[1][0]
		trail = self.pattern[3][0]
		if lead == trail:
			return lead
		else:
			return lead, trail

	@edges.setter
	def edges(self, value):
		self.pattern[1][0] = value
		self.pattern[3][0] = value

	@property
	def voltage(self):
		if self.pattern[1][1] != self.pattern[2][1]:
			return self.get_voltage_pattern()
		else:
			return self.pattern[1][1]

	@voltage.setter
	def voltage(self, value):
		self.pattern[1][1] = value
		self.pattern[2][1] = value

###################
# Measurement class
class Measurement:
	def __init__(self, mode, average_time, sample_rate, duration, **kwargs):
		self.start_delay = 0
		self.mode = mode
		self.average_time = average_time
		self.sample_rate = sample_rate
		self.duration = duration
		for key in kwargs:
			setattr(self, key, kwargs[key])

		self.result = []

	def get_meas_count(self):
		return int(self.duration / self.sample_rate)

	def get_total_duration(self):
		return self.start_delay + self.get_meas_count() * self.sample_rate

#############
# WGFMU Class
class WGFMU:
	def __init__(self, id: int, name = 'WGFMU'):
		self.id = id
		self.name = name
		self.wave = None
		self.meas = None

	def measure(self, **kwargs):
		"""Shortcut for wgfmu.wave.measure"""
		if self.wave is None:
			raise ValueError("Trying to measure a 'None' waveform")
		
		return self.wave.measure(**kwargs)

	def measure_self(self, average_time, sample_rate):
		"""
		Creates and sets a measurement for the current waveform.
		It selects the adapted voltage range.
		"""
		max_voltage = self.wave.get_max_abs_voltage()
		range = '10V' if max_voltage >= 5 else '5V'

		self.meas = self.measure(mode='voltage', range=range, average_time=average_time, sample_rate=sample_rate)

###############
# B1530 Wrapper
class B1530:
	DEFAULT_ADDR = r'GPIB0::18::INSTR'

	def __init__(self, addr=DEFAULT_ADDR):
		b1530_methods = [func for func in dir(B1530Driver) if callable(getattr(B1530Driver, func)) and not func.startswith("__")]
		for method in b1530_methods:
			fn = getattr(B1530Driver, method)
			def wrapper_gen(func):
				def call_wrapper(*args, **kwargs):
					err_buf = io.BytesIO()
					has_err = False
					with stderr_redirector(err_buf):
						ret = func(*args, **kwargs)
						if isinstance(ret, tuple):
							err = ret[0]
							rets = ret[1:]
						else:
							err = ret
							rets = None
						has_err = (err[0] != 0)
					
					if has_err:
						raise Exception(err_buf.getvalue().decode('utf-8'))

					return rets
				return call_wrapper
			
			setattr(self, 'd_' + method, wrapper_gen(fn))

		self.chan = {
			1: WGFMU(101, 'A'),
			2: WGFMU(102, 'B'),
			3: WGFMU(201, 'C'),
			4: WGFMU(202, 'D'),
		}

		self.active_chan = {
			1: False,
			2: False,
			3: False,
			4: False,
		}

		self.pattern_name = {
			1: 'Pattern1',
			2: 'Pattern2',
			3: 'Pattern3',
			4: 'Pattern4',
		}

		self._repeat = 1
		self.result = None

		self.d_openSession(addr)

	def __del__(self):
		self.d_initialize()
		self.d_closeSession()

	def get_active_chans(self):
		return dict(filter(lambda i: self.active_chan[i[0]], self.chan.items()))

	def get_inactive_chans(self):
		return dict(filter(lambda i: not self.active_chan[i[0]], self.chan.items()))

	def get_meas_chans(self):
		return dict(filter(lambda i: i[1].meas is not None, self.chan.items()))

	def reset_configuration(self):
		for wgfmu in self.chan.values():
			wgfmu.wave = None
			wgfmu.meas = None

		self.d_initialize()

	def configure(self, repeat=0):
		self.d_clear()

		self._repeat = repeat

		for i, channel in self.chan.items():
			if channel.wave is None:
				if channel.meas is None:
					self.active_chan[i] = False
					continue
				else: # If there is a meas, we overwrite the pattern accordingly so
					channel.wave = Waveform([[channel.meas.get_total_duration() + channel.meas.average_time, 0]])
			self.active_chan[i] = True

			# Configure waves
			wf = channel.wave
			self.d_createPattern(self.pattern_name[i], wf.pattern[0][1])
			if len(wf.pattern) > 1:
				time_pattern = wf.get_time_pattern()
				voltage_pattern = wf.get_voltage_pattern()

				if time_pattern[0] == 0: # If the first time point is 0, it has been set to define the start voltage, we remove it
					time_pattern    = time_pattern[1:]
					voltage_pattern = voltage_pattern[1:]
					if len(time_pattern) == 0: # If it becomes empty, we dont add vector
						break

				self.d_addVectors(self.pattern_name[i], time_pattern, voltage_pattern, len(time_pattern))
			else:
				self.d_addVector(self.pattern_name[i], wf.pattern[0][0], wf.pattern[0][1])

			# Configure meas
			meas = channel.meas
			if meas is not None:
				meas_event_name = 'MeasEvent' + str(i)
				start_delay = meas.start_delay
				self.d_setMeasureEvent(
					self.pattern_name[i],
					meas_event_name,
					start_delay,
					meas.get_meas_count(),
					meas.sample_rate,
					meas.average_time,
					B1530Driver._measureEventData['averaged']
				)

			# Link config to the chan
			self.d_addSequence(channel.id, self.pattern_name[i], self._repeat + 1)

			# Connect and configure wgfmu hardware
			self.d_setOperationMode(channel.id, B1530Driver._operationMode['fastiv'])

			if meas is not None:
				mode = channel.meas.mode
				self.d_setMeasureMode(channel.id, B1530Driver._measureMode[mode])
				
				if mode == 'voltage':
					self.d_setForceVoltageRange(channel.id, B1530Driver._forceVoltageRange['auto'])
					self.d_setMeasureVoltageRange(channel.id, B1530Driver._measureVoltageRange[channel.meas.range])
				elif mode == 'current':
					self.d_setMeasureCurrentRange(channel.id, B1530Driver._measureCurrentRange[channel.meas.range])
				else:
					raise ValueError('Unknown measure mode: ' + mode)

			self.d_connect(channel.id)
			

	def exec(self, concat_result=True):
		self.result = []

		# If there is no active chan, we dont run anything
		if not any(self.active_chan.values()):
			return

		self.d_execute()
		self.d_waitUntilCompleted()

		meas_chan = self.get_meas_chans()
		if len(meas_chan) == 0: # If there is no channel measuring, we stop here
			return

		for j in range(self._repeat + 1):
			data = pd.DataFrame()

			for i, channel in meas_chan.items():
				if channel.meas is not None:
					count = channel.meas.get_meas_count()
					start_id = count * j
					end_id   = start_id + count

					time, meas = self.d_getMeasureValues(channel.id, 0, count * (self._repeat + 1))
					
					data['tps' + channel.name] = time[start_id:end_id]
					data[channel.name]         = meas[start_id:end_id]

			self.result.append(data)

		if concat_result:
			self.result = pd.concat(self.result)

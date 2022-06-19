from aad.extlibs import B1530Driver
from aad.extlibs.stderr_redirect import stderr_redirector
import pyvisa as visa

import pandas as pd

import io
import copy as cp
import functools as ft

################
# Utils function
################
def device_list():
	return visa.ResourceManager('@ivi').list_resources('?*')

def print_devices():
	for device in device_list():
		print(device)

################
# Waveform class
################
class Waveform:
	"""
	Waveform class
	
	Stores the pattern used to generate the waveform and provides helper functions
	
	Attributes:
		pattern: [[Delta Time (s), Voltage (V)], ...] : pattern used to generate the waveform
	"""
	def __init__(self, pattern = [[0,0]]):
		self.pattern = pattern
	
	def append(self, other):
		"""Append another waveform to self. Returns self in order to chain the calls"""
		self.pattern.extend(cp.deepcopy(other.pattern))
		return self

	def repeat(self, count):
		"""Repeat this waveform 'count' times. Returns self in order to chain the calls"""
		for _ in range(count):
			self.pattern.extend(cp.deepcopy(self.pattern))
		return self
	
	def measure(self, start_delay = 0, ignore_gnd=False, **kwargs):
		"""
		Creates a measurement with the provided parameters adapted to the waveform.
		
		Parameters:
			**kwargs, start_delay : default parameters required to construct B1530Lib.Measurement ;
			ignore_gnd: bool : Whether to ignore (when retrieving the measurements) the measurement samples when the waveform voltage is zero ;
			
		Details:
			This function will create a measurement that ignores samples that may give erroneous results after the voltage is changed.
			The 'setting_time' values come from the official B1530A datasheet.
			
			############################################################################
			#                                                                          #
			#                                      |<-setting_time->|      ^ Voltage   #
			#  v-----------------------------------■________________•___   |           #
			#                                     /¦                ¦      |           #
			#                                    / ¦                ¦      |           #
			#                                   /  ¦                ¦      |           #
			#                                  /   ¦                ¦      |           #
			#                                 /    ¦                ¦      |           #
			#  last_v---■___________________■/     ¦                ¦      |           #
			#           ^                   ^      ^                ^      -           #
			#           ¦<----------------->¦<-t ->¦                ¦                  #
			#           |when two consecut. ¦<--------------------->¦                  #
			#   v == 0, ignore_gnd?         | we ignore everything in between          #
			#                                                                          #
			#  '■' are points stored in self.pattern                                   #
			#                                                                          #
			############################################################################
			
		Returns:
			The measurement created.
		"""
		kwargs.setdefault('duration', self.get_total_duration() - start_delay)

		meas = Measurement(**kwargs)

		# From B1530A datasheet
		setting_time = 0
		if meas.mode == 'voltage':
			setting_time = {
				'5V':  85e-9,
				'10V': 110e-9,
			}[meas.range]

		elif meas.mode == 'current':
			setting_time = {
				'1uA':   37e-6,
				'10uA':  5.8e-6,
				'100uA': 820e-9,
				'1mA':   200e-9,
				'10mA':  125e-9,
			}[meas.range]
		# else:
		# 	Unknown mode, self.configure will raise except for us		

		change_sample_id = None
		total_time = 0
		for i in range(len(self.pattern)):
			t, v = self.pattern[i]
			last_v = self.pattern[i-1][1] if i > 0 else v
			total_time += t

			if abs(v - last_v) > 0.01 and change_sample_id is None: # Voltage change
				change_sample_id = meas.get_id_at(total_time)

			elif abs(v - last_v) < 0.01 and change_sample_id is not None: # Voltage fixed
				established_sample_id = min(
					change_sample_id + int((t + setting_time) / meas.sample_interval) + 1,
					meas.get_count()
				)

				meas.ignore_sample.update(range(change_sample_id, established_sample_id))

				change_sample_id = None

			if ignore_gnd and abs(last_v) < 0.01 and abs(v) < 0.01:
				last_sample_id = meas.get_id_at(total_time - t)
				current_sample_id = meas.get_id_at(total_time)

				meas.ignore_sample.update(range(last_sample_id, current_sample_id))

		return meas

	def get_time_pattern(self):
		return [p[0] for p in self.pattern]
	
	def get_voltage_pattern(self):
		return [p[1] for p in self.pattern]

	def get_total_duration(self):
		return sum(self.get_time_pattern())

	def get_max_voltage(self):
		return ft.reduce(lambda a, b: a if a[1] > b[1] else b, self.pattern)[1]

	def get_min_voltage(self):
		return ft.reduce(lambda a, b: a if a[1] < b[1] else b, self.pattern)[1]

	def get_max_abs_voltage(self):
		return ft.reduce(lambda a, b: a if abs(a[1]) > abs(b[1]) else b, self.pattern)[1]

	def get_min_abs_voltage(self):
		return ft.reduce(lambda a, b: a if abs(a[1]) < abs(b[1]) else b, self.pattern)[1]

################
# Pulse Waveform
################
class Pulse(Waveform):
	r"""
	Pulse Waveform  
	
	Special type of waveform to help generate pulses.  
	
	See the parameters below:  
	
	======================================================================================
	
	voltage----------------------------■________________■
	                                  /¦                ¦\
	                                 / ¦                ¦ \
	                                /  ¦                ¦  \
	                               /   ¦                ¦   \
	                              /    ¦                ¦    \
	                             /     ¦                ¦     \
	                            /      ¦                ¦      \
	                           /       ¦                ¦       \
	0---■____________________■/        ¦                ¦        \■____________________■
	    ^                    ^         ^                ^         ^                    ^
	    |<----interval/2---->|<-edges->|<----length---->|<-edges->|<----interval/2---->|
	
	"""
	def __init__(self, voltage, interval, edges, length):
		self.pattern = [[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]
		
		self.voltage  = voltage
		self.interval = interval
		self.edges    = edges
		self.length   = length

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
	"""
	Measurement class
	
	Stores data needed for measurements and gives helper functions
	
	Attributes:
		start_delay: float :           Time delay before starting measurement ;
		mode: 'voltage' or 'current' : Whether to measure voltage or current ; 
		range: '5V' or '10V' when 'voltage' ; '10mA', '1mA', '100uA', '10uA', '1uA' when 'current' : range used for the measurement ;
		average_time: float :          Averaging time ;
		sample_interval: float :       Interval between two measurements ;
		duration: float :              Duration of the measurement ;
		ignore_sample: set(int) :      Set of sample indices to ignore when retrieving the measurement ;
		result: pandas.DataFrame :     Object used to store the results of the measurement ;
	"""
	def __init__(self, mode, range, average_time, sample_interval, duration):
		self.start_delay = 0
		self.mode = mode
		self.range = range
		self.average_time = average_time
		self.sample_interval = sample_interval
		self.duration = duration
		self.ignore_sample = set()

		self.result = pd.DataFrame()

	def get_id_at(self, time):
		"""Returns the sample index associated with the time 'time'"""
		relative_time = time - self.start_delay

		if relative_time > self.duration:
			raise ValueError("Time greater than duration does not have an id")

		return int(relative_time / self.sample_interval)

	def get_count(self):
		"""Returns the total sample count"""
		return int(self.duration / self.sample_interval)

	def get_total_duration(self):
		"""Returns the total duration (may be different from self.duration because of rounding with self.sample_interval)"""
		return self.start_delay + self.get_count() * self.sample_interval

#############
# WGFMU Class
#############
class WGFMU:
	"""
	WGFMU Class
	
	Attributes:
		id: int : Hardware identifier of the WGFMU
		name: str : Software name of the WGFMU, will be used to store measurements
		wave: B1530Lib.Waveform : Output waveform generated by this WGFMU
		meas: B1530Lib.Measurement : Measurement to perform by this WGFMU
	"""
	def __init__(self, id: int, name = 'WGFMU'):
		self.id   = id
		self.name = name
		self.wave = None
		self.meas = None

	def measure(self, **kwargs):
		"""Shortcut for wgfmu.wave.measure"""
		if self.wave is None:
			raise ValueError("Trying to measure a 'None' waveform")
		
		return self.wave.measure(**kwargs)

	def measure_self(self, average_time, sample_interval, ignore_gnd=False):
		"""
		Creates and sets a measurement for the current waveform.
		It selects the adapted voltage range.
		"""
		max_voltage = self.wave.get_max_abs_voltage()
		range = '10V' if max_voltage >= 5 else '5V'

		self.meas = self.measure(mode='voltage', range=range, average_time=average_time, sample_interval=sample_interval, ignore_gnd=ignore_gnd)

###############
# B1530 Wrapper
###############
class B1530:
	"""
	B1530 Wrapper class
	
	* Wraps every function of the driver 'B1530.d_{DRIVER_FN_NAME}' with a Python error management
	* Provides high-level helper functions to configure, execute, retrieve and manipulate measurements
	"""
	
	DEFAULT_ADDR = r'GPIB0::18::INSTR'

	def __init__(self, addr=DEFAULT_ADDR):
		"""
		Creates the B1530 wrapper.
		
		Parameters:
			addr: str : address of the B1500A (default value: 'GPIB0::18::INST')
		"""
		
		# Wraps driver function into d_{DRIVER_FN_NAME} with error handling
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

		# WGFMU channels
		self.chan = {
			1: WGFMU(101, 'A'),
			2: WGFMU(102, 'B'),
			3: WGFMU(201, 'C'),
			4: WGFMU(202, 'D'),
		}

		# By default, no chan is active
		self.active_chan = {
			1: False,
			2: False,
			3: False,
			4: False,
		}

		# They need to be unique so not created from self.chan[i].name
		self.pattern_name = {
			1: 'Pattern1',
			2: 'Pattern2',
			3: 'Pattern3',
			4: 'Pattern4',
		}

		self._repeat = 0

		self.d_openSession(addr)

	def __del__(self):
		self.d_initialize()
		self.d_closeSession()

	def get_active_chans(self):
		"""Returns the list of active channels i.e. that either generates a wave or make a measurement or both."""
		return dict(filter(lambda i: self.active_chan[i[0]], self.chan.items()))

	def get_inactive_chans(self):
		"""Returns the list of inactive channels i.e. that neither generates a wave nor make a measurement."""
		return dict(filter(lambda i: not self.active_chan[i[0]], self.chan.items()))

	def get_meas_chans(self):
		"""Returns the list of channels that make a measurement"""
		return dict(filter(lambda i: i[1].meas is not None, self.chan.items()))

	def reset_configuration(self):
		"""
		Resets the WGFMUs configuration.
		To use after a previous one in order to start a configuration from scratch
		"""
		for wgfmu in self.chan.values():
			wgfmu.wave = None
			wgfmu.meas = None

		self.d_initialize()

	def configure(self, repeat=0):
		"""
		Applies the WGFMUs configuration set with wgfmu.wave/meas.
		
		Parameters:
			repeat: int : how many times to repeat the pattern
		"""
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

				self.d_addVectors(self.pattern_name[i], time_pattern, voltage_pattern, len(time_pattern))
			elif wf.pattern[0][0] != 0: # DC setting
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
					meas.get_count(),
					meas.sample_interval,
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
			

	def exec(self, concat_repetitions=True):
		"""
		Executes the WGFMUs patterns (waveform generation and/or measurements)
		
		Parameters:
			concat_repetitions: bool : Concat, or keep in an array, the different measurements results associated to the repetitions
			
		Details:
			Executes the patterns and store the measurement results in chan[i].meas.result
			in pandas.DataFrame with column 'time + {channel.name}' for the time associated with the measurement '{channel.name}'
		"""
		pattern_count = self._repeat + 1

		# If there is no active chan, we dont run anything
		if not any(self.active_chan.values()):
			return

		self.d_execute()
		self.d_waitUntilCompleted()

		meas_chan = self.get_meas_chans()
		if len(meas_chan) == 0: # If there is no channel measuring, we stop here
			return

		for channel in meas_chan.values():
			meas_count = channel.meas.get_count()
			data = pd.DataFrame()

			time, meas = self.d_getMeasureValues(channel.id, 0, meas_count * pattern_count)

			for i in range(pattern_count):
				start_id = meas_count * i
				end_id   = start_id + meas_count

				data['time' + channel.name] = time[start_id:end_id]
				data[channel.name]          = meas[start_id:end_id]

				data.drop(channel.meas.ignore_sample, inplace = True) # Drop the ignored samples

			if concat_repetitions:
				data = pd.concat(data)

			data.reset_index(inplace=True, drop=True)
			channel.meas.result = data

	def get_result(self, *args, join_outer=True):
		"""
		Gather the provided chans' measurements in a pandas.DataFrame
		
		Parameters:
			*args: channels to select (can be theirs ids or names)
			join_outer: Wether to perform an outer (if True) or inner (otherwise) merge
			Details:
				outer merge: will add NaN to missing measurements of channel compared to the other(s)
				inner merge: will remove the extra measurements of a channel compared to the other(s)
				
		Returns:
			The gathered results.
		"""
		result = None

		for arg in args:
			chan = None
			if isinstance(arg, int):
				chan = self.chan[arg]
				
			elif isinstance(arg, str):
				for c in self.chan.values():
					print(c.name, arg)
					if c.name == arg:
						chan = c
						break
				if chan is None:
					raise ValueError("Unknown channel name: " + arg)

			chan_time_name = 'time' + chan.name
			renamed = chan.meas.result.rename({chan_time_name: 'time'}, axis=1)

			if result is None:
				result = renamed
			else:
				result = result.merge(renamed, on = 'time', how = 'outer' if join_outer else 'inner')

		return result


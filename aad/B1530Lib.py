from aad.extlibs import B1530Driver
from aad.extlibs.stderr_redirect import stderr_redirector
import pyvisa as visa

import io

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
	def __init__(self, **kwargs):
		# Pattern: [[Time (s), Voltage (V)], ...]
		for key in kwargs:
			setattr(self, key, kwargs[key])
		
		# If no pattern has been set, we create a null one
		if not hasattr(self, 'pattern') or len(self.pattern) == 0:
			self.pattern = [[0, 0]]
	
	def measure(self, **kwargs):
		meas = Measurement()
		return meas

	def get_time_pattern(self):
		return [p[0] for p in self.pattern]
	
	def get_voltage_pattern(self):
		return [p[1] for p in self.pattern]

	def get_total_duration(self):
		return sum(self.get_time_pattern())

class Pulse(Waveform):
	def __init__(self, **kwargs):
		self.pattern = [[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]
		super().__init__(**kwargs)

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

	def measure(self, **kwargs):
		kwargs.setdefault('duration', -1)

		meas = Measurement(**kwargs)
		if kwargs.get('when_established', False):
			meas.start_delay += self.pattern[0][0] + self.pattern[1][0]
			meas.duration = self.length
		if meas.duration == -1:
			meas.duration = self.get_total_duration() - meas.start_delay
		
		return meas

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

	def get_measurement_count(self):
		return int(self.duration / self.sample_rate)

	def get_total_duration(self):
		return self.start_delay + self.duration

	def get_result(self, index = -1):
		return self.result if index == -1 else self.result[index]

#############
# WGFMU Class
class WGFMU:
	def __init__(self, id: int):
		self.id = id
		self.waveform = None
		self.measurement = None

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
			1: WGFMU(101),
			2: WGFMU(102),
			3: WGFMU(201),
			4: WGFMU(202),
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

		self.repeat = 1

		self.d_openSession(addr)

	def __del__(self):
		self.d_initialize()
		self.d_closeSession()

	def configure(self, repeat=1):
		self.d_clear()

		self.repeat = repeat

		for i, channel in self.chan.items():
			if channel.waveform is None:
				if channel.measurement is None:
					self.active_chan[i] = False
					continue
				else: # If there is a measurement, we overwrite the pattern accordingly so
					channel.waveform = Waveform(pattern=[[channel.measurement.get_total_duration(), 0]])
			self.active_chan[i] = True

			# Configure waveforms
			wf = channel.waveform
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

			# Configure measurement
			meas = channel.measurement
			if meas is not None:
				meas_event_name = 'MeasEvent' + str(i)
				start_delay = meas.start_delay
				self.d_setMeasureEvent(
					self.pattern_name[i],
					meas_event_name,
					start_delay,
					meas.get_measurement_count(),
					meas.sample_rate,
					meas.average_time,
					B1530Driver._measureEventData['averaged']
				)

			# Link config to the chan
			self.d_addSequence(channel.id, self.pattern_name[i], self.repeat)

	def get_active_chans(self):
		return dict(filter(lambda i: self.active_chan[i[0]], self.chan.items()))

	def get_inactive_chans(self):
		return dict(filter(lambda i: not self.active_chan[i[0]], self.chan.items()))

	def exec(self):
		self.d_initialize()

		chan = self.get_active_chans()
		if len(chan) == 0:
			return

		for i, channel in chan.items():
			self.d_setOperationMode(channel.id, B1530Driver._operationMode['fastiv'])

			if channel.measurement is not None:
				mode = channel.measurement.mode
				self.d_setMeasureMode(channel.id, B1530Driver._measureMode[mode])
				
				if mode == 'voltage':
					self.d_setForceVoltageRange(channel.id, B1530Driver._forceVoltageRange['auto'])
					self.d_setMeasureVoltageRange(channel.id, B1530Driver._measureVoltageRange[channel.measurement.range])
				else:
					self.d_setMeasureCurrentRange(channel.id, B1530Driver._measureCurrentRange[channel.measurement.range])

			self.d_connect(channel.id)

		self.d_execute()
		self.d_waitUntilCompleted()

		for i, channel in chan.items():
			if channel.measurement is not None:
				count = channel.measurement.get_measurement_count()
				time, meas = self.d_getMeasureValues(channel.id, 0, count * self.repeat)

				channel.measurement.result = []
				for j in range(self.repeat):
					start_id = count * j
					end_id   = start_id + count
					channel.measurement.result.append(list(zip(time[start_id:end_id], meas[start_id:end_id])))
# Awesome Array Python Driver

Python drivers to control the Awesome Array @ C2N.  

## Installation
This library requires:  
* ⚠️ 32 bits version of Python
* `pyserial` version 3.5 or any other compatible version
* `pyvisa` version 1.11.3 or any other compatible version
* The associated NI-VISA drivers, see [the official doc](https://pyvisa.readthedocs.io/en/latest/faq/getting_nivisa.html#faq-getting-nivisa). (⚠️ 32 bits version required)

### Global installation
1. Download and install the NI-VISA drivers
2. `B1530driver.py` and `B1530ErrorModule.py` are licensed and cannot be shared on GitHub, they are therefore missing on this repo.  
You must copy them at the location `extlibs/B1530Driver`, aside the `__init__.py` file.  
3. You can then go back to the root of this repo and run the command `python setup.py install`. The script should download the Python library and install `aad` globally.

You can now use `aad` as a regular library, by using `import aad` in any directory on the computer.

---
#### **Linux users only**
Only `mcdriver` is available on Linux. In order to test it out, you will need to add your user to the `dialout` group:  
```bash
sudo usermod -aG dialout $USER
```



## Library Architecture
<p align="center">
	<img src="misc/aad_arch.png?raw=true" alt="Library Architecture Diagram" />
</p>

## Usage
### Awesome Array Driver
The high-level driver intended to be used.  
See [`demo/aadriver.ipynb`](demo/aadriver.ipynb) for a demo. 

### Microcontroller Driver
This should not be used unless a low-level change with the µc is needed for the `aad`.  
See [`demo/mcdriver.ipynb`](demo/mcdriver.ipynb) for a demo.

### B1530 Library
This should not be used unless a low-level change with the B1530 is needed for the `aad`.  
See [`demo/B1530lib.ipynb`](demo/B1530lib.ipynb) for a demo.

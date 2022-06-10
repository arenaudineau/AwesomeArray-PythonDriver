# Awesome Array Python Driver

Python drivers to control the Awesome Array @ C2N.  

## Installation
This library requires:  
* `pyserial` version 0.0.97 or any other compatible 
* ...

#### **Linux users only**
Only `mcdriver` is available on Linux. In order to test it out, you will need to add your user to the `dialout` group:  
> sudo usermod -aG dialout $USER`

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
Coming soon...
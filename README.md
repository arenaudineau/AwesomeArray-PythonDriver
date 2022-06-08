# Awesome Array Python Driver

Python drivers to control the Awesome Array @ C2N.  

## Installation
This library requires:  
* `pyserial` version 0.0.97 or any other compatible 
* `lab library` @ [GitHub Repo](https://github.com/tvbv/controle_manip)

#### **Linux users only**
`lab library` is not available on Linux but to test out only `lldriver`, you will need to add your user to the `dialout` group:  
> sudo usermod -aG dialout $USER`

## Library Architecture
<p align="center">
	<img src="misc/add_arch.png" alt="Library Architecture Diagram" />
</p>

## Usage
### Low-Level Driver
This should not be used unless a low-level change is needed for the `aad`.  
See [`demo/lldriver.ipynb`](demo/lldriver.ipynb) for a demo.

### Awesome Array Driver
The high-level driver intended to be used.  
See [`demo/aadriver.ipynb`](demo/aadriver.ipynb) for a demo. 
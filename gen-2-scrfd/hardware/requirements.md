# Parts and requirements

[Hardware overview](README.md)

These are deployment requirements, not a shopping list: the maintainer reports
that the required hardware is already available. Quantities are for one unit.

## Core assembly

| Part | Quantity | Requirement / purpose |
| --- | --- | --- |
| Raspberry Pi 5 | 1 | Raspberry Pi 5 (4GB RAM) |
| Raspberry Pi Camera Module 3 | 1 | Record standard/wide and visible-light/NoIR variant |
| Pi 5 camera cable | 1 | 22-pin Pi end to 15-pin Camera Module 3 end; appropriate length |
| USB-C power supply | 1 | Suitable 5V/5A supply; official 27W supply is a supported starting choice |
| Active cooling | 1 | Pi 5-compatible cooler with clearance and airflow |
| Storage | 1 | microSD with 64-bit Raspberry Pi OS; 64GB microSD card installed |
| Stable lighting | As needed | Even illumination at the capture position; avoid strong backlighting |
| Camera mount and standoffs | 1 set | Hold the camera steady and avoid cable strain or PCB shorts |
| Breadboard and jumper wires | 1 set | Low-current signal prototyping; select connectors for the actual modules |
| OLED display | 1 | Record controller, resolution, interface, address and supply voltage; Pi-compatible logic |
| Enclosure | 1 | Space for cooling, camera view, cables and insulated electronics |

A network connection or another computer is useful for initial setup. Model files
and dependencies can be downloaded beforehand; face inference runs locally.
A monitor/keyboard is optional when configuring the Pi through SSH. Generation 2 utilizes
ONNX Runtime with ARM NEON SIMD on the Pi 5's Cortex-A76 CPU (<8ms latency), requiring no external accelerator.

## Optional outputs and a physical lock

| Part | When needed | Selection requirement |
| --- | --- | --- |
| Red/green LEDs with series resistors | Extra visible feedback | Size resistors to LED specifications and GPIO limits |
| Buzzer with suitable driver | Audible feedback | Use a driver when the load exceeds GPIO capability |
| Lock or demonstration actuator | Physical access demonstration | Document rated voltage/current and desired power-loss behavior |
| Relay/MOSFET driver | Switching an actuator | Accept 3.3V control and support the load's DC/inrush ratings |
| Actuator power supply | Powered lock/actuator | Match rated voltage and peak current; do not power the load from GPIO |
| Transient suppression | Inductive load | Use the manufacturer's suitable protection; some drivers include it |
| Fuse, terminals and suitable wiring | Powered actuator circuit | Match wire/load ratings; keep load current off the breadboard |
| Exit/release mechanism | Door installation | Provide independent release appropriate to the installation |
| Door-position sensor | Confirm actual door state | Optional; callback success alone does not prove a door opened |

An OLED or LED can demonstrate an access decision without a lock. A physical door
needs its own verified driver, release behavior and installation requirements.

## Sources

- [Raspberry Pi 5 power and cooling](https://www.raspberrypi.com/products/raspberry-pi-5/)
- [Official camera connection guide](https://www.raspberrypi.com/documentation/accessories/camera.html)
- [GPIO reference](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header)
- [Picamera2 manual](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf)

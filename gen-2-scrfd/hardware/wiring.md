# Connections and wiring requirements

[Hardware overview](README.md)

Disconnect power before changing connections. This guide does not specify the
installed relay pin or OLED model because those details have not been supplied.
Record actual connections in [the deployment template](deployment.example.md).

## Camera, storage and cooling

1. Fit the Pi 5-compatible cooler and connect it to the dedicated fan connector
   according to the cooler instructions.
2. Connect Camera Module 3 with the Pi 5 22-pin-to-15-pin camera cable. Follow the
   connector orientation shown in the [official camera guide](https://www.raspberrypi.com/documentation/accessories/camera.html).
3. Insert the OS storage, secure the camera mount and route the ribbon cable
   without sharp bends. Leave the cooler and airflow clear.
4. Connect the suitable USB-C supply after inspecting the assembly.

## Reference wiring for a compatible I2C OLED

Use this table only if the selected OLED supports I2C, 3.3V supply and 3.3V signals.
A SPI OLED needs different wiring. Verify the module's labelled pins and datasheet;
connector order is not universal.

| OLED signal | Pi physical header pin | BCM GPIO / function |
| --- | --- | --- |
| VCC | 1 | 3.3V power |
| GND | 6 | Ground |
| SDA | 3 | GPIO2 / I2C data |
| SCL | 5 | GPIO3 / I2C clock |

Physical pin numbers and BCM GPIO numbers are different. Confirm them with the
Pi's `pinout` command and the [official GPIO reference](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header).
Do not allow module pull-ups to pull GPIO signals to 5V. Record the controller,
resolution and detected I2C address instead of assuming them.

## Actuator interface

- Select a free BCM GPIO only after recording all other peripherals.
- Match the driver input voltage and active-high/active-low behavior.
- Use the actuator's rated supply and driver; GPIO carries a control signal only.
- Follow the driver manufacturer's grounding/isolation schematic. Isolated and
  non-isolated boards may require different ground and jumper arrangements.
- Use load-rated contacts/wiring, suitable suppression and overcurrent protection.
- Establish the inactive output state at boot, shutdown and application failure.
- Set a bounded action duration and ensure the driver returns to its inactive state
  even if software raises an exception.

Connect the driver through `app.config['ACCESS_ACTION']` as described in
[decision safety](../docs/decision-safety.md). The callback is invoked for allowed
actions outside the shared cooldown. It is not a general display event feed:
showing every denial or fault on the OLED requires display integration too.
No hardware driver or GPIO assignment is automatically configured by this folder.

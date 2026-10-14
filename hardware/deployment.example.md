# Deployment record template

Copy to `hardware/deployment.local.md` (ignored by Git). Do not store credentials,
face images or embeddings in this template. Blank fields mean not recorded.

## Components

| Field | Installed value |
| --- | --- |
| Pi 5 RAM / revision | |
| Camera Module 3 variant / cable length | |
| Power supply model / rating | |
| Cooler | |
| Storage / capacity | |
| OS version / architecture | |
| OLED model / controller / interface / resolution | |
| OLED address / supply voltage | |
| Actuator / rated voltage / peak current | |
| Driver model / input voltage / polarity | |
| Load power supply / protection | |
| Mounting / lighting | |

## Actual connections

| Peripheral signal | Physical pin / connector | BCM GPIO | Voltage / notes |
| --- | --- | --- | --- |
| Camera | | | |
| OLED power / ground | | | |
| OLED data / clock | | | |
| Actuator control | | | |
| Exit / release | | | |
| Door sensor (if used) | | | |

## Software and action behavior

- Software revision:
- Python / OpenCV / Picamera2 / model versions:
- Camera resolution / frame rate / orientation:
- Actuator callback module:
- Inactive level / boot and shutdown behavior:
- Action duration / timeout / cooldown:
- Release and power-loss behavior:
- Spoof-resistance mechanism and test reference:


Performance evaluation is a separate final step. Reference the saved evaluation
report and conditions here only after functional testing passes.

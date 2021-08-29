# Xiaomi Raw

![GitHub actions](https://github.com/syssi/xiaomi_raw/actions/workflows/ci.yaml/badge.svg)
![GitHub stars](https://img.shields.io/github/stars/syssi/xiaomi_raw)
![GitHub forks](https://img.shields.io/github/forks/syssi/xiaomi_raw)
![GitHub watchers](https://img.shields.io/github/watchers/syssi/xiaomi_raw)
[!["Buy Me A Coffee"](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg)](https://www.buymeacoffee.com/syssi)

This is a custom component for home assistant to faciliate the reverse engeneering of Xiaomi MiIO devices.

Please follow the instructions on [Retrieving the Access Token](https://home-assistant.io/components/xiaomi/#retrieving-the-access-token) to get the API token to use in the configuration.yaml file.

Credits: Thanks to [Rytilahti](https://github.com/rytilahti/python-miio) for all the work.

## Features

* Power (on, off)
* Sensor value (RSSI in dBm of the WiFi connection)
* Raw command (method + params)
* Set properties (property list)
* Attributes (can be extended by "Set properties")
  - model
  - firmware_version
  - hardware_version
  - properties


## Install

You can install this custom component by adding this repository ([https://github.com/syssi/xiaomi_raw](https://github.com/syssi/xiaomi_raw/)) to [HACS](https://hacs.xyz/) in the settings menu of HACS first. You will find the custom component in the integration menu afterwards, look for 'Xiaomi MiIO Raw'. Alternatively, you can install it manually by copying the custom_component folder to your Home Assistant configuration folder.


## Setup

```yaml
# configuration.yaml

logger:
  default: warn
  logs:
    custom_components.sensor.xiaomi_miio_raw: info
    miio: info

sensor:
  - platform: xiaomi_miio_raw
    name: Any Xiaomi MiIO device
    host: 192.168.130.73
    token: 56197337f51f287d69a8a16cf0677379
    # Optional and device specific config parameters
    sensor_property: 'humidity'
    sensor_unit: '%'
    default_properties_getter: 'get_prop'
    default_properties:
      - humidity
      - power
      - temperature

  # If your device doesn't support multiple named properties
  - platform: xiaomi_miio_raw
    name: Any Xiaomi MiIO device
    host: 192.168.130.73
    token: 56197337f51f287d69a8a16cf0677379
    sensor_property: 'unnamed6'
    default_properties_getter: 'get_prop'
    default_properties:
      - 'all'

switch:
  - platform: xiaomi_miio_raw
    name: Any Xiaomi MiIO device
    host: 192.168.130.73
    token: 56197337f51f287d69a8a16cf0677379
    turn_on_command: 'set_power'
    turn_on_parameters: 'on'
    turn_off_command: 'set_power'
    turn_off_parameters: 'off'
    state_property: 'power'
    state_property_getter: 'get_prop'
    state_on_value: 'on'
    state_off_value: 'off'

```

Another example configuration to control a miot device (`chuangmi.plug.212a01`). Thanks to @lovelylain for adding miot support to the sensor entity!

```yaml

sensor:
  - platform: xiaomi_miio_raw
    name: Smart Plug
    host: 192.168.30.74
    token: d880f00295a6db218b29a1879eea4663
    max_properties: 10
    default_properties_getter: get_properties
    default_properties:
      - "{'did': 'power', 'piid': 1, 'siid': 2}"
      - "{'did': 'temperature', 'piid': 6, 'siid': 2}"
      - "{'did': 'indicator_light', 'piid': 1, 'siid': 3}"
      - "{'did': 'on_duration', 'piid': 1, 'siid': 4}"
      - "{'did': 'off_duration', 'piid': 2, 'siid': 4}"
      - "{'did': 'countdown', 'piid': 3, 'siid': 4}"
      - "{'did': 'task_switch', 'piid': 4, 'siid': 4}"
      - "{'did': 'countdown_info', 'piid': 5, 'siid': 4}"
      - "{'did': 'power_consumption', 'piid': 1, 'siid': 5}"
      - "{'did': 'electric_current', 'piid': 2, 'siid': 5}"
      - "{'did': 'voltage', 'piid': 3, 'siid': 5}"
      - "{'did': 'electric_power', 'piid': 6, 'siid': 5}"
  - platform: template
    sensors:
      smart_plug_power:
        unique_id: smart_plug_power
        unit_of_measurement: W
        value_template: "{{ state_attr('sensor.smart_plug', 'electric_power')|int / 100 }}"
        availability_template: "{{ not is_state('sensor.smart_plug', 'unavailable') }}"
        icon_template: "mdi:flash"

switch:
  - platform: template
    switches:
      smart_plug_switch:
        unique_id: smart_plug_switch
        value_template: "{{ state_attr('sensor.smart_plug', 'power') }}"
        availability_template: "{{ not is_state('sensor.smart_plug', 'unavailable') }}"
        turn_on:
          service: xiaomi_miio_raw.sensor_raw_command
          data:
            entity_id: sensor.smart_plug
            method: set_properties
            params:
              - did: power
                siid: 2
                piid: 1
                value: true
        turn_off:
          service: xiaomi_miio_raw.sensor_raw_command
          data:
            entity_id: sensor.smart_plug
            method: set_properties
            params:
              - did: power
                siid: 2
                piid: 1
                value: false

```

Configuration variables (sensor platform):
- **host** (*Required*): The IP of your miio device.
- **token** (*Required*): The API token of your miio device.
- **name** (*Optional*): The name of your miio device.
- **max_properties** (*Optional*): The number of retrieved properties per API call
- **sensor_property** (*Optional*): Property used as sensor value. WiFi RSSI if unset.
- **sensor_unit** (*Optional*): Measurement unit of the property. dBm if unset.
- **default_properties** (*Optional*): List of requested properties. ['power'] if unset.
- **default_properties_getter** (*Optional*): Method to requested properties. Default value: `get_prop`

Configuration variables (switch platform):
- **host** (*Required*): The IP of your miio device.
- **token** (*Required*): The API token of your miio device.
- **name** (*Optional*): The name of your miio device.
- **turn_on_command** (*Optional*): The miIO command to send on `switch.turn_on`. Default value: `set_power`.
- **turn_on_parameters** (*Optional*): The miIO commands parameters. Default value: `on`.
- **turn_off_command** (*Optional*): The miIO command to send on `switch.turn_off`. Default value: `set_power`.
- **turn_off_parameters** (*Optional*): The miIO commands parameters. Default value: `off`.
- **state_property** (*Optional*): The miIO property which provides the current state.
- **state_property_getter** (*Optional*): Method to requested properties. Default value: `get_prop`
- **state_on_value** (*Optional*): The value of the `state_property` which indicates the `is_on` state. Default value: 'on'
- **state_off_value** (*Optional*): The value of the `state_property` which indicates the `is_off` state. Default value: 'off'

## Debugging

If the custom component doesn't work out of the box for your device please update your configuration to increase log level:

```yaml
# configuration.yaml

logger:
  default: warn
  logs:
    custom_components.sensor.xiaomi_miio_raw: debug
    custom_components.switch.xiaomi_miio_raw: debug
    miio: debug
```

## Platform services

#### Service `xiaomi_miio_raw.sensor_set_properties`

Update the list of the retrieved properties.

| Service data attribute    | Optional | Description                                                                |
|---------------------------|----------|----------------------------------------------------------------------------|
| `entity_id`               |       no | Only act on a specific Xiaomi miIO fan entity.                             |
| `properties`              |      yes | List of properties. The default is `['power']`                             |


```
# http://localhost:8123/dev-service

Service: xiaomi_miio_raw.sensor_set_properties
Service Data: {"properties":["power","temperature","humidity","aqi"]}
```

#### Service `xiaomi_miio_raw.sensor_raw_command`

Send a command to the device.

| Service data attribute    | Optional | Description                                                                |
|---------------------------|----------|----------------------------------------------------------------------------|
| `entity_id`               |       no | Only act on a specific Xiaomi miIO fan entity.                             |
| `method`                  |       no | Method name of the command. Example: `set_power`                           |
| `params`                  |      yes | List of parameters. Example: `['on']`                                      |


```
# http://localhost:8123/dev-service

# Turn the device on
Service: xiaomi_miio_raw.sensor_raw_command
Service Data: {"method":"set_power","params":["on"]}

# Turn the device off
Service: xiaomi_miio_raw.sensor_raw_command
Service Data: {"method":"set_power","params":["off"]}

# Request some properties
Service: xiaomi_miio_raw.sensor_raw_command
Service Data: {"method":"get_prop","params":["power","temperature","humidity","aqi"]}
```

#### Service `xiaomi_miio_raw.sensor_turn_on`

Turn the device on.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |       no | Only act on a specific xiaomi miio entity.                           |

#### Service `xiaomi_miio_raw.sensor_turn_off`

Turn the device off.

| Service data attribute    | Optional | Description                                                          |
|---------------------------|----------|----------------------------------------------------------------------|
| `entity_id`               |       no | Only act on a specific Xiaomi miIO fan entity.                       |


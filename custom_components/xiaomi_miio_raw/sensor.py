import asyncio
import logging
from ast import literal_eval
from functools import partial

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from miio import Device, DeviceException

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Device"
DATA_KEY = "sensor.xiaomi_miio_raw"
DOMAIN = "xiaomi_miio_raw"

CONF_SENSOR_PROPERTY = "sensor_property"
CONF_SENSOR_UNIT = "sensor_unit"
CONF_DEFAULT_PROPERTIES = "default_properties"
CONF_DEFAULT_PROPERTIES_GETTER = "default_properties_getter"
CONF_MAX_PROPERTIES = "max_properties"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SENSOR_PROPERTY): cv.string,
        vol.Optional(CONF_SENSOR_UNIT): cv.string,
        vol.Optional(CONF_DEFAULT_PROPERTIES_GETTER, default="get_prop"): cv.string,
        vol.Optional(CONF_DEFAULT_PROPERTIES, default=["power"]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_MAX_PROPERTIES, default=15): cv.positive_int,
    }
)

ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"
ATTR_PROPERTIES = "properties"
ATTR_SENSOR_PROPERTY = "sensor_property"
ATTR_METHOD = "method"
ATTR_PARAMS = "params"
CMD_GET_PROPERTIES = "get_properties"

SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

SERVICE_SCHEMA_SET_PROPERTIES = SERVICE_SCHEMA.extend(
    {
        vol.Optional(ATTR_PROPERTIES, default=["power"]): vol.All(
            cv.ensure_list, [cv.string]
        )
    }
)

SERVICE_SCHEMA_COMMAND = SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_METHOD): cv.string,
        vol.Optional(ATTR_PARAMS, default=[]): vol.All(cv.ensure_list),
    }
)

SERVICE_CUSTOM_TURN_ON = "sensor_turn_on"
SERVICE_CUSTOM_TURN_OFF = "sensor_turn_off"
SERVICE_SET_PROPERTIES = "sensor_set_properties"
SERVICE_COMMAND = "sensor_raw_command"

SERVICE_TO_METHOD = {
    SERVICE_CUSTOM_TURN_ON: {"method": "async_turn_on"},
    SERVICE_CUSTOM_TURN_OFF: {"method": "async_turn_off"},
    SERVICE_SET_PROPERTIES: {
        "method": "async_set_properties",
        "schema": SERVICE_SCHEMA_SET_PROPERTIES,
    },
    SERVICE_COMMAND: {"method": "async_command", "schema": SERVICE_SCHEMA_COMMAND},
}


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor from config."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        miio_device = Device(host, token)
        device_info = miio_device.info()
        model = device_info.model
        _LOGGER.info(
            "%s %s %s detected",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )

        device = XiaomiMiioGenericDevice(miio_device, config, device_info)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)

    @asyncio.coroutine
    def async_service_handler(service):
        """Map services to methods on XiaomiMiioDevice."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [
                device
                for device in hass.data[DATA_KEY].values()
                if device.entity_id in entity_ids
            ]
        else:
            devices = hass.data[DATA_KEY].values()

        update_tasks = []
        for device in devices:
            yield from getattr(device, method["method"])(**params)
            update_tasks.append(device.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service].get("schema", SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=schema
        )


class XiaomiMiioGenericDevice(Entity):
    """Representation of a Xiaomi Air Quality Monitor."""

    def __init__(self, device, config, device_info):
        """Initialize the entity."""
        self._device = device

        self._name = config.get(CONF_NAME)
        self._sensor_property = config.get(CONF_SENSOR_PROPERTY)
        self._unit_of_measurement = config.get(CONF_SENSOR_UNIT)
        self._properties = config.get(CONF_DEFAULT_PROPERTIES)
        self._properties_getter = config.get(CONF_DEFAULT_PROPERTIES_GETTER)
        self._max_properties = config.get(CONF_MAX_PROPERTIES)

        if (
            self._properties_getter != CMD_GET_PROPERTIES
            and self._sensor_property is not None
            and not self._sensor_property.startswith("unnamed")
        ):
            self._properties.append(self._sensor_property)

        self._model = device_info.model
        self._unique_id = "{}-{}-{}".format(
            device_info.model, device_info.mac_address, self._sensor_property
        )
        self._icon = "mdi:flask-outline"

        self._available = None
        self._state = None
        properties = self.set_properties(self._properties)
        self._state_attrs = {
            ATTR_MODEL: self._model,
            ATTR_FIRMWARE_VERSION: device_info.firmware_version,
            ATTR_HARDWARE_VERSION: device_info.hardware_version,
            ATTR_PROPERTIES: properties,
            ATTR_SENSOR_PROPERTY: self._sensor_property,
        }

    def set_properties(self, properties):
        if self._properties_getter != CMD_GET_PROPERTIES:
            self._properties = list(set(properties))
            return self._properties
        else:
            attrs = {}
            for p in properties:
                p = literal_eval(p)
                attrs[p["siid"], p["piid"]] = p.pop("name", p["did"]), p
            self._properties = attrs
            return list(i[0] for i in attrs.values())

    @property
    def should_poll(self):
        """Poll the miio device."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes of the device."""
        return self._state_attrs

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a device command handling error messages."""
        try:
            result = await self.hass.async_add_job(partial(func, *args, **kwargs))

            _LOGGER.info("Response received from miio device: %s", result)

            return result and (
                result[0] == "ok" or result[0] == "OK" or result[0]["code"] == 0
            )
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def async_update(self):
        """Fetch state from the miio device."""
        attrs = self._properties
        is_new = isinstance(attrs, dict)
        try:
            # A single request is limited to 16 properties. Therefore the
            # properties are divided into multiple requests
            _props = list(i[1] for i in attrs.values()) if is_new else attrs.copy()
            _LOGGER.debug("Request of the get properties call: %s", _props)

            values = []
            while _props:
                values.extend(
                    await self.hass.async_add_job(
                        self._device.send,
                        self._properties_getter,
                        _props[: self._max_properties],
                    )
                )
                _props[:] = _props[self._max_properties :]

            _LOGGER.debug("Response of the get properties call: %s", values)
        except DeviceException as ex:
            self._available = False
            _LOGGER.warning("Got exception while fetching the state: %s", ex)
            return

        properties_count = len(attrs)
        values_count = len(values)
        if properties_count != values_count:
            if not is_new and properties_count == 1 and attrs[0] == "all":
                attrs = ["unnamed" + str(i) for i in range(values_count)]
            else:
                _LOGGER.debug(
                    "Count (%s) of requested properties does not match the "
                    "count (%s) of received values.",
                    properties_count,
                    values_count,
                )

        if is_new:
            state = dict(
                (attrs[i["siid"], i["piid"]][0], i.get("value")) for i in values
            )
        else:
            state = dict(zip(attrs, values))

        _LOGGER.info("New state: %s", state)

        self._available = True
        self._state_attrs.update(state)

        if self._sensor_property is not None:
            self._state = state.get(self._sensor_property)
        else:
            try:
                device_info = await self.hass.async_add_job(self._device.info)
                self._state = device_info.accesspoint.get("rssi", self._model)

            except DeviceException as ex:
                self._available = False
                _LOGGER.warning("Got exception while fetching device info: %s", ex)

    async def async_turn_on(self, **kwargs):
        """Turn the miio device on."""
        await self._try_command(
            "Turning the miio device on failed.", self._device.send, "set_power", ["on"]
        )

    async def async_turn_off(self, **kwargs):
        """Turn the miio device off."""
        await self._try_command(
            "Turning the miio device off failed.",
            self._device.send,
            "set_power",
            ["off"],
        )

    async def async_set_properties(self, properties: list):
        """Set properties. Will be retrieved on next update."""
        if (
            self._properties_getter != CMD_GET_PROPERTIES
            and self._sensor_property is not None
            and not self._sensor_property.startswith("unnamed")
        ):
            properties.append(self._sensor_property)

        properties = self.set_properties(properties)
        self._state_attrs.update({ATTR_PROPERTIES: properties})

    async def async_command(self, method: str, params):
        """Send a raw command to the device."""
        _LOGGER.info("Sending command: %s %s" % (method, params))
        await self._try_command(
            "Turning the miio device on failed.", self._device.send, method, params
        )

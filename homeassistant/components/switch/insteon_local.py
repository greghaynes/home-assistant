"""
Support for Insteon switch devices via local hub support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.insteon_local/
"""
import json
import logging
import os
from datetime import timedelta

from homeassistant.components.switch import SwitchDevice
from homeassistant.loader import get_component
import homeassistant.util as util

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['insteon_local']
DOMAIN = 'switch'

INSTEON_LOCAL_SWITCH_CONF = 'insteon_local_switch.conf'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Insteon local switch platform."""
    insteonhub = hass.data['insteon_local']

    conf_switches = config_from_file(hass.config.path(
        INSTEON_LOCAL_SWITCH_CONF))
    if len(conf_switches):
        for device_id in conf_switches:
            setup_switch(
                device_id, conf_switches[device_id], insteonhub, hass,
                add_devices)

    linked = insteonhub.get_linked()

    for device_id in linked:
        if linked[device_id]['cat_type'] == 'switch'\
                and device_id not in conf_switches:
            request_configuration(device_id, insteonhub,
                                  linked[device_id]['model_name'] + ' ' +
                                  linked[device_id]['sku'], hass, add_devices)


def request_configuration(device_id, insteonhub, model, hass,
                          add_devices_callback):
    """Request configuration steps from the user."""
    configurator = get_component('configurator')

    # We got an error if this method is called while we are configuring
    if device_id in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[device_id], 'Failed to register, please try again.')

        return

    def insteon_switch_config_callback(data):
        """The actions to do when our configuration callback is called."""
        setup_switch(device_id, data.get('name'), insteonhub, hass,
                     add_devices_callback)

    _CONFIGURING[device_id] = configurator.request_config(
        hass, 'Insteon Switch ' + model + ' addr: ' + device_id,
        insteon_switch_config_callback,
        description=('Enter a name for ' + model + ' addr: ' + device_id),
        entity_picture='/static/images/config_insteon.png',
        submit_caption='Confirm',
        fields=[{'id': 'name', 'name': 'Name', 'type': ''}]
    )


def setup_switch(device_id, name, insteonhub, hass, add_devices_callback):
    """Set up the switch."""
    if device_id in _CONFIGURING:
        request_id = _CONFIGURING.pop(device_id)
        configurator = get_component('configurator')
        configurator.request_done(request_id)
        _LOGGER.info("Device configuration done!")

    conf_switch = config_from_file(hass.config.path(INSTEON_LOCAL_SWITCH_CONF))
    if device_id not in conf_switch:
        conf_switch[device_id] = name

    if not config_from_file(
            hass.config.path(INSTEON_LOCAL_SWITCH_CONF), conf_switch):
        _LOGGER.error("Failed to save configuration file")

    device = insteonhub.switch(device_id)
    add_devices_callback([InsteonLocalSwitchDevice(device, name)])


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We're writing configuration
        try:
            with open(filename, 'w') as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            _LOGGER.error("Saving configuration file failed: %s", error)
            return False
        return True
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                _LOGGER.error("Reading config file failed: %s", error)
                # This won't work yet
                return False
        else:
            return {}


class InsteonLocalSwitchDevice(SwitchDevice):
    """An abstract Class for an Insteon node."""

    def __init__(self, node, name):
        """Initialize the device."""
        self.node = node
        self.node.deviceName = name
        self._state = False

    @property
    def name(self):
        """Return the the name of the node."""
        return self.node.deviceName

    @property
    def unique_id(self):
        """Return the ID of this Insteon node."""
        return 'insteon_local_{}'.format(self.node.device_id)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Get the updated status of the switch."""
        resp = self.node.status(0)
        if 'cmd2' in resp:
            self._state = int(resp['cmd2'], 16) > 0

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.node.on()
        self._state = True

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.node.off()
        self._state = False

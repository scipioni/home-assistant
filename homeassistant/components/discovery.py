"""
Starts a service to scan in intervals for new devices.

Will emit EVENT_PLATFORM_DISCOVERED whenever a new service has been discovered.

Knows which components handle certain types, will make sure they are
loaded before the EVENT_PLATFORM_DISCOVERED is fired.
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_START
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.discovery import async_load_platform, async_discover
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['netdisco==0.9.0']

DOMAIN = 'discovery'

SCAN_INTERVAL = timedelta(seconds=300)
SERVICE_NETGEAR = 'netgear_router'
SERVICE_WEMO = 'belkin_wemo'
SERVICE_HASS_IOS_APP = 'hass_ios'

SERVICE_HANDLERS = {
    SERVICE_HASS_IOS_APP: ('ios', None),
    SERVICE_NETGEAR: ('device_tracker', None),
    SERVICE_WEMO: ('wemo', None),
    'philips_hue': ('light', 'hue'),
    'google_cast': ('media_player', 'cast'),
    'panasonic_viera': ('media_player', 'panasonic_viera'),
    'plex_mediaserver': ('media_player', 'plex'),
    'roku': ('media_player', 'roku'),
    'sonos': ('media_player', 'sonos'),
    'yamaha': ('media_player', 'yamaha'),
    'logitech_mediaserver': ('media_player', 'squeezebox'),
    'directv': ('media_player', 'directv'),
    'denonavr': ('media_player', 'denonavr'),
    'samsung_tv': ('media_player', 'samsungtv'),
    'yeelight': ('light', 'yeelight'),
    'flux_led': ('light', 'flux_led'),
    'apple_tv': ('media_player', 'apple_tv'),
    'frontier_silicon': ('media_player', 'frontier_silicon'),
    'openhome': ('media_player', 'openhome'),
}

CONF_IGNORE = 'ignore'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_IGNORE, default=[]):
            vol.All(cv.ensure_list, [vol.In(SERVICE_HANDLERS)])
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Start a discovery service."""
    from netdisco.discovery import NetworkDiscovery

    logger = logging.getLogger(__name__)
    netdisco = NetworkDiscovery()

    # Disable zeroconf logging, it spams
    logging.getLogger('zeroconf').setLevel(logging.CRITICAL)

    # Platforms ignore by config
    ignored_platforms = config[DOMAIN][CONF_IGNORE]

    @asyncio.coroutine
    def new_service_found(service, info):
        """Called when a new service is found."""
        if service in ignored_platforms:
            logger.info("Ignoring service: %s %s", service, info)
            return

        logger.info("Found new service: %s %s", service, info)

        comp_plat = SERVICE_HANDLERS.get(service)

        # We do not know how to handle this service.
        if not comp_plat:
            return

        component, platform = comp_plat

        if platform is None:
            yield from async_discover(hass, service, info, component, config)
        else:
            yield from async_load_platform(
                hass, component, platform, info, config)

    def discover():
        """Discover devices."""
        results = []
        try:
            netdisco.scan()

            for disc in netdisco.discover():
                for service in netdisco.get_info(disc):
                    results.append((disc, service))
        finally:
            netdisco.stop()

        return results

    @asyncio.coroutine
    def scan_devices(_):
        """Scan for devices."""
        results = yield from hass.loop.run_in_executor(None, discover)

        for result in results:
            hass.async_add_job(new_service_found(*result))

        async_track_point_in_utc_time(hass, scan_devices,
                                      dt_util.utcnow() + SCAN_INTERVAL)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, scan_devices)

    return True

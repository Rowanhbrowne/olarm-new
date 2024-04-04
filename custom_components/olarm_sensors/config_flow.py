"""Module used for a GUI to configure the device."""
import asyncio
from typing import Any

from .olarm_api import OlarmSetupApi  # type: ignore[import-untyped]
import voluptuous as vol  # type: ignore[import-untyped]

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    AUTHENTICATION_ERROR,
    CONF_ALARM_CODE,
    CONF_DEVICE_FIRMWARE,
    CONF_OLARM_DEVICES,
    DOMAIN,
    LOGGER,
    OLARM_DEVICE_AMOUNT,
    OLARM_DEVICE_NAMES,
    OLARM_DEVICES,
)
from .coordinator import OlarmCoordinator
from .exceptions import APIForbiddenError


class OlarmSensorsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Olarm Sensors."""

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema(),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}

        if user_input is None:
            return await self._show_setup_form()

        # If user_input is not None, the user has submitted the form
        if user_input is not None:
            # Validate the user input
            if not user_input[CONF_API_KEY]:
                errors[CONF_API_KEY] = "API key is required."

            if not user_input[CONF_SCAN_INTERVAL]:
                errors[CONF_SCAN_INTERVAL] = "Scan interval is required."

            elif user_input[CONF_SCAN_INTERVAL] < 8:
                errors[CONF_SCAN_INTERVAL] = "Scan interval must be at least 8 seconds."

            api_key = user_input[CONF_API_KEY]
            scan_interval = user_input[CONF_SCAN_INTERVAL]

            if user_input[CONF_ALARM_CODE] == "1234567890":
                alarm_code = None

            else:
                alarm_code = user_input[CONF_ALARM_CODE]

            if api_key not in ("mock_api_key", ""):
                try:
                    api = OlarmSetupApi(api_key)
                    json = await api.get_olarm_devices()

                except APIForbiddenError:
                    LOGGER.warning(
                        "User entered invalid credentials or API access is not enabled!"
                    )
                    errors[AUTHENTICATION_ERROR] = "Invalid credentials!"
            else:
                json = [
                    {
                        "deviceName": "Device1",
                        "deviceFirmware": "1.0",
                        "deviceId": "123",
                        "deviceAlarmType": "Paradox",
                    },
                    {
                        "deviceName": "Device2",
                        "deviceFirmware": "1.1",
                        "deviceId": "124",
                        "deviceAlarmType": "IDS",
                    },
                ]

            if json is None:
                errors[AUTHENTICATION_ERROR] = "Invalid credentials!"

            # If there are errors, show the setup form with error messages
            if errors:
                return await self._show_setup_form(errors=errors)

            setup_devices = [dev["deviceName"] for dev in json]

            # If there are no errors, create a config entry and return
            firmware = json[0]["deviceFirmware"]
            temp_entry = ConfigEntry(
                domain=DOMAIN,
                source="User",
                version=1,
                minor_version=0,
                title="Olarm Sensors",
                data={
                    CONF_API_KEY: api_key,
                    CONF_SCAN_INTERVAL: scan_interval,
                    CONF_DEVICE_FIRMWARE: firmware,
                    CONF_ALARM_CODE: alarm_code,
                    CONF_OLARM_DEVICES: setup_devices,
                    OLARM_DEVICE_AMOUNT: len(json),
                    OLARM_DEVICE_NAMES: setup_devices,
                },
            )

            for device in json:
                if device["deviceName"] not in setup_devices:
                    continue

                await asyncio.sleep(2)
                coordinator = OlarmCoordinator(
                    self.hass,
                    entry=temp_entry,
                    device_id=device["deviceId"],
                    device_name=device["deviceName"],
                    device_make=device["deviceAlarmType"],
                )

                await coordinator.update_data()

                self.hass.data[DOMAIN][device["deviceId"]] = coordinator

            # Saving the device
            return self.async_create_entry(
                title="Olarm Sensors",
                data={
                    CONF_API_KEY: api_key,
                    CONF_SCAN_INTERVAL: scan_interval,
                    CONF_DEVICE_FIRMWARE: firmware,
                    CONF_ALARM_CODE: alarm_code,
                    CONF_OLARM_DEVICES: setup_devices,
                    OLARM_DEVICES: json,
                    OLARM_DEVICE_AMOUNT: len(json),
                    OLARM_DEVICE_NAMES: setup_devices,
                },
            )

        return self.async_show_form(step_id="user", data_schema=self._get_schema())

    def _get_schema(self):
        """Return the data schema for the user form."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_API_KEY,
                ): cv.string,
                vol.Required(
                    CONF_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=8)),
                vol.Optional(
                    CONF_ALARM_CODE,
                    default="1234567890"
                ): cv.string,
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OlarmOptionsFlow(config_entry)


class OlarmOptionsFlow(OptionsFlow):
    """Options for Olarm config."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    def _get_schema(self):
        """Return the data schema for the user form."""
        if self.config_entry.data[CONF_ALARM_CODE] is None:
            alarm_code = "1234567890"

        else:
            alarm_code = self.config_entry.data[CONF_ALARM_CODE]

        return vol.Schema(
            {
                vol.Required(
                    CONF_API_KEY,
                    default=self.config_entry.data[CONF_API_KEY]
                ): cv.string,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=int(self.config_entry.data[CONF_SCAN_INTERVAL])
                ): vol.All(vol.Coerce(int), vol.Range(min=8)),
                vol.Optional(
                    CONF_ALARM_CODE,
                    default=alarm_code
                ): cv.string,
                vol.Optional(
                    CONF_OLARM_DEVICES,
                ): cv.multi_select(self.config_entry.data[OLARM_DEVICE_NAMES]),
            }
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input[CONF_ALARM_CODE] == "1234567890":
                alarm_code = None

            else:
                alarm_code = user_input[CONF_ALARM_CODE]

            new = {**self.config_entry.data}

            new[CONF_ALARM_CODE] = alarm_code
            new[OLARM_DEVICE_AMOUNT] = len(self.config_entry.data[OLARM_DEVICE_NAMES])
            new[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]
            new[CONF_API_KEY] = user_input[CONF_API_KEY]
            new[CONF_OLARM_DEVICES] = user_input[CONF_OLARM_DEVICES]

            return self.async_create_entry(title="Olarm Sensors", data=new)

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_schema(),
        )
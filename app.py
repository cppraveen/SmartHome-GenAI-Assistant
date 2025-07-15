import logging
from functools import wraps
from authlib.jose import jwt, JoseError
import bleach
import paho.mqtt.client as mqtt
import os

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# --- OAuth 2.0 Token Validation Setup ---
OAUTH_PUBLIC_KEY = os.environ.get('OAUTH_PUBLIC_KEY', 'your-public-key-here')  # Replace with real key or JWKS fetch
OAUTH_ISSUER = os.environ.get('OAUTH_ISSUER', 'https://example.com/')
OAUTH_AUDIENCE = os.environ.get('OAUTH_AUDIENCE', 'smarthome-api')

def require_oauth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', None)
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning('Missing or invalid Authorization header')
            abort(401, description='Missing or invalid Authorization header')
        token = auth_header.split(' ')[1]
        try:
            claims = jwt.decode(token, OAUTH_PUBLIC_KEY)
            claims.validate()
            if claims.get('iss') != OAUTH_ISSUER or claims.get('aud') != OAUTH_AUDIENCE:
                logger.warning('Invalid token issuer or audience')
                abort(401, description='Invalid token issuer or audience')
        except JoseError as e:
            logger.warning(f'JWT validation error: {e}')
            abort(401, description='Invalid token')
        return f(*args, **kwargs)
    return decorated

# --- MQTT Setup ---
MQTT_BROKER = os.environ.get('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.environ.get('MQTT_PORT', 1883))
mqtt_client = mqtt.Client()
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    logger.warning(f'Could not connect to MQTT broker: {e}')

# --- Input Sanitization Helper ---
def sanitize_input(data):
    if isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(i) for i in data]
    elif isinstance(data, str):
        return bleach.clean(data)
    else:
        return data

from flask import Flask, request, jsonify, abort

app = Flask(__name__)

# In-memory device registry (mock database)
device_registry = {
    "coffee_maker_123": {
        "id": "coffee_maker_123",
        "friendlyName": "My Smart Coffee Maker",
        "type": "COFFEE_MAKER",
        "state": {
            "powerState": "OFF",
            "brewStrength": "medium",
            "waterLevel": 100,
            "errorState": "none"
        }
    },
    "light_456": {
        "id": "light_456",
        "friendlyName": "Living Room Light",
        "type": "LIGHT",
        "state": {
            "powerState": "OFF",
            "brightness": 50,
            "color": {"hue": 0, "saturation": 0, "brightness": 100}
        }
    },
    "thermostat_789": {
        "id": "thermostat_789",
        "friendlyName": "Hallway Thermostat",
        "type": "THERMOSTAT",
        "state": {
            "targetSetpoint": 22.0,
            "temperature": 21.5,
            "thermostatMode": "HEAT"
        }
    },
    "sensor_321": {
        "id": "sensor_321",
        "friendlyName": "Front Door Sensor",
        "type": "CONTACT_SENSOR",
        "state": {
            "detectionState": "NOT_DETECTED",
            "temperature": 19.0
        }
    }
}

# --- Smart Assistant Platform facing API Endpoints ---

@app.route('/smart-home/discovery', methods=['POST'])
@require_oauth
def discover_devices():
    logger.info("Discovery request received.")
    endpoints = []
    for device_id, device_info in device_registry.items():
        capabilities = []
        if device_info["type"] == "COFFEE_MAKER":
            capabilities = [
                {"type": "AlexaInterface", "interface": "Alexa.PowerController", "version": "3",
                 "properties": {"supported": [{"name": "powerState"}], "retrievable": True, "proactivelyReported": False}},
                {"type": "AlexaInterface", "interface": "Alexa.ModeController", "version": "1.0",
                 "instance": "BrewStrength.coffee_maker_123", "capabilityResources": {"friendlyNames": [{"value": {"text": "brew strength", "locale": "en-US"}}]},
                 "properties": {"supported": [{"name": "mode"}], "retrievable": True, "proactivelyReported": False},
                 "configuration": {"ordered": False, "supportedModes": [
                     {"value": "light", "modeResources": {"friendlyNames": [{"value": {"text": "light", "locale": "en-US"}}]}},
                     {"value": "medium", "modeResources": {"friendlyNames": [{"value": {"text": "medium", "locale": "en-US"}}]}},
                     {"value": "strong", "modeResources": {"friendlyNames": [{"value": {"text": "strong", "locale": "en-US"}}]}}
                 ]}},
                {"type": "AlexaInterface", "interface": "Alexa.RangeController", "version": "3",
                 "instance": "WaterLevel.coffee_maker_123",
                 "capabilityResources": {"friendlyNames": [{"value": {"text": "water level", "locale": "en-US"}}]},
                 "properties": {"supported": [{"name": "rangeValue"}], "retrievable": True, "proactivelyReported": False},
                 "configuration": {"supportedRange": {"minimumValue": 0, "maximumValue": 100, "precision": 1},
                                    "unitOfMeasure": "Percent"}},
                {"type": "AlexaInterface", "interface": "Alexa.EndpointHealth", "version": "3",
                 "properties": {"supported": [{"name": "connectivity"}], "retrievable": True, "proactivelyReported": False}},
                {"type": "AlexaInterface", "interface": "Alexa.ModeController", "version": "1.0",
                 "instance": "ErrorState.coffee_maker_123", "capabilityResources": {"friendlyNames": [{"value": {"text": "error state", "locale": "en-US"}}]},
                 "properties": {"supported": [{"name": "mode"}], "retrievable": True, "proactivelyReported": False},
                 "configuration": {"ordered": False, "supportedModes": [
                     {"value": "none", "modeResources": {"friendlyNames": [{"value": {"text": "none", "locale": "en-US"}}]}},
                     {"value": "lowWater", "modeResources": {"friendlyNames": [{"value": {"text": "low water", "locale": "en-US"}}]}},
                     {"value": "jammed", "modeResources": {"friendlyNames": [{"value": {"text": "jammed", "locale": "en-US"}}]}}
                 ]}}
            ]
        elif device_info["type"] == "LIGHT":
            capabilities = [
                {"type": "AlexaInterface", "interface": "Alexa.PowerController", "version": "3",
                 "properties": {"supported": [{"name": "powerState"}], "retrievable": True, "proactivelyReported": False}},
                {"type": "AlexaInterface", "interface": "Alexa.BrightnessController", "version": "3",
                 "properties": {"supported": [{"name": "brightness"}], "retrievable": True, "proactivelyReported": False}},
                {"type": "AlexaInterface", "interface": "Alexa.ColorController", "version": "3",
                 "properties": {"supported": [{"name": "color"}], "retrievable": True, "proactivelyReported": False}},
                {"type": "AlexaInterface", "interface": "Alexa.EndpointHealth", "version": "3",
                 "properties": {"supported": [{"name": "connectivity"}], "retrievable": True, "proactivelyReported": False}}
            ]
        elif device_info["type"] == "THERMOSTAT":
            capabilities = [
                {"type": "AlexaInterface", "interface": "Alexa.ThermostatController", "version": "3",
                 "properties": {"supported": [
                     {"name": "targetSetpoint"},
                     {"name": "thermostatMode"}
                 ], "retrievable": True, "proactivelyReported": False}},
                {"type": "AlexaInterface", "interface": "Alexa.TemperatureSensor", "version": "3",
                 "properties": {"supported": [{"name": "temperature"}], "retrievable": True, "proactivelyReported": False}},
                {"type": "AlexaInterface", "interface": "Alexa.EndpointHealth", "version": "3",
                 "properties": {"supported": [{"name": "connectivity"}], "retrievable": True, "proactivelyReported": False}}
            ]
        elif device_info["type"] == "CONTACT_SENSOR":
            capabilities = [
                {"type": "AlexaInterface", "interface": "Alexa.ContactSensor", "version": "3",
                 "properties": {"supported": [{"name": "detectionState"}], "retrievable": True, "proactivelyReported": False}},
                {"type": "AlexaInterface", "interface": "Alexa.TemperatureSensor", "version": "3",
                 "properties": {"supported": [{"name": "temperature"}], "retrievable": True, "proactivelyReported": False}},
                {"type": "AlexaInterface", "interface": "Alexa.EndpointHealth", "version": "3",
                 "properties": {"supported": [{"name": "connectivity"}], "retrievable": True, "proactivelyReported": False}}
            ]
        endpoints.append({
            "endpointId": device_info["id"],
            "friendlyName": device_info["friendlyName"],
            "description": f"My smart {device_info['type']}",
            "manufacturerName": "My Awesome IoT Company",
            "displayCategories": [device_info["type"]],
            "capabilities": capabilities
        })
    return jsonify({"event": {"header": {"namespace": "Alexa.Discovery", "name": "Discover.Response", "payloadVersion": "3"},
                              "payload": {"endpoints": endpoints}}})

@app.route('/smart-home/control', methods=['POST'])
@require_oauth
def control_device():
    request_data = sanitize_input(request.json)
    directive = request_data.get('directive', {}) if isinstance(request_data, dict) else {}
    header = directive.get('header', {}) if isinstance(directive, dict) else {}
    endpoint = directive.get('endpoint', {}) if isinstance(directive, dict) else {}
    payload = directive.get('payload', {}) if isinstance(directive, dict) else {}

    name = header.get('name')
    namespace = header.get('namespace')
    endpoint_id = endpoint.get('endpointId')
    correlation_token = header.get('correlationToken')

    logger.info(f"Control request: {namespace}.{name} for {endpoint_id}")

    if endpoint_id not in device_registry:
        logger.error(f"Device not found: {endpoint_id}")
        abort(404, description="Device not found.")

    device_info = device_registry[endpoint_id]
    device_state = device_info["state"]
    device_type = device_info["type"]
    new_state_value = None
    success_message = "Command executed."

    # --- COFFEE MAKER logic (existing) ---
    if device_type == "COFFEE_MAKER":
        if namespace == "Alexa.PowerController":
            if name == "TurnOn":
                device_state["powerState"] = "ON"
                new_state_value = {"name": "powerState", "value": "ON"}
                success_message = f"{device_registry[endpoint_id]['friendlyName']} turned on."
                logger.info(f"Actuating physical device {endpoint_id}: TURN ON")
                try:
                    mqtt_client.publish(f"devices/{endpoint_id}/power", "ON")
                except Exception as e:
                    logger.warning(f"MQTT publish failed: {e}")
            elif name == "TurnOff":
                device_state["powerState"] = "OFF"
                new_state_value = {"name": "powerState", "value": "OFF"}
                success_message = f"{device_registry[endpoint_id]['friendlyName']} turned off."
                logger.info(f"Actuating physical device {endpoint_id}: TURN OFF")
                try:
                    mqtt_client.publish(f"devices/{endpoint_id}/power", "OFF")
                except Exception as e:
                    logger.warning(f"MQTT publish failed: {e}")
            else:
                abort(400, description="Unsupported PowerController command.")
        elif namespace == "Alexa.ModeController":
            if name == "SetMode":
                if header.get('instance') == "BrewStrength.coffee_maker_123":
                    new_mode = payload.get('mode')
                    if new_mode and new_mode.get('value') in ["light", "medium", "strong"]:
                        device_state["brewStrength"] = new_mode['value']
                        new_state_value = {"name": "mode", "value": new_mode['value'], "instance": header['instance']}
                        success_message = f"Set brew strength to {new_mode['value']}."
                        logger.info(f"Actuating physical device {endpoint_id}: SET BREW STRENGTH to {new_mode['value']}")
                        try:
                            mqtt_client.publish(f"devices/{endpoint_id}/brewStrength", new_mode['value'])
                        except Exception as e:
                            logger.warning(f"MQTT publish failed: {e}")
                    else:
                        abort(400, description="Invalid brew strength.")
                elif header.get('instance') == "ErrorState.coffee_maker_123":
                    new_error = payload.get('mode', {}).get('value')
                    if new_error in ["none", "lowWater", "jammed"]:
                        device_state["errorState"] = new_error
                        new_state_value = {"name": "mode", "value": new_error, "instance": header['instance']}
                        logger.info(f"Set error state to {new_error}")
                    else:
                        abort(400, description="Invalid error state value.")
                else:
                    abort(400, description="Unsupported mode instance.")
            else:
                abort(400, description="Unsupported ModeController command.")
        elif namespace == "Alexa.RangeController":
            if name == "SetRangeValue":
                if header.get('instance') == "WaterLevel.coffee_maker_123":
                    new_level = payload.get('rangeValue')
                    if isinstance(new_level, (int, float)) and 0 <= new_level <= 100:
                        device_state["waterLevel"] = new_level
                        new_state_value = {"name": "rangeValue", "value": new_level, "instance": header['instance']}
                        success_message = f"Set water level to {new_level}%."
                        logger.info(f"Actuating physical device {endpoint_id}: SET WATER LEVEL to {new_level}")
                        try:
                            mqtt_client.publish(f"devices/{endpoint_id}/waterLevel", str(new_level))
                        except Exception as e:
                            logger.warning(f"MQTT publish failed: {e}")
                    else:
                        logger.error("Invalid water level value.")
                        abort(400, description="Invalid water level value.")
                else:
                    logger.error("Unsupported range instance.")
                    abort(400, description="Unsupported range instance.")
            else:
                abort(400, description="Unsupported RangeController command.")
        elif namespace == "Alexa.EndpointHealth":
            if name == "ReportState":
                properties = []
                if "powerState" in device_state:
                    properties.append({"namespace": "Alexa.PowerController", "name": "powerState",
                                       "value": device_state["powerState"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "brewStrength" in device_state:
                    properties.append({"namespace": "Alexa.ModeController", "name": "mode", "instance": "BrewStrength.coffee_maker_123",
                                       "value": device_state["brewStrength"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "waterLevel" in device_state:
                    properties.append({"namespace": "Alexa.RangeController", "name": "rangeValue", "instance": "WaterLevel.coffee_maker_123",
                                       "value": device_state["waterLevel"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                properties.append({"namespace": "Alexa.EndpointHealth", "name": "connectivity", "value": {"value": "OK"}, "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "errorState" in device_state:
                    properties.append({"namespace": "Alexa.ModeController", "name": "mode", "instance": "ErrorState.coffee_maker_123",
                                       "value": device_state["errorState"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                return jsonify({
                    "event": {
                        "header": {
                            "namespace": "Alexa",
                            "name": "StateReport",
                            "payloadVersion": "3",
                            "messageId": "unique-message-id",
                            "correlationToken": correlation_token
                        },
                        "endpoint": {"endpointId": endpoint_id},
                        "payload": {"properties": properties}
                    }
                }), 200
            else:
                abort(400, description="Unsupported EndpointHealth command.")
        else:
            abort(400, description="Unsupported coffee maker namespace.")

    # --- SMART LIGHT logic ---
    elif device_type == "LIGHT":
        if namespace == "Alexa.PowerController":
            if name == "TurnOn":
                device_state["powerState"] = "ON"
                new_state_value = {"name": "powerState", "value": "ON"}
                success_message = f"{device_registry[endpoint_id]['friendlyName']} turned on."
                logger.info(f"Actuating physical device {endpoint_id}: TURN ON")
                try:
                    mqtt_client.publish(f"devices/{endpoint_id}/power", "ON")
                except Exception as e:
                    logger.warning(f"MQTT publish failed: {e}")
            elif name == "TurnOff":
                device_state["powerState"] = "OFF"
                new_state_value = {"name": "powerState", "value": "OFF"}
                success_message = f"{device_registry[endpoint_id]['friendlyName']} turned off."
                logger.info(f"Actuating physical device {endpoint_id}: TURN OFF")
                try:
                    mqtt_client.publish(f"devices/{endpoint_id}/power", "OFF")
                except Exception as e:
                    logger.warning(f"MQTT publish failed: {e}")
            else:
                abort(400, description="Unsupported PowerController command.")
        elif namespace == "Alexa.BrightnessController":
            if name == "SetBrightness":
                brightness = payload.get("brightness")
                if isinstance(brightness, int) and 0 <= brightness <= 100:
                    device_state["brightness"] = brightness
                    new_state_value = {"name": "brightness", "value": brightness}
                    success_message = f"Light {device_registry[endpoint_id]['friendlyName']} brightness set to {brightness}."
                    logger.info(f"Actuating physical device {endpoint_id}: SET BRIGHTNESS to {brightness}")
                    try:
                        mqtt_client.publish(f"devices/{endpoint_id}/brightness", str(brightness))
                    except Exception as e:
                        logger.warning(f"MQTT publish failed: {e}")
                else:
                    abort(400, description="Invalid brightness value.")
            else:
                abort(400, description="Unsupported BrightnessController command.")
        elif namespace == "Alexa.ColorController":
            if name == "SetColor":
                color = payload.get("color")
                if color and all(k in color for k in ("hue", "saturation", "brightness")):
                    device_state["color"] = color
                    new_state_value = {"name": "color", "value": color}
                    success_message = f"Light {device_registry[endpoint_id]['friendlyName']} color set to {color}."
                    logger.info(f"Actuating physical device {endpoint_id}: SET COLOR to {color}")
                    try:
                        mqtt_client.publish(f"devices/{endpoint_id}/color", str(color))
                    except Exception as e:
                        logger.warning(f"MQTT publish failed: {e}")
                else:
                    abort(400, description="Invalid color value.")
            else:
                abort(400, description="Unsupported ColorController command.")
        elif namespace == "Alexa.EndpointHealth":
            if name == "ReportState":
                properties = []
                if "powerState" in device_state:
                    properties.append({"namespace": "Alexa.PowerController", "name": "powerState",
                                       "value": device_state["powerState"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "brightness" in device_state:
                    properties.append({"namespace": "Alexa.BrightnessController", "name": "brightness",
                                       "value": device_state["brightness"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "color" in device_state:
                    properties.append({"namespace": "Alexa.ColorController", "name": "color",
                                       "value": device_state["color"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                properties.append({"namespace": "Alexa.EndpointHealth", "name": "connectivity", "value": {"value": "OK"}, "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                return jsonify({
                    "event": {
                        "header": {
                            "namespace": "Alexa",
                            "name": "StateReport",
                            "payloadVersion": "3",
                            "messageId": "unique-message-id",
                            "correlationToken": correlation_token
                        },
                        "endpoint": {"endpointId": endpoint_id},
                        "payload": {"properties": properties}
                    }
                }), 200
            else:
                abort(400, description="Unsupported EndpointHealth command.")
        else:
            abort(400, description="Unsupported light namespace.")

    # --- THERMOSTAT logic ---
    elif device_type == "THERMOSTAT":
        if namespace == "Alexa.ThermostatController":
            if name == "SetTargetTemperature":
                target = payload.get("targetSetpoint", {}).get("value")
                if isinstance(target, (int, float)):
                    device_state["targetSetpoint"] = target
                    new_state_value = {"name": "targetSetpoint", "value": target}
                    success_message = f"Thermostat {device_registry[endpoint_id]['friendlyName']} setpoint set to {target}."
                    logger.info(f"Actuating physical device {endpoint_id}: SET TARGET SETPOINT to {target}")
                    try:
                        mqtt_client.publish(f"devices/{endpoint_id}/targetSetpoint", str(target))
                    except Exception as e:
                        logger.warning(f"MQTT publish failed: {e}")
                else:
                    abort(400, description="Invalid target setpoint value.")
            elif name == "SetThermostatMode":
                mode = payload.get("thermostatMode")
                if mode in ["HEAT", "COOL", "AUTO", "OFF"]:
                    device_state["thermostatMode"] = mode
                    new_state_value = {"name": "thermostatMode", "value": mode}
                    success_message = f"Thermostat {device_registry[endpoint_id]['friendlyName']} mode set to {mode}."
                    logger.info(f"Actuating physical device {endpoint_id}: SET THERMOSTAT MODE to {mode}")
                    try:
                        mqtt_client.publish(f"devices/{endpoint_id}/thermostatMode", mode)
                    except Exception as e:
                        logger.warning(f"MQTT publish failed: {e}")
                else:
                    abort(400, description="Invalid thermostat mode.")
            else:
                abort(400, description="Unsupported ThermostatController command.")
        elif namespace == "Alexa.TemperatureSensor":
            if name == "ReportState":
                properties = []
                if "targetSetpoint" in device_state:
                    properties.append({"namespace": "Alexa.ThermostatController", "name": "targetSetpoint",
                                       "value": device_state["targetSetpoint"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "thermostatMode" in device_state:
                    properties.append({"namespace": "Alexa.ThermostatController", "name": "thermostatMode",
                                       "value": device_state["thermostatMode"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "temperature" in device_state:
                    properties.append({"namespace": "Alexa.TemperatureSensor", "name": "temperature",
                                       "value": device_state["temperature"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                properties.append({"namespace": "Alexa.EndpointHealth", "name": "connectivity", "value": {"value": "OK"}, "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                return jsonify({
                    "event": {
                        "header": {
                            "namespace": "Alexa",
                            "name": "StateReport",
                            "payloadVersion": "3",
                            "messageId": "unique-message-id",
                            "correlationToken": correlation_token
                        },
                        "endpoint": {"endpointId": endpoint_id},
                        "payload": {"properties": properties}
                    }
                }), 200
            else:
                abort(400, description="Unsupported TemperatureSensor command.")
        elif namespace == "Alexa.EndpointHealth":
            if name == "ReportState":
                properties = []
                if "targetSetpoint" in device_state:
                    properties.append({"namespace": "Alexa.ThermostatController", "name": "targetSetpoint",
                                       "value": device_state["targetSetpoint"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "thermostatMode" in device_state:
                    properties.append({"namespace": "Alexa.ThermostatController", "name": "thermostatMode",
                                       "value": device_state["thermostatMode"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "temperature" in device_state:
                    properties.append({"namespace": "Alexa.TemperatureSensor", "name": "temperature",
                                       "value": device_state["temperature"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                properties.append({"namespace": "Alexa.EndpointHealth", "name": "connectivity", "value": {"value": "OK"}, "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                return jsonify({
                    "event": {
                        "header": {
                            "namespace": "Alexa",
                            "name": "StateReport",
                            "payloadVersion": "3",
                            "messageId": "unique-message-id",
                            "correlationToken": correlation_token
                        },
                        "endpoint": {"endpointId": endpoint_id},
                        "payload": {"properties": properties}
                    }
                }), 200
            else:
                abort(400, description="Unsupported EndpointHealth command.")
        else:
            abort(400, description="Unsupported thermostat namespace.")

    # --- CONTACT SENSOR logic (read-only, no control) ---
    elif device_type == "CONTACT_SENSOR":
        if namespace == "Alexa.ContactSensor":
            if name == "ReportState":
                properties = []
                if "detectionState" in device_state:
                    properties.append({"namespace": "Alexa.ContactSensor", "name": "detectionState",
                                       "value": device_state["detectionState"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "temperature" in device_state:
                    properties.append({"namespace": "Alexa.TemperatureSensor", "name": "temperature",
                                       "value": device_state["temperature"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                properties.append({"namespace": "Alexa.EndpointHealth", "name": "connectivity", "value": {"value": "OK"}, "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                return jsonify({
                    "event": {
                        "header": {
                            "namespace": "Alexa",
                            "name": "StateReport",
                            "payloadVersion": "3",
                            "messageId": "unique-message-id",
                            "correlationToken": correlation_token
                        },
                        "endpoint": {"endpointId": endpoint_id},
                        "payload": {"properties": properties}
                    }
                }), 200
            else:
                abort(400, description="Unsupported ContactSensor command.")
        elif namespace == "Alexa.EndpointHealth":
            if name == "ReportState":
                properties = []
                if "detectionState" in device_state:
                    properties.append({"namespace": "Alexa.ContactSensor", "name": "detectionState",
                                       "value": device_state["detectionState"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                if "temperature" in device_state:
                    properties.append({"namespace": "Alexa.TemperatureSensor", "name": "temperature",
                                       "value": device_state["temperature"], "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                properties.append({"namespace": "Alexa.EndpointHealth", "name": "connectivity", "value": {"value": "OK"}, "timeOfSample": "2025-07-10T12:00:00.000Z", "uncertaintyInMilliseconds": 50})
                return jsonify({
                    "event": {
                        "header": {
                            "namespace": "Alexa",
                            "name": "StateReport",
                            "payloadVersion": "3",
                            "messageId": "unique-message-id",
                            "correlationToken": correlation_token
                        },
                        "endpoint": {"endpointId": endpoint_id},
                        "payload": {"properties": properties}
                    }
                }), 200
            else:
                abort(400, description="Unsupported EndpointHealth command.")
        else:
            abort(400, description="Unsupported contact sensor namespace.")

    # --- Fallback to existing coffee maker and generic logic for other commands ---
    else:
        logger.error("Unsupported command or namespace.")
        abort(400, description="Unsupported command or namespace.")

    response_payload = {
        "event": {
            "header": {
                "namespace": namespace,
                "name": f"{name}Response",
                "payloadVersion": "3",
                "messageId": "some-unique-response-id",
                "correlationToken": correlation_token
            },
            "endpoint": {"endpointId": endpoint_id},
            "payload": {}
        },
        "context": {
            "properties": []
        }
    }

    if new_state_value:
        response_payload['context']['properties'].append({
            "namespace": namespace,
            "name": new_state_value['name'],
            "value": new_state_value['value'],
            "timeOfSample": "2025-07-10T12:00:00.000Z",
            "uncertaintyInMilliseconds": 0
        })
        if "instance" in new_state_value:
             response_payload['context']['properties'][-1]["instance"] = new_state_value["instance"]

    return jsonify(response_payload), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000) 
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
            "waterLevel": "full"  # Example of a retrievable property
        }
    }
}

# --- Smart Assistant Platform facing API Endpoints ---

@app.route('/smart-home/discovery', methods=['POST'])
def discover_devices():
    print("Discovery request received.")
    endpoints = []
    for device_id, device_info in device_registry.items():
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
             ]}}
            # For brevity, other capabilities like water level sensor are omitted
        ]
        endpoints.append({
            "endpointId": device_info["id"],
            "friendlyName": device_info["friendlyName"],
            "description": f"My smart {device_info['type']}",
            "manufacturerName": "My Awesome IoT Company",
            "displayCategories": ["COFFEE_MAKER"],
            "capabilities": capabilities
        })
    return jsonify({"event": {"header": {"namespace": "Alexa.Discovery", "name": "Discover.Response", "payloadVersion": "3"},
                              "payload": {"endpoints": endpoints}}})

@app.route('/smart-home/control', methods=['POST'])
def control_device():
    request_data = request.json
    directive = request_data.get('directive', {}) if request_data else {}
    header = directive.get('header', {}) if directive else {}
    endpoint = directive.get('endpoint', {}) if directive else {}
    payload = directive.get('payload', {}) if directive else {}

    name = header.get('name')
    namespace = header.get('namespace')
    endpoint_id = endpoint.get('endpointId')
    correlation_token = header.get('correlationToken')

    print(f"Control request: {namespace}.{name} for {endpoint_id}")

    if endpoint_id not in device_registry:
        abort(404, description="Device not found.")

    device_state = device_registry[endpoint_id]["state"]
    new_state_value = None
    success_message = "Command executed."

    if namespace == "Alexa.PowerController" and name == "TurnOn":
        device_state["powerState"] = "ON"
        new_state_value = {"name": "powerState", "value": "ON"}
        success_message = f"{device_registry[endpoint_id]['friendlyName']} turned on."
        print(f"Actuating physical device {endpoint_id}: TURN ON")

    elif namespace == "Alexa.PowerController" and name == "TurnOff":
        device_state["powerState"] = "OFF"
        new_state_value = {"name": "powerState", "value": "OFF"}
        success_message = f"{device_registry[endpoint_id]['friendlyName']} turned off."
        print(f"Actuating physical device {endpoint_id}: TURN OFF")

    elif namespace == "Alexa.ModeController" and name == "SetMode":
        if header.get('instance') == "BrewStrength.coffee_maker_123":
            new_mode = payload.get('mode')
            if new_mode and new_mode.get('value') in ["light", "medium", "strong"]:
                device_state["brewStrength"] = new_mode['value']
                new_state_value = {"name": "mode", "value": new_mode['value'], "instance": header['instance']}
                success_message = f"Set brew strength to {new_mode['value']}."
                print(f"Actuating physical device {endpoint_id}: SET BREW STRENGTH to {new_mode['value']}")
            else:
                abort(400, description="Invalid brew strength.")
        else:
            abort(400, description="Unsupported mode instance.")

    elif namespace == "Alexa.StateReport" and name == "ReportState":
        print(f"State report requested for {endpoint_id}")
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
# SmartHome-GenAI-Assistant

This is a conceptual server-side package for integrating a smart home device (e.g., a Smart Coffee Maker) with a smart assistant platform (like Amazon Alexa).

## Features
- Device discovery endpoint for smart assistant integration
- Device control endpoint supporting power and mode (brew strength)
- State reporting endpoint for querying device status
- In-memory device registry (for demo purposes)
- Flask-based API

## Endpoints
- `POST /smart-home/discovery` — Device discovery for account linking
- `POST /smart-home/control` — Device control and state reporting

## Running the Server

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the server:
   ```bash
   python app.py
   ```

The server will run on `http://localhost:5000` by default.

## Notes
- This is a demo. In production, use persistent storage, robust authentication, and real IoT integration.
- For Alexa/Google integration, follow their respective developer documentation for account linking and endpoint requirements. 
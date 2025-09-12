# Open-Source Travel Assistant Application

## Overview
A web-based "voice & chat" travel planning assistant using Rasa for dialogue, Llama LLM (via LangGraph) for fallback/tool-calling, LiveKit for voice (prep), Piper TTS/Whisper STT, and free APIs. Global coverage for weather, flights, attractions, currency, time. Auto-trains Rasa from query logs every 6 hours. Access via link for voice/text chat.

## Usage
This repository is **public** for anyone to read, search, and use to build their own version of the `livekit-travel-voice-assistant` app. You can clone, fork, or download the code to explore or adapt it. However, **modification access** is restricted to collaborators explicitly invited by the owner (Siddhant Kumar). To contribute changes, fork the repo, make a pull request, or contact me for write access.

For collaboration, contract work, or to support this project:
- **Email**: stjl093@gmail.com
- **Phone**: +918095875948
- **LinkedIn**: [linkedin.com/in/sid-093](https://linkedin.com/in/sid-093)
- **Donate**: [PayPal Donation Link](https://www.paypal.com/ncp/payment/2J5NTJBYW2HL8)
**"Fuel my passion for building innovative open-source tools like this – your donation keeps the journey going!"**

## Features
- **Conversational**: Friendly, proactive (offers related info), context retention (slots/memory).
- **Guidelines Compliance**: Packing advice, flight duration, currency context, location confirmation.
- **Data Sources**: OpenWeatherMap (weather), Amadeus test (flights), Geoapify (attractions), TimeZoneDB (time), exchangeratesapi.io (currency via DB/scheduler).
- **Logging**: Shared query_history.db for all queries (Rasa/LLM/currency updates), with query_count.
- **Auto-Training**: rasa_train.py appends new NLU examples from DB, trains/restarts Rasa every 6 hours.
- **Services**: Systemd for hybrid LLM (5000), Rasa (5005), actions (5055), currency updater, auto-trainer.
- **Testing**: Curl for Rasa/LLM; TTS tested (en_US-lessac-medium).

## Setup Instructions
1. Clone: `git clone https://github.com/S-V-J/livekit-travel-voice-assistant.git`.
2. Activate venvs: `source llm_venv/bin/activate` (LLM) or `source rasa-bot/rasa_venv/bin/activate` (Rasa).
3. Install deps: `pip install -r requirements.txt` (in llm_venv); for Rasa, already set.
4. Piper TTS: Model at `~/.local/share/piper/voices/en_US-lessac-medium/`; set `$PIPER_DATA_DIR`.
5. Databases: Run `python3 db/init_db.py` to create query_history.db/exchange_rates.db in `db/`.
6. Services: Copy systemd files from `systemd/` to `/etc/systemd/system/`; run `sudo systemctl daemon-reload; sudo systemctl enable rasa.service rasa_actions.service rasa_train.service currency_converter.service hybrid_rasa_llm.service; sudo systemctl start rasa.service rasa_actions.service rasa_train.service currency_converter.service hybrid_rasa_llm.service`.
7. Train Rasa: `rasa train` (manual) or via rasa_train.service (auto).
8. Test Rasa: `curl -X POST http://localhost:5005/webhooks/rest/webhook -d '{"sender": "test", "message": "Book a flight to Paris"}'`.
9. Test LLM: `curl -X POST http://localhost:5000/llm -d '{"input": "What is the weather in Mumbai?"}'`.
10. Frontend/Voice: Add web-frontend/index.html with LiveKit; integrate voice_bot.py.
11. Deploy: Docker/K8s (add manifests); ngrok for public link.

## Architecture
- **Hybrid Backend**: hybrid_rasa_llm.py (Flask + LangGraph + Llama 1B/3B + tools/APIs).
- **Rasa**: rasa-bot/ (NLU in nlu.yml, domain/slots/responses in domain.yml, flows in stories/rules.yml, custom actions in actions.py logging to DB).
- **Currency**: currency_converter.py (fetches/stores rates, logs updates to DB, scheduler).
- **Auto-Train**: rasa_train.py (APScheduler extracts DB queries, appends to nlu.yml, trains/restarts Rasa).
- **DB**: Shared query_history.db (queries from Rasa/LLM/currency) + exchange_rates.db (init via db/init_db.py).
- **Services**: currency_converter, hybrid_rasa_llm, rasa, rasa_actions, rasa_train (systemd).
- **Voice Prep**: LiveKit + Whisper STT + Piper TTS (tested WAV generation/playback).

## Testing
- Rasa Curl: Greet, flights (asks/confirm/provides), weather, etc.
- LLM Curl: Tools work (weather, flights, currency, time, update, joke).
- DB Logs: Queries/responses stored (e.g., SELECT from query_history.db shows entries with query_count).
- Audio: TTS tested (echo | piper → WAV → aplay).

## Known Issues/Fixes
- SQLAlchemy warning: Suppressed via env in rasa.service.
- Piper Path: Fixed with directory structure.
- Flight Entities: Improved NLU/rules for partial info.
- Training Conflicts: Resolved by refining rules.yml.
- DB Column: query_count added/handled.

License: MIT

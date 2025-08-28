# Open-Source Travel Voice Assistant

## Overview
This is an open-source conversational travel planning assistant using Rasa for dialogue management, Llama LLM for fallback, LiveKit for voice, and free APIs for real-time data (weather, flights, attractions, currency, time). It's web-based: users click a link to start voice/text chat. Supports global locations (cities, villages).

### Features
- Conversational: Friendly, proactive (e.g., offers flights after weather).
- Context Retention: Remembers locations across turns.
- Guidelines: Packing advice, flight duration, currency context, location confirmation.
- Auto-Training: Retrains Rasa every 6 hours from query logs.
- Voice/Chat: Browser-based with Piper TTS/Whisper STT.
- Services: Systemd for rasa, actions, hybrid LLM, currency updater, auto-trainer.
- Shared Database: Rasa, LLM, and currency updates logged in `db/query_history.db` with schema checks for robustness.

### Setup Instructions
1. Clone repo: `git clone https://github.com/yourusername/open-travel-voice-assistant.git`.
2. Activate venv: `source llm_venv/bin/activate` (for LLM) or `source rasa-bot/rasa_venv/bin/activate` (for Rasa).
3. Install deps: See requirements.txt (`pip install -r requirements.txt`).
4. Download Piper model: `python -m piper.download_voices en_US-lessac-medium`.
5. Set Piper path: Move files to `~/.local/share/piper/voices/en_US-lessac-medium/`.
6. Create database dir: `mkdir -p ~/livekit-travel-voice-assistant/db`.
7. Initialize database: `sqlite3 ~/livekit-travel-voice-assistant/db/query_history.db "CREATE TABLE IF NOT EXISTS query_history (id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT, response TEXT, tool_name TEXT, timestamp INTEGER, date TEXT, query_count INTEGER DEFAULT 1)"`.
8. Start services: `sudo systemctl start currency_converter hybrid_rasa_llm rasa rasa_actions rasa_train`.
9. Test Rasa: `curl -X POST http://localhost:5005/webhooks/rest/webhook -d '{"sender": "test", "message": "Book a flight to Paris"}'`.
10. Test LLM: `curl -X POST http://127.0.0.1:5000/llm -d '{"input": "What is the weather in Mumbai?"}'`.
11. Check database: `sqlite3 ~/livekit-travel-voice-assistant/db/query_history.db "SELECT * FROM query_history ORDER BY timestamp DESC LIMIT 5;"`.
12. Frontend: Host web-frontend/index.html (add LiveKit integration).
13. Deploy: Use Docker/K8s manifests in docker/k8s.
14. GitHub: Push changes: `git add .; git commit -m "Update"; git push`.

### Architecture
- Hybrid Backend: `hybrid_rasa_llm.py` (Flask + LangGraph + Llama + tools).
- Rasa: `rasa-bot/` (NLU, dialogues, `actions.py` for APIs).
- Currency: `currency_converter.py` (DB + scheduler).
- Auto-Train: `rasa_train.py` (APScheduler + `query_history.db`).
- Voice: Prep for LiveKit/Piper (add `voice_bot.py`).
- Database: Shared `db/query_history.db` for Rasa/LLM queries and currency updates with schema checks.

### Testing
- Curl LLM: `curl -X POST http://127.0.0.1:5000/llm -d '{"input": "hello"}'`.
- Curl Rasa: As above.
- Logs: `tail -f hybrid_rasa_llm.log rasa_train.log currency_converter.log rasa-bot/actions.log`.
- Database: Check queries with SQLite command above.
- Troubleshoot Database: If `query_count` errors occur, run `sqlite3 ~/livekit-travel-voice-assistant/db/query_history.db "ALTER TABLE query_history ADD COLUMN query_count INTEGER DEFAULT 1;"`.

License: MIT
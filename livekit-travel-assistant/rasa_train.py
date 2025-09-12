import sqlite3
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import os
import logging
import yaml
from fuzzywuzzy import fuzz
import re  # For better entity extraction

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rasa_train.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def generate_nlu_data(db_path="query_history.db", max_age_hours=6, similarity_threshold=90):
    """Generate NLU training data from query_history.db."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT query, tool_name FROM query_history WHERE timestamp > ?",
                (int(datetime.now().timestamp()) - max_age_hours * 3600,)
            )
            queries = cursor.fetchall()
            nlu_data = {"version": "3.1", "nlu": []}
            existing_examples = set()
            
            # Load existing nlu.yml to avoid duplicates
            nlu_path = "rasa-bot/data/nlu.yml"
            with open(nlu_path, "r") as f:
                existing_nlu = yaml.safe_load(f)
                for intent_data in existing_nlu.get("nlu", []):
                    for example in intent_data.get("examples", "").split("\n"):
                        if example.startswith("- "):
                            existing_examples.add(example[2:].strip())
            
            intent_map = {
                "get_weather": "ask_weather",
                "get_flights": "ask_flights",
                "get_attractions": "ask_attractions",
                "get_currency_conversion": "ask_currency",
                "get_time": "ask_time",
                "get_joke": "nlu_fallback",
                "update_currency_rates": "nlu_fallback"
            }
            
            for query, tool_name in queries:
                # Skip duplicates
                if any(fuzz.ratio(query.lower(), ex.lower()) >= similarity_threshold for ex in existing_examples):
                    continue
                
                intent = intent_map.get(tool_name, "nlu_fallback")
                
                # Improved entity extraction
                entities = []
                if intent == "ask_flights":
                    # Extract from/to with regex
                    from_match = re.search(r"from\s+([A-Za-z\s]+)(?=\sto)", query, re.I)
                    to_match = re.search(r"to\s+([A-Za-z\s]+)", query, re.I)
                    if from_match:
                        entities.append(f"[{from_match.group(1).strip()}](from_location)")
                    if to_match:
                        entities.append(f"[{to_match.group(1).strip()}](to_location)")
                
                # Format example with entities (Rasa markdown format)
                example = query
                for entity in entities:
                    value = entity[1:-len(entity.split("]")[1])]
                    example = example.replace(value, entity)
                
                # Append to intent
                for intent_data in nlu_data["nlu"]:
                    if intent_data["intent"] == intent:
                        intent_data["examples"] += f"\n- {example}"
                        break
                else:
                    nlu_data["nlu"].append({"intent": intent, "examples": f"- {example}"})
                
                existing_examples.add(example)
            
            if nlu_data["nlu"]:
                # Append to existing nlu.yml
                with open(nlu_path, "a") as f:
                    for new_intent in nlu_data["nlu"]:
                        f.write(yaml.safe_dump([new_intent], allow_unicode=True))
                logger.info("Appended new examples to nlu.yml")
            else:
                logger.info("No new examples to append")
            
            return len(queries)
    except Exception as e:
        logger.error(f"Error generating NLU data: {e}")
        return 0

def train_rasa():
    """Run rasa train and restart rasa.service."""
    try:
        num_new = generate_nlu_data()
        if num_new > 0:
            # Run rasa train in rasa_venv
            cmd = (
                "source ~/livekit-travel-voice-assistant/rasa-bot/rasa_venv/bin/activate && "
                "cd ~/livekit-travel-voice-assistant/rasa-bot && "
                "rasa train"
            )
            result = os.system(cmd)
            if result == 0:
                logger.info("Rasa training completed successfully")
                # Restart rasa.service
                os.system("sudo systemctl restart rasa.service")
                logger.info("Rasa service restarted")
            else:
                logger.error(f"Rasa training failed with exit code {result}")
        else:
            logger.warning("No new data; skipping training")
    except Exception as e:
        logger.error(f"Rasa training failed: {e}")

def main():
    """Schedule Rasa training every 6 hours."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(train_rasa, 'interval', hours=6)
    scheduler.start()
    logger.info("Scheduler started for Rasa training every 6 hours")
    
    try:
        while True:
            time.sleep(60)  # Keep script running
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler")
        scheduler.shutdown()

if __name__ == "__main__":
    main()
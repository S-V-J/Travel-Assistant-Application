import sqlite3
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import os
import logging
import yaml
from fuzzywuzzy import fuzz
import re
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rasa_train.log', mode='w'),  # Overwrite log file each time the script runs
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def generate_nlu_data(DB_PATH="/home/stjl0/livekit-travel-voice-assistant/db/query_history.db", max_age_hours=6, similarity_threshold=90):
    """Generate NLU training data from query_history.db."""
    try:
        with sqlite3.connect(DB_PATH) as conn:  # Fixed: Use DB_PATH instead of db_path
            cursor = conn.cursor()
            cursor.execute(
                "SELECT query, tool_name FROM query_history WHERE timestamp > ?",
                (int(datetime.now().timestamp()) - max_age_hours * 3600,)
            )
            queries = cursor.fetchall()
            nlu_data = {"version": "3.1", "nlu": []}
            existing_examples = set()
            
            # Load existing nlu.yml to avoid duplicates
            nlu_path = "/home/stjl0/livekit-travel-voice-assistant/rasa-bot/data/nlu.yml"
            try:
                with open(nlu_path, "r") as f:
                    existing_nlu = yaml.safe_load(f) or {"nlu": []}
                    for intent_data in existing_nlu.get("nlu", []):
                        for example in intent_data.get("examples", "").split("\n"):
                            if example.startswith("- "):
                                existing_examples.add(example[2:].strip())
            except FileNotFoundError:
                logger.warning(f"NLU file {nlu_path} not found. Starting with empty NLU data.")
            
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
                if any(fuzz.ratio(query.lower(), ex.lower()) >= similarity_threshold for ex in existing_examples):
                    continue
                
                intent = intent_map.get(tool_name, "nlu_fallback")
                
                entities = []
                if intent == "ask_flights":
                    from_match = re.search(r"from\s+([A-Za-z\s]+)(?=\sto)", query, re.I)
                    to_match = re.search(r"to\s+([A-Za-z\s]+)", query, re.I)
                    if from_match:
                        entities.append(f"[{from_match.group(1).strip()}](from_location)")
                    if to_match:
                        entities.append(f"[{to_match.group(1).strip()}](to_location)")
                
                example = query
                for entity in entities:
                    value = entity[1:-len(entity.split("]")[1])]
                    example = example.replace(value, entity)
                
                for intent_data in nlu_data["nlu"]:
                    if intent_data["intent"] == intent:
                        intent_data["examples"] += f"\n- {example}"
                        break
                else:
                    nlu_data["nlu"].append({"intent": intent, "examples": f"- {example}"})
                
                existing_examples.add(example)
            
            if nlu_data["nlu"]:
                # Read existing NLU data and merge
                try:
                    with open(nlu_path, "r") as f:
                        existing_nlu = yaml.safe_load(f) or {"version": "3.1", "nlu": []}
                except FileNotFoundError:
                    existing_nlu = {"version": "3.1", "nlu": []}
                
                # Merge new intents with existing ones
                for new_intent in nlu_data["nlu"]:
                    for existing_intent in existing_nlu["nlu"]:
                        if existing_intent["intent"] == new_intent["intent"]:
                            existing_intent["examples"] += new_intent["examples"]
                            break
                    else:
                        existing_nlu["nlu"].append(new_intent)
                
                # Write back to nlu.yml
                with open(nlu_path, "w") as f:  # Overwrite instead of append to avoid YAML issues
                    yaml.safe_dump(existing_nlu, f, allow_unicode=True, sort_keys=False)
                logger.info(f"Updated {nlu_path} with {len(nlu_data['nlu'])} new intent examples")
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
            cmd = (
                f"source {os.environ.get('VIRTUAL_ENV')}/bin/activate && "
                f"cd /home/stjl0/livekit-travel-voice-assistant/rasa-bot && "
                "rasa train"
            )
            logger.info(f"Executing command: {cmd}")
            result = os.system(cmd)
            if result == 0:
                logger.info("Rasa training completed successfully")
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
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler")
        scheduler.shutdown()

if __name__ == "__main__":
    main()
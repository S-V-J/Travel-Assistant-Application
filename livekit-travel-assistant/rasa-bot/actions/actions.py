from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import requests
from geopy.geocoders import Nominatim
from datetime import datetime
import os
import sqlite3
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/stjl0/livekit-travel-voice-assistant/rasa-bot/actions.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# API Keys from .env
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY")
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
TIMEZONEDB_API_KEY = os.getenv("TIMEZONEDB_API_KEY")

# Initialize geolocator
geolocator = Nominatim(user_agent="travel_assistant")

# Check if query_count column exists in query_history table
def check_query_count_column(db_path: str = "/home/stjl0/livekit-travel-voice-assistant/db/query_history.db") -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(query_history);")
            columns = [info[1] for info in cursor.fetchall()]
            return "query_count" in columns
    except Exception as e:
        logger.error(f"Error checking query_count column: {e}")
        return False

# Function to store queries in the shared database
def store_rasa_query(query: str, response: str, tool_name: str, db_path: str = "/home/stjl0/livekit-travel-voice-assistant/db/query_history.db"):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            has_query_count = check_query_count_column(db_path)
            # Check if query exists and increment count if query_count exists
            cursor.execute("SELECT id, query_count FROM query_history WHERE query = ?", (query,))
            existing = cursor.fetchone()
            if existing and has_query_count:
                cursor.execute("UPDATE query_history SET query_count = query_count + 1, timestamp = ?, date = ? WHERE id = ?",
                              (int(datetime.now().timestamp()), datetime.now().strftime('%Y-%m-%d'), existing[0]))
            else:
                if has_query_count:
                    cursor.execute("""
                        INSERT INTO query_history (query, response, tool_name, timestamp, date, query_count)
                        VALUES (?, ?, ?, ?, ?, 1)
                    """, (query, response, tool_name, int(datetime.now().timestamp()), datetime.now().strftime('%Y-%m-%d')))
                else:
                    cursor.execute("""
                        INSERT INTO query_history (query, response, tool_name, timestamp, date)
                        VALUES (?, ?, ?, ?, ?)
                    """, (query, response, tool_name, int(datetime.now().timestamp()), datetime.now().strftime('%Y-%m-%d')))
            conn.commit()
            logger.info(f"Stored Rasa query: {query} with response: {response}")
    except Exception as e:
        logger.error(f"Error storing Rasa query: {e}")

class ActionConfirmLocation(Action):
    def name(self) -> Text:
        return "action_confirm_location"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Get entities and slots
        location = next(tracker.get_latest_entity_values('location'), None)
        from_location = next(tracker.get_latest_entity_values('from_location'), tracker.get_slot('from_location'))
        to_location = next(tracker.get_latest_entity_values('to_location'), tracker.get_slot('to_location'))
        intent = tracker.latest_message.get('intent', {}).get('name')
        query = tracker.latest_message.get('text', '')

        # Debugging
        logger.debug(f"Intent: {intent}, Location: {location}, From: {from_location}, To: {to_location}")

        # Handle flight intent
        if intent == "ask_flights":
            if to_location and not from_location:
                response = "You mentioned a flight to {}. Could you specify the departure city?".format(to_location)
                dispatcher.utter_message(text=response)
                store_rasa_query(query, response, "get_flights")
                return [SlotSet("to_location", to_location), SlotSet("from_location", None)]
            if from_location and to_location:
                response = "Just to confirm, you want a flight from {} to {}?".format(from_location, to_location)
                dispatcher.utter_message(text=response)
                store_rasa_query(query, response, "get_flights")
                return [SlotSet("from_location", from_location), SlotSet("to_location", to_location)]
            if from_location and not to_location:
                response = "You mentioned a flight from {}. Could you specify the destination city?".format(from_location)
                dispatcher.utter_message(text=response)
                store_rasa_query(query, response, "get_flights")
                return [SlotSet("from_location", from_location), SlotSet("to_location", None)]
            response = "Please provide both departure and destination cities for flights."
            dispatcher.utter_message(text=response)
            store_rasa_query(query, response, "get_flights")
            return [SlotSet("from_location", None), SlotSet("to_location", None)]

        # Handle general location-based intents
        if location and intent in ["ask_weather", "ask_attractions", "ask_time", "inform_location"]:
            loc = geolocator.geocode(location)
            if not loc:
                response = "Sorry, couldn't find that location. Try another?"
                dispatcher.utter_message(text=response)
                store_rasa_query(query, response, intent.replace("ask_", "get_"))
                return [SlotSet("location", None)]
            response = "Just to confirm, you mean {}?".format(location)
            dispatcher.utter_message(text=response)
            store_rasa_query(query, response, intent.replace("ask_", "get_"))
            return [SlotSet("location", location)]

        # Skip unnecessary confirmation if no relevant entities
        return []

class ActionOfferServices(Action):
    def name(self) -> Text:
        return "action_offer_services"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        query = tracker.latest_message.get('text', '')
        response = "I can help with weather, flights, attractions, currency, or time zones. What's next?"
        dispatcher.utter_message(text=response)
        store_rasa_query(query, response, "none")
        return []

class ActionProvideWeather(Action):
    def name(self) -> Text:
        return "action_provide_weather"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        query = tracker.latest_message.get('text', '')
        location = tracker.get_slot('location')
        if not location:
            response = "Please provide a location."
            dispatcher.utter_message(text=response)
            store_rasa_query(query, response, "get_weather")
            return []
        loc = geolocator.geocode(location)
        if not loc:
            response = "Sorry, couldn't find that location."
            dispatcher.utter_message(text=response)
            store_rasa_query(query, response, "get_weather")
            return []
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={loc.latitude}&lon={loc.longitude}&appid={OPENWEATHERMAP_API_KEY}&units=metric"
            response = requests.get(url).json()
            if response['cod'] != 200:
                response_text = "Weather data not available."
                dispatcher.utter_message(text=response_text)
                store_rasa_query(query, response_text, "get_weather")
                return []
            temp = response['main']['temp']
            description = response['weather'][0]['description']
            advice = "Pack light clothes and sunglasses!" if temp > 20 else "Bring layers and maybe an umbrella!"
            response_text = f"Current weather in {location}: {temp}°C, {description}. {advice}"
            dispatcher.utter_message(text=response_text)
            store_rasa_query(query, response_text, "get_weather")
            dispatcher.utter_message(response_key="utter_proactive_offer")
            return []
        except Exception as e:
            response_text = f"Couldn't fetch weather data: {e}"
            dispatcher.utter_message(text=response_text)
            store_rasa_query(query, response_text, "get_weather")
            return []

class ActionProvideFlights(Action):
    def name(self) -> Text:
        return "action_provide_flights"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        query = tracker.latest_message.get('text', '')
        from_location = tracker.get_slot('from_location')
        to_location = tracker.get_slot('to_location')
        if not (from_location and to_location):
            response = "Please provide both departure and destination cities."
            dispatcher.utter_message(text=response)
            store_rasa_query(query, response, "get_flights")
            return []
        try:
            token_url = "https://test.api.amadeus.com/v1/security/oauth2/token"
            data = {
                "grant_type": "client_credentials",
                "client_id": AMADEUS_API_KEY,
                "client_secret": AMADEUS_API_SECRET
            }
            token_response = requests.post(token_url, data=data).json()
            access_token = token_response.get("access_token")
            if not access_token:
                response = "Failed to authenticate with Amadeus API."
                dispatcher.utter_message(text=response)
                store_rasa_query(query, response, "get_flights")
                return []
            
            url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
            params = {
                "originLocationCode": from_location.upper()[:3],
                "destinationLocationCode": to_location.upper()[:3],
                "departureDate": datetime.today().date().isoformat(),
                "adults": 1
            }
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, params=params, headers=headers).json()
            if 'data' in response and response['data']:
                flight = response['data'][0]
                duration = flight['itineraries'][0]['duration']
                price = flight['price']['total']
                response_text = f"Found flight from {from_location} to {to_location}: Duration {duration}, price {price} EUR."
                dispatcher.utter_message(text=response_text)
                store_rasa_query(query, response_text, "get_flights")
            else:
                response_text = "No flights found."
                dispatcher.utter_message(text=response_text)
                store_rasa_query(query, response_text, "get_flights")
            return []
        except Exception as e:
            response_text = f"Couldn't fetch flight data: {e}"
            dispatcher.utter_message(text=response_text)
            store_rasa_query(query, response_text, "get_flights")
            return []

class ActionProvideAttractions(Action):
    def name(self) -> Text:
        return "action_provide_attractions"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        query = tracker.latest_message.get('text', '')
        location = tracker.get_slot('location')
        if not location:
            response = "Please provide a location."
            dispatcher.utter_message(text=response)
            store_rasa_query(query, response, "get_attractions")
            return []
        loc = geolocator.geocode(location)
        if not loc:
            response = "Sorry, couldn't find that location."
            dispatcher.utter_message(text=response)
            store_rasa_query(query, response, "get_attractions")
            return []
        try:
            url = f"https://api.geoapify.com/v2/places?categories=tourism.attraction&filter=circle:{loc.longitude},{loc.latitude},5000&apiKey={GEOAPIFY_API_KEY}"
            response = requests.get(url).json()
            attractions = [feature['properties']['name'] for feature in response['features'] if 'name' in feature['properties']][:3]
            if attractions:
                response_text = f"Top attractions in {location}: {', '.join(attractions)}. Practical tip: Use public transport!"
                dispatcher.utter_message(text=response_text)
                store_rasa_query(query, response_text, "get_attractions")
            else:
                response_text = "No attractions found for this location."
                dispatcher.utter_message(text=response_text)
                store_rasa_query(query, response_text, "get_attractions")
            return []
        except Exception as e:
            response_text = f"Couldn't fetch attractions: {e}"
            dispatcher.utter_message(text=response_text)
            store_rasa_query(query, response_text, "get_attractions")
            return []

class ActionProvideCurrency(Action):
    def name(self) -> Text:
        return "action_provide_currency"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        query = tracker.latest_message.get('text', '')
        amount = tracker.get_slot('amount')
        from_cur = tracker.get_slot('currency_from')
        to_cur = tracker.get_slot('currency_to')
        if not (amount and from_cur and to_cur):
            response = "Please provide amount and currencies (e.g., 100 USD to EUR)."
            dispatcher.utter_message(text=response)
            store_rasa_query(query, response, "get_currency_conversion")
            return []
        try:
            url = f"https://v6.exchangerate-api.com/v6/{EXCHANGERATE_API_KEY}/pair/{from_cur}/{to_cur}/{amount}"
            response = requests.get(url).json()
            if response['result'] == "success":
                result = round(response['conversion_result'], 2)
                response_text = f"{amount} {from_cur} is {result} {to_cur}—that's about the cost of a nice dinner!"
                dispatcher.utter_message(text=response_text)
                store_rasa_query(query, response_text, "get_currency_conversion")
            else:
                response_text = "Currency conversion not available."
                dispatcher.utter_message(text=response_text)
                store_rasa_query(query, response_text, "get_currency_conversion")
            return []
        except Exception as e:
            response_text = f"Couldn't fetch currency data: {e}"
            dispatcher.utter_message(text=response_text)
            store_rasa_query(query, response_text, "get_currency_conversion")
            return []

class ActionProvideTime(Action):
    def name(self) -> Text:
        return "action_provide_time"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        query = tracker.latest_message.get('text', '')
        location = tracker.get_slot('location')
        if not location:
            response = "Please provide a location."
            dispatcher.utter_message(text=response)
            store_rasa_query(query, response, "get_time")
            return []
        loc = geolocator.geocode(location)
        if not loc:
            response = "Sorry, couldn't find that location."
            dispatcher.utter_message(text=response)
            store_rasa_query(query, response, "get_time")
            return []
        try:
            url = f"http://api.timezonedb.com/v2.1/get-time-zone?key={TIMEZONEDB_API_KEY}&format=json&by=position&lat={loc.latitude}&lng={loc.longitude}"
            response = requests.get(url).json()
            if response['status'] == "OK":
                time = datetime.fromtimestamp(response['timestamp']).strftime('%H:%M')
                response_text = f"Current time in {location}: {time} ({response['zoneName']})."
                dispatcher.utter_message(text=response_text)
                store_rasa_query(query, response_text, "get_time")
            else:
                response_text = "Time data not available."
                dispatcher.utter_message(text=response_text)
                store_rasa_query(query, response_text, "get_time")
            return []
        except Exception as e:
            response_text = f"Couldn't fetch time data: {e}"
            dispatcher.utter_message(text=response_text)
            store_rasa_query(query, response_text, "get_time")
            return []

class ActionLlmFallback(Action):
    def name(self) -> Text:
        return "action_llm_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        query = tracker.latest_message.get('text', '')
        try:
            # Call LLM Flask API
            url = "http://127.0.0.1:5000/llm"
            payload = {"input": query, "chat_history": tracker.get_slot('chat_history') or []}
            response = requests.post(url, json=payload).json()
            llm_response = response.get('response', "Sorry, couldn't process that.")
            dispatcher.utter_message(text=llm_response)
            store_rasa_query(query, llm_response, "none")
        except Exception as e:
            response_text = f"Sorry, LLM fallback failed: {e}"
            dispatcher.utter_message(text=response_text)
            store_rasa_query(query, response_text, "none")
        return []
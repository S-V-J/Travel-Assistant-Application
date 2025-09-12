import requests
from geopy.geocoders import Nominatim
from datetime import datetime, date
from langchain_core.tools import tool
from config import OPENWEATHERMAP_API_KEY, AMADEUS_API_KEY, AMADEUS_API_SECRET, GEOAPIFY_API_KEY, TIMEZONEDB_API_KEY, EXCHANGERATE_API_KEY
import random
from functools import lru_cache
from time import time
import logging
from currency_converter import CurrencyConverter

logger = logging.getLogger(__name__)

geolocator = Nominatim(user_agent="travel_assistant")

IATA_CODES = {
    "new york": "NYC",
    "london": "LON",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "paris": "PAR"
}

@lru_cache(maxsize=1)
def get_amadeus_token():
    """Gets and caches Amadeus API token."""
    token_url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_API_KEY,
        "client_secret": AMADEUS_API_SECRET
    }
    try:
        response = requests.post(token_url, data=data).json()
        logger.debug(f"Amadeus token response: {response}")
        access_token = response.get("access_token")
        if not access_token:
            raise ValueError("Failed to authenticate with Amadeus API.")
        return access_token, time() + response.get("expires_in", 1799)
    except Exception as e:
        logger.error(f"Amadeus API error: {e}")
        raise

@tool
def get_weather(location: str) -> str:
    """Fetches the current weather for a given location, including temperature, description, and packing advice."""
    loc = geolocator.geocode(location)
    if not loc:
        return "Location not found. Ask for confirmation."
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={loc.latitude}&lon={loc.longitude}&appid={OPENWEATHERMAP_API_KEY}&units=metric"
    try:
        response = requests.get(url).json()
        logger.debug(f"Weather API response: {response}")
        if response['cod'] != 200:
            return f"Weather data not available: {response.get('message', 'Unknown error')}"
        temp = response['main']['temp']
        description = response['weather'][0]['description']
        pack = "Pack light clothes and sunscreen" if temp > 20 else "Bring layers and an umbrella"
        return f"Current weather in {location}: {temp}°C, {description}. {pack}."
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return f"Error fetching weather data: {str(e)}"

@tool
def get_flights(from_location: str, to_location: str) -> str:
    """Searches for flights between two locations, returning duration and price if available."""
    from_code = IATA_CODES.get(from_location.lower())
    to_code = IATA_CODES.get(to_location.lower())
    if not from_code or not to_code:
        return f"Invalid airport codes for {from_location} or {to_location}. Please use city names like 'New York' or 'London'."
    try:
        access_token, expiry = get_amadeus_token()
        if time() > expiry:
            get_amadeus_token.cache_clear()
            access_token, expiry = get_amadeus_token()
        url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
        params = {
            "originLocationCode": from_code,
            "destinationLocationCode": to_code,
            "departureDate": date.today().isoformat(),
            "adults": 1
        }
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(url, params=params, headers=headers).json()
        logger.debug(f"Flights API response: {response}")
        if 'data' in response and response['data']:
            flight = response['data'][0]
            duration = flight['itineraries'][0]['duration']
            price = flight['price']['total']
            return f"Found flight from {from_location} to {to_location}: Duration {duration}, price {price} EUR."
        return "No flights found for the specified route or date."
    except Exception as e:
        logger.error(f"Flights API error: {e}")
        return f"Error searching flights: {str(e)}"

@tool
def get_attractions(location: str) -> str:
    """Retrieves a list of top tourist attractions for a given location."""
    loc = geolocator.geocode(location)
    if not loc:
        return "Location not found. Ask for confirmation."
    url = f"https://api.geoapify.com/v2/places?categories=tourism.attraction&filter=circle:{loc.longitude},{loc.latitude},10000&apiKey={GEOAPIFY_API_KEY}"
    try:
        response = requests.get(url).json()
        logger.debug(f"Attractions API response: {response}")
        attractions = [feature['properties']['name'] for feature in response['features'] if 'name' in feature['properties']][:3]
        if not attractions:
            return f"No attractions found in {location}."
        return f"Top attractions in {location}: {', '.join(attractions)}."
    except Exception as e:
        logger.error(f"Attractions API error: {e}")
        return f"Error fetching attractions: {str(e)}"

@tool
def get_currency_conversion(amount: float, from_cur: str, to_cur: str) -> str:
    """Converts an amount from one currency to another using stored exchange rates."""
    try:
        result = currency_converter.convert(amount, from_cur, to_cur)
        logger.debug(f"Currency conversion result: {result}")
        if result['success']:
            converted_amount = result['result']
            context = " (that's about the cost of a nice dinner)" if converted_amount >= 20 else " (that's about the cost of a coffee)"
            return f"{amount} {from_cur} is {converted_amount} {to_cur}{context}."
        if "not supported" in result['error']:
            return f"Currency conversion failed: {result['error']}. Try updating currency rates."
        return f"Currency conversion failed: {result['error']}."
    except Exception as e:
        logger.error(f"Currency conversion error: {e}")
        return f"Error converting currency: {str(e)}. Please check database or update rates."

@tool
def update_currency_rates() -> str:
    """Updates the currency exchange rates in the database."""
    try:
        result = currency_converter.update_rates()
        if result['success']:
            return f"Currency rates updated successfully for {result['date']}."
        return f"Failed to update currency rates: {result['error']}."
    except Exception as e:
        logger.error(f"Update rates error: {e}")
        return f"Error updating currency rates: {str(e)}."

@tool
def get_time(location: str) -> str:
    """Fetches the current local time for a given location."""
    loc = geolocator.geocode(location)
    if not loc:
        return "Location not found. Ask for confirmation."
    url = f"http://api.timezonedb.com/v2.1/get-time-zone?key={TIMEZONEDB_API_KEY}&format=json&by=position&lat={loc.latitude}&lng={loc.longitude}"
    try:
        response = requests.get(url).json()
        logger.debug(f"Time API response: {response}")
        if response['status'] == 'OK':
            time = datetime.fromtimestamp(response['timestamp']).strftime('%H:%M')
            return f"Current time in {location}: {time} ({response['zoneName']})."
        return f"Time data not available: {response.get('message', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Time API error: {e}")
        return f"Error fetching time: {str(e)}"

@tool
def get_joke() -> str:
    """Returns a random travel-themed joke."""
    jokes = [
        "Why did the airplane go to therapy? It had too many baggage issues.",
        "Why don't mountains get lost? They always know their peak.",
        "What do you call a dinosaur that takes the scenic route? A Tour-a-saurus."
    ]
    return random.choice(jokes)

# Export the tools list for use in agent.py
tools = [
    get_weather,
    get_flights,
    get_attractions,
    get_currency_conversion,
    update_currency_rates,
    get_time,
    get_joke
]
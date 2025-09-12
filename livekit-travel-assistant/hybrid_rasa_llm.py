from flask import Flask, request, jsonify
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langchain_core.tools import tool
from dotenv import load_dotenv
import requests
from geopy.geocoders import Nominatim
from datetime import datetime, date
import os
import json
import re
import sqlite3
import logging
from langchain_community.llms import LlamaCpp
from typing import Dict, List, Any, Optional
from langchain_core.prompts import PromptTemplate
from functools import lru_cache
from time import time
import random
from currency_converter import CurrencyConverter
from langgraph.checkpoint.memory import MemorySaver
from fuzzywuzzy import fuzz
import time as time_module

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hybrid_rasa_llm.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Access API Keys from .env
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY")
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
TIMEZONEDB_API_KEY = os.getenv("TIMEZONEDB_API_KEY")

# Initialize Flask app
app = Flask(__name__)

# Initialize geolocator
geolocator = Nominatim(user_agent="travel_assistant")

# Initialize CurrencyConverter
currency_converter = CurrencyConverter(access_key=EXCHANGERATE_API_KEY)

# Initialize SQLite database for query history
def init_query_db(db_path="query_history.db"):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT,
                    response TEXT,
                    tool_name TEXT,
                    timestamp INTEGER,
                    date TEXT,
                    query_count INTEGER DEFAULT 1
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_query ON query_history (query)")
            conn.commit()
        logger.info("Query history database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing query database: {e}")
        raise

# Initialize the database
init_query_db()

# Model paths (GGUF files)
model_1b_path = os.path.expanduser("~/.llama/checkpoints/Llama3.2-1B-Instruct.gguf")
model_3b_path = os.path.expanduser("~/.llama/checkpoints/Llama3.2-3B-Instruct.gguf")

# Verify model paths exist
if not os.path.exists(model_1b_path) or not os.path.exists(model_3b_path):
    raise FileNotFoundError(f"Model files not found: {model_1b_path}, {model_3b_path}")

# Load Llama models with LlamaCpp
try:
    llm_1b = LlamaCpp(
        model_path=model_1b_path,
        n_ctx=1024,
        n_gpu_layers=50,
        temperature=0.1,
        max_tokens=1000,
        verbose=True,
        stop=["\n", "Please", "<|eot_id|>", "Result:", "Note:", "This is", ";"]
    )
    llm_3b = LlamaCpp(
        model_path=model_3b_path,
        n_ctx=1024,
        n_gpu_layers=50,
        temperature=0.1,
        max_tokens=1000,
        verbose=True,
        stop=["\n", "Please", "<|eot_id|>", "Result:", "Note:", "This is", ";"]
    )
except Exception as e:
    logger.error(f"Error loading Llama models: {e}")
    raise

# Custom LLM wrapper to switch between 1B and 3B based on input length
class DynamicLlamaCpp:
    def __init__(self, llm_1b, llm_3b):
        self.llm_1b = llm_1b
        self.llm_3b = llm_3b

    def invoke(self, input, config=None, **kwargs):
        if isinstance(input, list):
            prompt_text = "\n".join([msg.content if hasattr(msg, 'content') else str(msg) for msg in input])
        else:
            prompt_text = str(input)
        
        input_tokens = len(self.llm_1b.client.tokenize(prompt_text.encode('utf-8')))
        selected_llm = self.llm_1b if input_tokens < 100 else self.llm_3b
        logger.info(f"Selected model: {'1B' if input_tokens < 100 else '3B'} for {input_tokens} tokens")
        logger.debug(f"Input prompt: {prompt_text}")
        return selected_llm.invoke(prompt_text, config=config, **kwargs)

# Initialize dynamic LLM
llm = DynamicLlamaCpp(llm_1b=llm_1b, llm_3b=llm_3b)

# Use MemorySaver for LangGraph checkpointing
try:
    checkpoint = MemorySaver()
except ImportError as e:
    logger.error(f"Failed to import MemorySaver: {e}")
    raise ImportError("Ensure langgraph is installed with checkpointing support. Run: pip install langgraph")

# System message with updated tools
system_message = """You are a travel assistant. Respond EXCLUSIVELY with:
- A single valid JSON object for tool calls: {"name": "tool_name", "parameters": {...}}
- Plain text for direct answers (e.g., for general questions like jokes).
DO NOT include explanations, notes, simulated chat interfaces, multiple JSON objects, or extra text like 'assistant: '. DO NOT use semicolons to separate JSON objects.

Available tools and their required parameters:
1. get_weather: {"location": "string"}
2. get_flights: {"from_location": "string", "to_location": "string"} (DO NOT use "from_city" or "to_city")
3. get_attractions: {"location": "string"}
4. get_currency_conversion: {"amount": number, "from_cur": "string", "to_cur": "string"}
5. get_time: {"location": "string"}
6. get_joke: {}
7. update_currency_rates: {}

Examples of valid responses:
- User: "What is the weather in Tokyo?"
  Response: {"name": "get_weather", "parameters": {"location": "Tokyo"}}
- User: "Tell me a joke."
  Response: "Why did the airplane go to therapy? It had too many baggage issues."
- User: "Find flights from New York to London."
  Response: {"name": "get_flights", "parameters": {"from_location": "New York", "to_location": "London"}}
- User: "Convert 100 USD to EUR."
  Response: {"name": "get_currency_conversion", "parameters": {"amount": 100, "from_cur": "USD", "to_cur": "EUR"}}
- User: "Update currency rates."
  Response: {"name": "update_currency_rates", "parameters": {}}

Invalid responses (DO NOT USE):
- assistant: {"name": "get_weather", "parameters": {"location": "Tokyo"}}
- {"name": "get_flights", "parameters": {"from_city": "New York", "to_city": "London"}}
- {"name": "get_joke", "parameters": {}}
- {"name": "get_weather", "parameters": {"location": "Tokyo"}}; {"name": "other_tool", ...}
- Note: Processing...

Current date: {date}
"""

# API Tools
@tool
def get_weather(location: str) -> str:
    """Get current weather for a location. Input: location."""
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

# Simple IATA code mapping
IATA_CODES = {
    "new york": "NYC",
    "london": "LON",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "paris": "PAR"
}

@lru_cache(maxsize=1)
def get_amadeus_token():
    """Get and cache Amadeus API token."""
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
def get_flights(from_location: str, to_location: str) -> str:
    """Search for flights between two locations. Input: from_location, to_location."""
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
    """Get tourist attractions for a location. Input: location."""
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
    """Convert currency using stored rates. Input: amount, from_cur, to_cur."""
    try:
        result = currency_converter.convert(amount, from_cur, to_cur)
        logger.debug(f"Currency conversion result: {result}")
        if result['success']:
            converted_amount = result['result']
            context = " (that's about the cost of a nice dinner)" if converted_amount >= 20 else " (that's about the cost of a coffee)"
            return f"{amount} {from_cur} is {converted_amount} {to_cur}{context}."
        # Suggest updating rates if currency is not supported
        if "not supported" in result['error']:
            return f"Currency conversion failed: {result['error']}. Try updating currency rates."
        return f"Currency conversion failed: {result['error']}."
    except Exception as e:
        logger.error(f"Currency conversion error: {e}")
        return f"Error converting currency: {str(e)}. Please check database or update rates."

@tool
def update_currency_rates() -> str:
    """Manually update currency rates in the database."""
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
    """Get current time for a location. Input: location."""
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
    """Return a random travel-themed joke."""
    jokes = [
        "Why did the airplane go to therapy? It had too many baggage issues.",
        "Why don't mountains get lost? They always know their peak.",
        "What do you call a dinosaur that takes the scenic route? A Tour-a-saurus."
    ]
    return random.choice(jokes)

# List of tools for the agent
tools = [get_weather, get_flights, get_attractions, get_currency_conversion, get_time, get_joke, update_currency_rates]
tool_map = {tool.name: tool for tool in tools}

# Prompt template
prompt_template = PromptTemplate.from_template(
    """{system_message}

Available tools: {tool_names}

Current date: {date}
User input: {input}
Chat history: {history}
"""
)

# Define state for the agent
class AgentState(Dict):
    messages: List[Any]

# Function to check cache for recent responses with fuzzy matching
def check_cache(query: str, db_path: str = "query_history.db", max_age_hours: int = 24, similarity_threshold: int = 90) -> Optional[str]:
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT query, response FROM query_history 
                WHERE timestamp > ? 
                ORDER BY timestamp DESC
            """, (int(time()) - max_age_hours * 3600,))
            results = cursor.fetchall()
            for cached_query, response in results:
                if fuzz.ratio(query.lower(), cached_query.lower()) >= similarity_threshold:
                    logger.info(f"Cache hit for query: {query} (matched: {cached_query})")
                    return response
            logger.info(f"Cache miss for query: {query}")
            return None
    except Exception as e:
        logger.error(f"Error checking cache: {e}")
        return None

# Function to store query and response in database
def store_query_response(query: str, response: str, tool_name: str, db_path: str = "query_history.db"):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Check if query exists and increment count
            cursor.execute("SELECT id, query_count FROM query_history WHERE query = ?", (query,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("UPDATE query_history SET query_count = query_count + 1, timestamp = ?, date = ? WHERE id = ?",
                              (int(time()), datetime.now().strftime('%Y-%m-%d'), existing[0]))
            else:
                cursor.execute("""
                    INSERT INTO query_history (query, response, tool_name, timestamp, date, query_count)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (query, response, tool_name, int(time()), datetime.now().strftime('%Y-%m-%d')))
            conn.commit()
            logger.info(f"Stored query: {query} with response: {response}")
    except Exception as e:
        logger.error(f"Error storing query/response: {e}")

# Clean up old database entries
def cleanup_old_entries(db_path: str = "query_history.db", max_age_days: int = 30):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM query_history WHERE timestamp < ?",
                          (int(time()) - max_age_days * 24 * 3600,))
            conn.commit()
            logger.info(f"Cleaned up {cursor.rowcount} old entries from query_history")
    except Exception as e:
        logger.error(f"Error cleaning up database: {e}")

# Agent node to process input and generate response
def agent_node(state: AgentState, llm, tools, tool_map):
    start_time = time_module.time()
    user_input = state["messages"][-1].content
    history = "\n".join([f"{msg.type}: {msg.content}" for msg in state["messages"]])
    tool_names = ", ".join([tool.name for tool in tools])

    # Check cache for recent response
    cached_response = check_cache(user_input)
    if cached_response:
        response_time = time_module.time() - start_time
        logger.info(f"Response time (cache hit): {response_time:.2f} seconds")
        return {"messages": [AIMessage(content=cached_response)]}

    prompt = prompt_template.format(
        system_message=system_message,
        tool_names=tool_names,
        date=date.today().strftime('%d %b %Y'),
        input=user_input,
        history=history
    )

    response = llm.invoke(prompt).strip()
    logger.debug(f"Raw LLM response: {response}")

    if not response:
        logger.warning("LLM returned empty response")
        return {"messages": [AIMessage(content="Sorry, I couldn't generate a response. Please try again.")]}

    # Strip 'assistant: ' prefix if present
    response = response.replace("assistant: ", "").strip()

    # Try parsing as JSON
    json_match = re.match(r'\{.*\}', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
        try:
            tool_call = json.loads(json_str)
            if isinstance(tool_call, dict) and "name" in tool_call and "parameters" in tool_call:
                # Fix incorrect parameter names for get_flights
                if tool_call["name"] == "get_flights":
                    params = tool_call["parameters"]
                    if "from_city" in params:
                        params["from_location"] = params.pop("from_city")
                    if "to_city" in params:
                        params["to_location"] = params.pop("to_city")

                tool = tool_map.get(tool_call["name"])
                if tool:
                    try:
                        logger.info(f"Invoking tool: {tool_call['name']} with parameters: {tool_call['parameters']}")
                        tool_result = tool.invoke(tool_call["parameters"])
                        logger.debug(f"Tool result: {tool_result}")
                        # Store query and response in database
                        store_query_response(user_input, tool_result, tool_call["name"])
                        response_time = time_module.time() - start_time
                        logger.info(f"Response time (tool call): {response_time:.2f} seconds")
                        return {"messages": [AIMessage(content=tool_result)]}
                    except Exception as e:
                        logger.error(f"Tool execution error: {e}")
                        return {"messages": [AIMessage(content=f"Error executing tool {tool_call['name']}: {str(e)}")]}
                else:
                    logger.warning(f"Invalid tool name: {tool_call['name']}")
                    return {"messages": [AIMessage(content=f"Invalid tool name: {tool_call['name']}")]}
            else:
                logger.warning("Invalid tool call format")
                return {"messages": [AIMessage(content="Invalid tool call format.")]}
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return {"messages": [AIMessage(content="Sorry, I couldn't process that request. Please try again.")]}
    
    # If not JSON, treat as plain text response
    logger.info("Treating response as plain text")
    store_query_response(user_input, response, "none")
    response_time = time_module.time() - start_time
    logger.info(f"Response time (plain text): {response_time:.2f} seconds")
    return {"messages": [AIMessage(content=response)]}

# Create StateGraph
workflow = StateGraph(AgentState)
workflow.add_node("agent", lambda state: agent_node(state, llm, tools, tool_map))
workflow.add_edge("agent", END)
workflow.set_entry_point("agent")

# Compile the graph with MemorySaver
app_graph = workflow.compile(checkpointer=checkpoint)

@app.route('/llm', methods=['POST'])
def llm_fallback():
    data = request.json
    if not data or 'input' not in data:
        logger.error("Invalid request: 'input' field is required")
        return jsonify({"error": "Invalid request: 'input' field is required"}), 400
    
    user_input = data.get('input')
    chat_history = data.get('chat_history', [])
    try:
        messages = []
        for entry in chat_history:
            if entry.get('role') == 'user':
                messages.append(HumanMessage(content=entry.get('content')))
            elif entry.get('role') == 'assistant':
                messages.append(AIMessage(content=entry.get('content')))
        messages.append(HumanMessage(content=user_input))

        response = app_graph.invoke({"messages": messages}, config={"configurable": {"thread_id": "1"}})

        assistant_response = response['messages'][-1].content
        logger.info(f"Returning response: {assistant_response}")
        return jsonify({"response": assistant_response})
    except Exception as e:
        logger.error(f"Error in llm_fallback: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Clean up old database entries on startup
    cleanup_old_entries()
    app.run(host='127.0.0.1', port=5000)
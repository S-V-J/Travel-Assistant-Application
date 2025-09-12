from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langchain_core.prompts import PromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from typing import Dict, List, Any
import logging
from datetime import date
from time import time
from config import SYSTEM_MESSAGE
from database import check_cache, store_query_response
from tools import tools
from llm import DynamicLlamaCpp

logger = logging.getLogger(__name__)

# Initialize LLM
llm = DynamicLlamaCpp()

# Standard ReAct prompt (escaped {name} and removed unexpected location variable)
react_prompt = PromptTemplate.from_template(
    SYSTEM_MESSAGE + """
Answer the following questions as best you can. You have access to the following tools:

{tools_desc}

Use the following format:

Question: {input}
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}
"""
)

class AgentState(Dict):
    messages: List[Any]

def extract_location_from_history(history: str) -> str:
    """Extracts the last mentioned location from chat history."""
    lines = history.split("\n")
    for line in reversed(lines):
        for city in ["Tokyo", "Paris", "New York", "London", "Mumbai", "New Delhi"]:
            if city.lower() in line.lower():
                return city
    return ""

def agent_node(state: AgentState):
    start_time = time()
    user_input = state["messages"][-1].content
    history = "\n".join([f"{msg.type}: {msg.content}" for msg in state["messages"]])

    # Resolve ambiguous references like "there"
    if "there" in user_input.lower():
        location = extract_location_from_history(history)
        if location:
            user_input = user_input.replace("there", location)
        else:
            return {"messages": [AIMessage(content="Please specify the location.")]}
    logger.debug(f"Processed input: {user_input}")

    # Check cache
    cached_response = check_cache(user_input)
    if cached_response:
        response_time = time() - start_time
        logger.info(f"Response time (cache hit): {response_time:.2f} seconds")
        return {"messages": [AIMessage(content=cached_response)]}

    # Prepare tool names and descriptions
    tool_names = ", ".join([tool.name for tool in tools])
    tools_desc = "\n".join([f"{tool.name}: {tool.description}" for tool in tools])

    # Prepare tools as a list of dict schemas for the agent
    tools_schemas = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args_schema.schema() if tool.args_schema else {}
            }
        } for tool in tools
    ]

    # Create ReAct agent
    agent = create_react_agent(llm, tools, react_prompt)

    # Use AgentExecutor for chaining (runs the ReAct loop)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

    # Invoke executor
    try:
        response = executor.invoke({
            "input": user_input,
            "history": history,
            "date": date.today().strftime('%d %b %Y'),
            "agent_scratchpad": "",
            "tool_names": tool_names,
            "tools_desc": tools_desc,
            "tools": tools_schemas
        })
        output = response["output"]
        logger.debug(f"Agent output: {output}")

        # Store in database
        store_query_response(user_input, output, "react_agent", date.today().strftime('%Y-%m-%d'))
        response_time = time() - start_time
        logger.info(f"Response time (agent): {response_time:.2f} seconds")
        return {"messages": [AIMessage(content=output)]}
    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        return {"messages": [AIMessage(content=f"Error processing request: {str(e)}")]}

def create_workflow():
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_edge("agent", END)
    workflow.set_entry_point("agent")
    return workflow
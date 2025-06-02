from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from typing import TypedDict, Sequence, Annotated
from langchain_core.tools import tool
from terminal_controller import Process
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI

load_dotenv()

pw = Process()

class AgentState(TypedDict):
    messages : Annotated[Sequence[BaseMessage],add_messages]

@tool
def send_command(cmd: str) -> str:
    """Takes a command string, executes it in the PowerShell session, and returns the output"""
    try:
        output = pw.send_command(cmd)
        return output if output else "No output returned from command."
    except Exception as e:
        error_msg = f"Error executing command '{cmd}': {str(e)}"
        return error_msg

tools = [send_command]

endpoint = "https://models.github.ai/inference"
model = "openai/gpt-4.1-mini"

llm = ChatOpenAI(
    openai_api_base=endpoint,
    model_name=model
).bind_tools(tools)

def agent_node(state: AgentState) -> AgentState:
    """Agent Node"""
    system_prompt = SystemMessage(
        """
        You are a terminal agent running on a Windows operating system, equipped with PowerShell session creation and command execution tools. Help the user with the best of your ability.
        - If you are not able to perform anything, automatically retry with an other command until you do it.
        - Strictly use Latest Powershell commands.
        - You are a highly intelligent and fast terminal assistant agent.
        - Often times you are able to perform the action correctly but you are thinking you didn't perform it and you are trying to re-do it. Please be mindful of this and act properly.
        - When asked to create a gitignore file, read the contents of the directory and make a suitable desicion to keep what all files and directories in the git repository. See the file extensions to find out which language is being used.
        """
    )
    try:
        response = llm.invoke([system_prompt] + state["messages"])
        return {"messages": [response] + state["messages"]}
    except Exception as e:
        print(f"Error in agent_node: {e}")
        return {
            "messages": state["messages"] + [AIMessage(content=f"Error processing request: {str(e)}")]
        }

def should_continue(state: AgentState) -> str:
    """Simple decider that only checks for tool calls"""
    messages_dict = state["messages"]
    last_message = messages_dict[-1]
    if not last_message.tool_calls:
        return "end"
    else: 
        return "continue"

graph = StateGraph(AgentState)
tool_node = ToolNode(tools=tools)
graph.add_node("tool_node",tool_node)
graph.add_node("agent_node",agent_node)
graph.add_edge(START,"agent_node")
graph.add_edge("tool_node","agent_node")
graph.add_conditional_edges(
    "agent_node",
    should_continue,
    {
        "continue": "tool_node",
        "end": END,
        "": "tool_node"
    }
)
agent = graph.compile()

conversation_history = []
user_input = input("Command: ")
while user_input != "exit":
    conversation_history.append(HumanMessage(content=user_input))
    inputs = {"messages": conversation_history}
    
    for chunk in agent.stream(inputs, {"recursion_limit": 35}, stream_mode="values"):
        message = chunk["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()
    
    final_result = agent.invoke(inputs)
    conversation_history = final_result["messages"]
    
    user_input = input("Command: ")
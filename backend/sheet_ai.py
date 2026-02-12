# main.py
# FastAPI framework for building the backend API
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # Enables cross-origin requests (for frontend-backend communication)

# MCP client components for communicating with the GDrive MCP server
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
# Utility to dynamically load tools exposed by the MCP server
from langchain_mcp_adapters.tools import load_mcp_tools
# Helper to build a ReAct-style agent from LangGraph
from langgraph.prebuilt import create_react_agent
# LLM interface from LangChain
from langchain_openai import ChatOpenAI
# Python utilities
import asyncio
from contextlib import asynccontextmanager
import os

# Data models for API input/output
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

# Initialize LLM (you'll need to set OPENAI_API_KEY environment variable)
llm = ChatOpenAI(model="gpt-4o")

# === 2. Configure MCP server parameters ===
# This tells the agent how to start the GDrive MCP server (Node.js), with necessary credential paths
server_params = StdioServerParameters(
    command="node",
    args=["/home/ubuntu/gdrive-mcp-server/dist/index.js"],
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        "MCP_GDRIVE_CREDENTIALS": os.environ["MCP_GDRIVE_CREDENTIALS"]
    }
)

# === 3. Create the MCP agent asynchronously ===
async def create_agent():
    # Open a stdio connection to the MCP server
    async with stdio_client(server_params) as (read, write):
        # Wrap the connection in a client session
        async with ClientSession(read, write) as session:
            # Handshake between client and server
            await session.initialize() 

            # Dynamically load the list of tools (e.g., search, summarize)
            tools = await load_mcp_tools(session)

            # Create a LangGraph ReAct agent using the LLM and tools
            agent = create_react_agent(llm, tools)
            
            # OPTIONAL: dry-run test query to check if things work
            agent_response = await agent.ainvoke({"messages": "What is the name of my Drive file about diet"})

            return agent
            # agent_response = await agent.ainvoke({"messages": "What is the name of my Drive file about diet"})
            # return agent_response

# === 4. FastAPI app startup (lifespan) ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    #preload agent at app startup
    global agent2
    agent2 = await create_agent()
    yield

# === 5. Initialize FastAPI app ===
app = FastAPI(title="Chat Assistant API", lifespan=lifespan)

# === 6. Enable CORS (for Vercel frontend to access backend) ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 7. Define Pydantic request/response models ===
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: str


# === 8. Health check route ===

@app.get("/")
async def root():
    return {"message": "Chat Assistant API is running"}

# === 9. Main chat endpoint ===
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Create new MCP connection and session per request (stateless)
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()

                 # Load tools from MCP server
                tools = await load_mcp_tools(session)

                # Create agent with tools and LLM
                agent = create_react_agent(llm, tools)

                # Call the agent with the user's message
                agent_response = await agent.ainvoke({"messages": request.message})
                response_messages = agent_response["messages"]
                # Return the final message content as the agent's reply
                return ChatResponse(
                    response=response_messages[-1].content,
                    session_id=request.session_id,
                    timestamp=datetime.now().isoformat()
                )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
# === 10. Clear session (Not used currently — placeholder for future stateful memory) ===
@app.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    """Clear chat history for a specific session"""
    if session_id in sessions:
        del sessions[session_id]
        return {"message": f"Session {session_id} cleared"}
    return {"message": f"Session {session_id} not found"}
# === 11. List all sessions (also not active yet) ===
@app.get("/sessions")
async def list_sessions():
    """List all active sessions"""
    return {"sessions": list(sessions.keys())}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
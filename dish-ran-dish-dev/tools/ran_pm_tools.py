from utils import constants as CONST
from langchain_mcp_adapters.client import MultiServerMCPClient


MCP_SERVERS = {
    "RAN_PM_query_and_analysis": {
        "url": CONST.RAN_MCP_URL,
        "transport": "sse",
    },
    "RAN_Vendor_tool": {
        "url": CONST.RAN_MCP_VENDOR_URL,
        "transport": "sse",
    }
}

# Create MCP client
mcp_client = MultiServerMCPClient(MCP_SERVERS)


async def get_mcp_tools():
    """
    Asynchronously fetch tools from the configured MCP client.

    Returns:
        List: A list of tool objects retrieved from MCP.
    """
    tools = await mcp_client.get_tools()
    return tools

async def get_mcp_vendor_tools():
    """
    Asynchronously fetch tools from the configured MCP client.

    Returns:
        List: A list of tool objects retrieved from MCP.
    """
    tools = await mcp_client.get_tools(server_name="RAN_Vendor_tool")
    return tools

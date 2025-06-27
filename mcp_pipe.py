"""
This script is used to connect to the MCP server and pipe the input and output to the websocket endpoint.
Version: 0.1.0

Usage:

export MCP_ENDPOINT=<mcp_endpoint>
python mcp_pipe.py <mcp_script>

"""


from config_manager import load_config
import os
import sys
import logging
import argparse

config = load_config()
# 设置 MCP_ENDPOINT 环境变量
# 如果通过命令行传递了MCP_ENDPOINT，则优先使用命令行的值
if "MCP_ENDPOINT" not in os.environ:
    os.environ["MCP_ENDPOINT"] = config["MCP_ENDPOINT"]
    

import asyncio
import websockets
import subprocess
import signal
import random
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mcp_pipe.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('MCP_PIPE')

# Reconnection settings
INITIAL_BACKOFF = 1  # Initial wait time in seconds
MAX_BACKOFF = 600  # Maximum wait time in seconds
reconnect_attempt = 0
backoff = INITIAL_BACKOFF

async def connect_with_retry(uri):
    """Connect to WebSocket server with retry mechanism"""
    global reconnect_attempt, backoff
    while True:  # Infinite reconnection
        try:
            if reconnect_attempt > 0:
                wait_time = backoff * (1 + random.random() * 0.1)  # Add some random jitter
                logger.info(f"Waiting {wait_time:.2f} seconds before reconnection attempt {reconnect_attempt}...")
                await asyncio.sleep(wait_time)
                
            # Attempt to connect
            await connect_to_server(uri)
        
        except Exception as e:
            reconnect_attempt += 1
            logger.warning(f"Connection closed (attempt: {reconnect_attempt}): {e}")            
            # Calculate wait time for next reconnection (exponential backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)

async def connect_to_server(uri):
    """Connect to WebSocket server and establish bidirectional communication with `mcp_script`"""
    global reconnect_attempt, backoff
    try:
        logger.info(f"Connecting to WebSocket server: {uri}")
        async with websockets.connect(uri) as websocket:
            logger.info(f"Successfully connected to WebSocket server")
            
            # Reset reconnection counter if connection closes normally
            reconnect_attempt = 0
            backoff = INITIAL_BACKOFF
            
            # Start mcp_script process
            process = subprocess.Popen(
                ['python', mcp_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',  # Add encoding parameter
                errors='replace'   # Handle decoding errors gracefully
            )
            logger.info(f"Started {mcp_script} process")
            
            # Create two tasks: read from WebSocket and write to process, read from process and write to WebSocket
            await asyncio.gather(
                pipe_websocket_to_process(websocket, process),
                pipe_process_to_websocket(process, websocket),
                pipe_process_stderr_to_terminal(process)
            )
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"WebSocket connection closed: {e}")
        raise  # Re-throw exception to trigger reconnection
    except Exception as e:
        logger.error(f"Connection error: {e}")
        raise  # Re-throw exception
    finally:
        # Ensure the child process is properly terminated
        if 'process' in locals():
            logger.info(f"Terminating {mcp_script} process")
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            logger.info(f"{mcp_script} process terminated")

async def pipe_websocket_to_process(websocket, process):
    """Read data from WebSocket and write to process stdin"""
    try:
        while True:
            # Read message from WebSocket
            message = await websocket.recv()
            logger.debug(f"<< {message[:120]}...")
            
            # Write to process stdin (in text mode)
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            process.stdin.write(message + '\n')
            process.stdin.flush()
    except Exception as e:
        logger.error(f"Error in WebSocket to process pipe: {e}")
        raise  # Re-throw exception to trigger reconnection
    finally:
        # Close process stdin
        if not process.stdin.closed:
            process.stdin.close()

async def pipe_process_to_websocket(process, websocket):
    """Read data from process stdout and send to WebSocket"""
    try:
        while True:
            # Read data from process stdout
            data = await asyncio.get_event_loop().run_in_executor(
                None, process.stdout.readline
            )
            
            if not data:
                logger.info("Process has ended output")
                break
                
            # 新增日志转发功能
            if data.startswith("[GUI_LOG]"):
                await websocket.send(data)
                continue
                
            logger.debug(f">> {data[:120]}...")
            await websocket.send(data)
    except Exception as e:
        logger.error(f"Error in process to WebSocket pipe: {e}")
        raise  # Re-throw exception to trigger reconnection

async def pipe_process_stderr_to_terminal(process):
    """Read data from process stderr and print to terminal"""
    try:
        while True:
            # Read data from process stderr
            data = await asyncio.get_event_loop().run_in_executor(
                None, process.stderr.readline
            )
            
            if not data:  # If no data, the process may have ended
                logger.info("Process has ended stderr output")
                break
                
            # Print stderr data to terminal (in text mode, data is already a string)
            sys.stderr.write(data)
            sys.stderr.flush()
    except Exception as e:
        logger.error(f"Error in process stderr pipe: {e}")
        raise  # Re-throw exception to trigger reconnection

# 新增日志发送函数
def send_log_to_gui(message):
    print(f"[GUI_LOG]{message}")

def signal_handler(sig, frame):
    """Handle interrupt signals"""
    logger.info("Received interrupt signal, shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='MCP Pipe for connecting MCP scripts to WebSocket server')
    parser.add_argument('mcp_script', help='Path to the MCP script to run')
    parser.add_argument('--endpoint', help='MCP WebSocket endpoint URL (overrides env variable)')
    args = parser.parse_args()
    
    # Set MCP script
    mcp_script = args.mcp_script
    
    # Get endpoint URL from arguments or environment
    endpoint_url = args.endpoint or os.environ.get('MCP_ENDPOINT')
    if not endpoint_url:
        logger.error("MCP_ENDPOINT not found. Please set the MCP_ENDPOINT environment variable or use --endpoint")
        sys.exit(1)
    
    logger.info(f"使用MCP端点: {endpoint_url}")
    
    # Start main loop
    try:
        asyncio.run(connect_with_retry(endpoint_url))
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
    except Exception as e:
        logger.error(f"Program execution error: {e}")
        input("按Enter退出...")
        sys.exit(1)

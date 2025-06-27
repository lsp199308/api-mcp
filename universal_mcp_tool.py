from mcp.server.fastmcp import FastMCP
import requests
import json
import logging
import sys
import io
import os
from typing import Dict, Any, List, Optional, Union
from config_manager import load_config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[logging.FileHandler("universal_mcp.log", encoding='utf-8'),
                             logging.StreamHandler()])
logger = logging.getLogger('universal_mcp')

# DO NOT modify sys.stdout/sys.stderr here - let MCP handle it

class UniversalMCPTool:
    def __init__(self):
        self.mcp = FastMCP("universal_mcps")
        self.api_configs = []
        self.config = load_config()
        logger.info(f"配置加载完成，MCP端点: {self.config.get('MCP_ENDPOINT', '未设置')}")
        
        # 设置MCP环境变量
        self._setup_mcp_environment()
        
        self._load_api_configs()
        self._register_apis_as_tools()
    
    def _setup_mcp_environment(self):
        """设置MCP所需的环境变量"""
        # 确保MCP_ENDPOINT环境变量被正确设置
        mcp_endpoint = self.config.get("MCP_ENDPOINT")
        if mcp_endpoint:
            os.environ["MCP_ENDPOINT"] = mcp_endpoint
            logger.info(f"已设置MCP_ENDPOINT环境变量: {mcp_endpoint}")
        else:
            logger.error("未找到MCP_ENDPOINT配置，请先在GUI中配置")
            raise ValueError("MCP_ENDPOINT未配置")
    
    def _load_api_configs(self):
        """Load API configurations from file"""
        try:
            with open('api_configs.json', 'r', encoding='utf-8') as f:
                self.api_configs = json.load(f)
                logger.info(f"Loaded {len(self.api_configs)} API configurations")
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("No API configurations found or invalid format")
            self.api_configs = []
    
    def _save_api_configs(self):
        """Save API configurations to file"""
        with open('api_configs.json', 'w', encoding='utf-8') as f:
            json.dump(self.api_configs, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(self.api_configs)} API configurations")
    
    def add_api(self, api_name: str, api_url: str, method: str, 
                request_format: Dict[str, Any], response_format: Dict[str, Any],
                description: str):
        """Add a new API configuration"""
        api_config = {
            "api_name": api_name,
            "api_url": api_url,
            "method": method.upper(),
            "request_format": request_format,
            "response_format": response_format,
            "description": description
        }
        
        # Check if API with this name already exists
        for i, config in enumerate(self.api_configs):
            if config["api_name"] == api_name:
                # Update existing config
                self.api_configs[i] = api_config
                logger.info(f"Updated API configuration: {api_name}")
                self._save_api_configs()
                return True
        
        # Add new API config
        self.api_configs.append(api_config)
        logger.info(f"Added new API configuration: {api_name}")
        self._save_api_configs()
        return True
    
    def remove_api(self, api_name: str):
        """Remove an API configuration by name"""
        initial_length = len(self.api_configs)
        self.api_configs = [config for config in self.api_configs if config["api_name"] != api_name]
        
        if len(self.api_configs) < initial_length:
            logger.info(f"Removed API configuration: {api_name}")
            self._save_api_configs()
            return True
        else:
            logger.warning(f"API configuration not found: {api_name}")
            return False
    
    def list_apis(self):
        """List all registered API configurations"""
        return self.api_configs
    
    def _register_apis_as_tools(self):
        """Register all APIs as MCP tools"""
        for api_config in self.api_configs:
            self._register_single_api(api_config)
    
    def _register_single_api(self, api_config):
        """Register a single API as an MCP tool"""
        api_name = api_config["api_name"]
        api_url = api_config["api_url"]
        method = api_config["method"]
        request_format = api_config["request_format"]
        description = api_config["description"]
        
        # 获取API密钥相关配置
        api_key = api_config.get("api_key", "")
        key_location = api_config.get("key_location", "header")
        key_name = api_config.get("key_name", "Authorization")
        
        # Create a dynamic function for this API
        def api_caller(**kwargs):
            logger.info(f"Calling API: {api_name}")
            try:
                # 准备请求参数
                params = kwargs.copy()
                headers = {}
                url = api_url
                
                # 如果配置了API密钥，添加到请求中
                if api_key:
                    if key_location == "header":
                        headers[key_name] = f"Bearer {api_key}" if key_name.lower() == "authorization" else api_key
                    elif key_location == "query":
                        # 将密钥添加到URL查询参数
                        if "?" in url:
                            url += f"&{key_name}={api_key}"
                        else:
                            url += f"?{key_name}={api_key}"
                    elif key_location == "body":
                        # 将密钥添加到请求体
                        params[key_name] = api_key
                
                # 发送请求
                if method == "GET":
                    response = requests.get(url, params=params, headers=headers)
                elif method == "POST":
                    response = requests.post(url, json=params, headers=headers)
                else:
                    return {
                        "success": False,
                        "error": f"Unsupported method: {method}"
                    }
                
                response.raise_for_status()
                return {
                    "success": True,
                    "result": response.json()
                }
            except Exception as e:
                logger.error(f"API call error: {str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Set function name and docstring
        api_caller.__name__ = api_name
        api_caller.__doc__ = description
        
        # Register function as a tool
        self.mcp.tool()(api_caller)
        logger.info(f"Registered API as tool: {api_name}")
    
    def reload_apis(self):
        """Reload APIs from configuration file and register them as tools"""
        self._load_api_configs()
        self._register_apis_as_tools()
        return True
    
    def run(self):
        """Run the MCP server"""
        # Register management tools
        @self.mcp.tool()
        def register_api(api_name: str, api_url: str, method: str, 
                      request_format: str, response_format: str,
                      description: str, api_key: str = "", 
                      key_location: str = "header", 
                      key_name: str = "Authorization") -> Dict[str, Any]:
            """
            Register a new API as an MCP tool
            :param api_name: Name of the API (will be the tool name)
            :param api_url: URL of the API endpoint
            :param method: HTTP method (GET or POST)
            :param request_format: JSON string describing request format
            :param response_format: JSON string describing response format
            :param description: Description of the API
            :param api_key: Optional API key for authentication
            :param key_location: Where to put the API key (header, query, body)
            :param key_name: Name of the API key parameter
            :return: Success status
            """
            try:
                req_format = json.loads(request_format)
                resp_format = json.loads(response_format)
                
                # 创建API配置
                api_config = {
                    "api_name": api_name,
                    "api_url": api_url,
                    "method": method,
                    "request_format": req_format,
                    "response_format": resp_format,
                    "description": description
                }
                
                # 如果提供了API密钥，添加到配置中
                if api_key:
                    api_config["api_key"] = api_key
                    api_config["key_location"] = key_location
                    api_config["key_name"] = key_name
                
                # 添加或更新API
                result = True
                for i, config in enumerate(self.api_configs):
                    if config["api_name"] == api_name:
                        self.api_configs[i] = api_config
                        self._save_api_configs()
                        break
                else:
                    self.api_configs.append(api_config)
                    self._save_api_configs()
                
                # Reload APIs to register the new one
                self.reload_apis()
                
                return {
                    "success": True,
                    "message": f"API {api_name} registered successfully"
                }
            except Exception as e:
                logger.error(f"Error registering API: {str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        def list_registered_apis() -> Dict[str, Any]:
            """
            List all registered APIs
            :return: List of registered APIs
            """
            apis = self.list_apis()
            return {
                "success": True,
                "apis": apis
            }
        
        @self.mcp.tool()
        def remove_registered_api(api_name: str) -> Dict[str, Any]:
            """
            Remove a registered API
            :param api_name: Name of the API to remove
            :return: Success status
            """
            result = self.remove_api(api_name)
            # Reload APIs to update registered tools
            self.reload_apis()
            return {
                "success": result,
                "message": f"API {api_name} removed successfully" if result else f"API {api_name} not found"
            }
        
        # Start the MCP server
        logger.info("Starting Universal MCP Tool server")
        logger.info(f"Using MCP_ENDPOINT: {os.environ.get('MCP_ENDPOINT', 'Not set')}")
        try:
            self.mcp.run(transport="stdio")
        except Exception as e:
            logger.error(f"启动MCP服务失败: {str(e)}")
            raise

    def test_api(self, api_name, api_url, method, params):
        import requests
        try:
            if method.lower() == 'get':
                response = requests.get(api_url, params=params)
            elif method.lower() == 'post':
                response = requests.post(api_url, json=params)
            else:
                raise ValueError('Unsupported method: {}'.format(method))

            # Check if the response is valid
            if response.status_code == 200:
                print(f'API {api_name} is available. Response: {response.json()}')
            else:
                print(f'API {api_name} returned an error: {response.status_code} - {response.text}')
        except Exception as e:
            print(f'Failed to test API {api_name}: {str(e)}')

if __name__ == "__main__":
    try:
        logger.info("=== 启动 Universal MCP Tool ===")
        tool = UniversalMCPTool()
        tool.run()
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}", exc_info=True)
        input("按Enter退出...")
        sys.exit(1) 
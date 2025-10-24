from mcp.server.fastmcp import FastMCP
import requests
import json
import logging
import sys
import os
from typing import Dict, Any
from config_manager import load_config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[logging.FileHandler("universal_mcp.log", encoding='utf-8'),
                             logging.StreamHandler()])
logger = logging.getLogger('universal_mcp')


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
        mcp_endpoint = self.config.get("MCP_ENDPOINT")
        if mcp_endpoint:
            os.environ["MCP_ENDPOINT"] = mcp_endpoint
            logger.info(f"已设置MCP_ENDPOINT环境变量: {mcp_endpoint}")
        else:
            logger.error("未找到MCP_ENDPOINT配置，请先在GUI中配置")
            raise ValueError("MCP_ENDPOINT未配置")

    def _load_api_configs(self):
        """加载 API 配置"""
        try:
            with open('api_configs.json', 'r', encoding='utf-8') as f:
                self.api_configs = json.load(f)
                logger.info(f"Loaded {len(self.api_configs)} API configurations")
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("No API configurations found or invalid format")
            self.api_configs = []

    def _save_api_configs(self):
        """保存 API 配置"""
        with open('api_configs.json', 'w', encoding='utf-8') as f:
            json.dump(self.api_configs, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(self.api_configs)} API configurations")

    def add_api(self, api_name: str, api_url: str, method: str,
                request_format: Dict[str, Any], response_format: Dict[str, Any],
                description: str):
        """新增 API 配置"""
        api_config = {
            "api_name": api_name,
            "api_url": api_url,
            "method": method.upper(),
            "request_format": request_format,
            "response_format": response_format,
            "description": description
        }

        for i, config in enumerate(self.api_configs):
            if config["api_name"] == api_name:
                self.api_configs[i] = api_config
                self._save_api_configs()
                logger.info(f"Updated API configuration: {api_name}")
                return True

        self.api_configs.append(api_config)
        self._save_api_configs()
        logger.info(f"Added new API configuration: {api_name}")
        return True

    def remove_api(self, api_name: str):
        """删除 API 配置"""
        initial_length = len(self.api_configs)
        self.api_configs = [c for c in self.api_configs if c["api_name"] != api_name]
        if len(self.api_configs) < initial_length:
            self._save_api_configs()
            logger.info(f"Removed API configuration: {api_name}")
            return True
        logger.warning(f"API configuration not found: {api_name}")
        return False

    def list_apis(self):
        """列出所有 API"""
        return self.api_configs

    def _register_apis_as_tools(self):
        """注册所有 API 为 MCP 工具"""
        for api_config in self.api_configs:
            self._register_single_api(api_config)

    def _register_single_api(self, api_config):
        """注册单个 API"""
        api_name = api_config["api_name"]
        api_url = api_config["api_url"]
        method = api_config["method"]
        request_format = api_config.get("request_format", {})
        description = api_config.get("description", "")

        # API 密钥配置
        api_key = api_config.get("api_key", "")
        key_location = api_config.get("key_location", "header")
        key_name = api_config.get("key_name", "Authorization")

        def api_caller(**kwargs):
            logger.info(f"Calling API: {api_name}")
            try:
                # 自动识别 request_format 第一个字段名作为主参数名
                if isinstance(request_format, dict) and len(request_format) > 0:
                    main_param = list(request_format.keys())[0]
                else:
                    main_param = "value"  # fallback

                # 处理 {"kwargs": "北京"} 或 {"kwargs": {...}}
                if "kwargs" in kwargs:
                    if isinstance(kwargs["kwargs"], str):
                        params = {main_param: kwargs["kwargs"]}
                    elif isinstance(kwargs["kwargs"], dict):
                        params = kwargs["kwargs"]
                    else:
                        return {"success": False, "error": f"Unsupported kwargs type: {type(kwargs['kwargs']).__name__}"}
                else:
                    params = kwargs.copy()

                headers = {}
                url = api_url

                # 如果有 API key，自动放置
                if api_key:
                    if key_location == "header":
                        headers[key_name] = f"Bearer {api_key}" if key_name.lower() == "authorization" else api_key
                    elif key_location == "query":
                        url += f"?{key_name}={api_key}" if "?" not in url else f"&{key_name}={api_key}"
                    elif key_location == "body":
                        params[key_name] = api_key

                # 发送请求
                if method == "GET":
                    response = requests.get(url, params=params, headers=headers)
                elif method == "POST":
                    response = requests.post(url, json=params, headers=headers)
                else:
                    return {"success": False, "error": f"Unsupported method: {method}"}

                response.raise_for_status()
                return {"success": True, "result": response.json()}

            except Exception as e:
                logger.error(f"API call error: {str(e)}", exc_info=True)
                return {"success": False, "error": str(e)}

        api_caller.__name__ = api_name
        api_caller.__doc__ = description

        # 注册为 MCP 工具
        self.mcp.tool()(api_caller)
        logger.info(f"Registered API as tool: {api_name}")

    def reload_apis(self):
        """重新加载 API"""
        self._load_api_configs()
        self._register_apis_as_tools()
        return True

    def run(self):
        """启动 MCP 服务"""

        @self.mcp.tool()
        def register_api(api_name: str, api_url: str, method: str,
                      request_format: str, response_format: str,
                      description: str, api_key: str = "",
                      key_location: str = "header",
                      key_name: str = "Authorization") -> Dict[str, Any]:
            """注册一个新的 API 工具"""
            try:
                req_format = json.loads(request_format)
                resp_format = json.loads(response_format)
                api_config = {
                    "api_name": api_name,
                    "api_url": api_url,
                    "method": method,
                    "request_format": req_format,
                    "response_format": resp_format,
                    "description": description
                }

                if api_key:
                    api_config["api_key"] = api_key
                    api_config["key_location"] = key_location
                    api_config["key_name"] = key_name

                for i, cfg in enumerate(self.api_configs):
                    if cfg["api_name"] == api_name:
                        self.api_configs[i] = api_config
                        break
                else:
                    self.api_configs.append(api_config)

                self._save_api_configs()
                self.reload_apis()

                return {"success": True, "message": f"API {api_name} registered successfully"}
            except Exception as e:
                logger.error(f"Error registering API: {str(e)}")
                return {"success": False, "error": str(e)}

        @self.mcp.tool()
        def list_registered_apis() -> Dict[str, Any]:
            """列出注册的 APIs"""
            return {"success": True, "apis": self.list_apis()}

        @self.mcp.tool()
        def remove_registered_api(api_name: str) -> Dict[str, Any]:
            """移除已注册 API"""
            result = self.remove_api(api_name)
            self.reload_apis()
            return {
                "success": result,
                "message": f"API {api_name} removed successfully" if result else f"API {api_name} not found"
            }

        logger.info("Starting Universal MCP Tool server")
        logger.info(f"Using MCP_ENDPOINT: {os.environ.get('MCP_ENDPOINT', 'Not set')}")

        try:
            self.mcp.run(transport="stdio")
        except Exception as e:
            logger.error(f"启动 MCP 服务失败: {str(e)}")
            raise

    def test_api(self, api_name, api_url, method, params):
        """测试 API 是否可用"""
        try:
            if method.lower() == 'get':
                response = requests.get(api_url, params=params)
            elif method.lower() == 'post':
                response = requests.post(api_url, json=params)
            else:
                raise ValueError(f'Unsupported method: {method}')

            if response.status_code == 200:
                print(f'API {api_name} 正常，响应: {response.json()}')
            else:
                print(f'API {api_name} 错误: {response.status_code} - {response.text}')
        except Exception as e:
            print(f'Failed to test API {api_name}: {str(e)}')


if __name__ == "__main__":
    try:
        logger.info("=== 启动 Universal MCP Tool ===")
        tool = UniversalMCPTool()
        tool.run()
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}", exc_info=True)
        input("按 Enter 退出...")
        sys.exit(1)

from mcp.server.fastmcp import FastMCP
import requests
import json
import logging
import sys
import os
from typing import Dict, Any
from config_manager import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("universal_mcp.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('universal_mcp')


class UniversalMCPTool:
    def __init__(self):
        self.mcp = FastMCP("universal_mcps")
        self.api_configs = []
        self.config = load_config()
        logger.info(f"配置加载完成，MCP端点: {self.config.get('MCP_ENDPOINT', '未设置')}")

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
                logger.info(f"加载 {len(self.api_configs)} 个 API 配置")
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("未找到有效的 api_configs.json 文件")
            self.api_configs = []

    def _save_api_configs(self):
        """保存 API 配置"""
        with open('api_configs.json', 'w', encoding='utf-8') as f:
            json.dump(self.api_configs, f, indent=2, ensure_ascii=False)
        logger.info(f"已保存 {len(self.api_configs)} 个 API 配置")

    def add_api(self, api_name: str, api_url: str, method: str,
                request_format: Dict[str, Any], response_format: Dict[str, Any],
                description: str):
        """添加新 API 配置"""
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
                logger.info(f"更新 API 配置: {api_name}")
                self._save_api_configs()
                return True

        self.api_configs.append(api_config)
        logger.info(f"新增 API 配置: {api_name}")
        self._save_api_configs()
        return True

    def remove_api(self, api_name: str):
        """删除 API"""
        initial_length = len(self.api_configs)
        self.api_configs = [cfg for cfg in self.api_configs if cfg["api_name"] != api_name]
        if len(self.api_configs) < initial_length:
            logger.info(f"已删除 API 配置: {api_name}")
            self._save_api_configs()
            return True
        logger.warning(f"未找到 API: {api_name}")
        return False

    def list_apis(self):
        """列出所有 API"""
        return self.api_configs

    def _register_apis_as_tools(self):
        """注册所有 API 为 MCP 工具"""
        for cfg in self.api_configs:
            self._register_single_api(cfg)

    def _register_single_api(self, api_config):
        """注册单个 API，支持多参数自动映射与超长截断"""
        api_name = api_config["api_name"]
        api_url = api_config["api_url"]
        method = api_config["method"].upper()
        request_format = api_config.get("request_format", {})
        description = api_config.get("description", "")

        api_key = api_config.get("api_key", "")
        key_location = api_config.get("key_location", "header")
        key_name = api_config.get("key_name", "Authorization")

        def api_caller(**kwargs):
            logger.info(f"调用 API: {api_name}")
            try:
                fields = list(request_format.keys())
                params = {}
                extra = []

                if "kwargs" in kwargs:
                    value = kwargs["kwargs"]
                    if isinstance(value, str):
                        parts = value.strip().split()
                        for i, field in enumerate(fields):
                            if i < len(parts):
                                params[field] = parts[i]
                            else:
                                params[field] = request_format.get(field, "")
                        if len(parts) > len(fields):
                            extra = parts[len(fields):]
                    elif isinstance(value, dict):
                        params.update(value)
                    else:
                        return {"success": False, "error": f"Unsupported kwargs type: {type(value).__name__}"}

                # 补全剩余字段
                for field in fields:
                    if field not in params:
                        params[field] = request_format.get(field, "")

                if extra:
                    logger.info(f"额外参数被忽略: {extra}")

                headers = {}
                url = api_url

                # 处理 API Key
                if api_key:
                    if key_location == "header":
                        headers[key_name] = f"Bearer {api_key}" if key_name.lower() == "authorization" else api_key
                    elif key_location == "query":
                        url += f"?{key_name}={api_key}" if "?" not in url else f"&{key_name}={api_key}"
                    elif key_location == "body":
                        params[key_name] = api_key

                logger.info(f"请求 URL: {url}")
                logger.info(f"请求参数: {params}")
                logger.info(f"请求头: {headers}")

                # 执行请求
                if method == "GET":
                    response = requests.get(url, params=params, headers=headers)
                elif method == "POST":
                    response = requests.post(url, json=params, headers=headers)
                else:
                    return {"success": False, "error": f"Unsupported method: {method}"}

                response.raise_for_status()
                result = response.json()
                logger.info(f"响应结果: {result}")
                return {"success": True, "result": result}

            except Exception as e:
                logger.error(f"API 调用错误: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        api_caller.__name__ = api_name
        api_caller.__doc__ = description
        self.mcp.tool()(api_caller)
        logger.info(f"✅ 已注册 API 工具: {api_name}")

    def reload_apis(self):
        """重新加载并注册所有 API"""
        self._load_api_configs()
        self._register_apis_as_tools()
        return True

    def run(self):
        """运行 MCP 服务"""
        @self.mcp.tool()
        def register_api(api_name: str, api_url: str, method: str,
                         request_format: str, response_format: str,
                         description: str, api_key: str = "",
                         key_location: str = "header",
                         key_name: str = "Authorization") -> Dict[str, Any]:
            """注册新 API"""
            try:
                req_fmt = json.loads(request_format)
                resp_fmt = json.loads(response_format)
                api_cfg = {
                    "api_name": api_name,
                    "api_url": api_url,
                    "method": method.upper(),
                    "request_format": req_fmt,
                    "response_format": resp_fmt,
                    "description": description
                }
                if api_key:
                    api_cfg.update({
                        "api_key": api_key,
                        "key_location": key_location,
                        "key_name": key_name
                    })
                for i, cfg in enumerate(self.api_configs):
                    if cfg["api_name"] == api_name:
                        self.api_configs[i] = api_cfg
                        break
                else:
                    self.api_configs.append(api_cfg)
                self._save_api_configs()
                self.reload_apis()
                return {"success": True, "message": f"API {api_name} 注册成功"}
            except Exception as e:
                logger.error(f"注册 API 失败: {e}")
                return {"success": False, "error": str(e)}

        @self.mcp.tool()
        def list_registered_apis() -> Dict[str, Any]:
            """列出所有注册的 API"""
            return {"success": True, "apis": self.list_apis()}

        @self.mcp.tool()
        def remove_registered_api(api_name: str) -> Dict[str, Any]:
            """移除已注册的 API"""
            result = self.remove_api(api_name)
            self.reload_apis()
            return {"success": result, "message": f"API {api_name} 已移除" if result else "未找到该 API"}

        logger.info("🚀 启动 Universal MCP Tool 服务中...")
        try:
            self.mcp.run(transport="stdio")
        except Exception as e:
            logger.error(f"MCP 启动失败: {e}", exc_info=True)
            raise

    def test_api(self, api_name, api_url, method, params):
        """测试 API 可用性"""
        try:
            if method.lower() == 'get':
                r = requests.get(api_url, params=params)
            elif method.lower() == 'post':
                r = requests.post(api_url, json=params)
            else:
                raise ValueError("Unsupported method")
            if r.status_code == 200:
                print(f"✅ {api_name} 响应: {r.json()}")
            else:
                print(f"⚠️ {api_name} 返回错误: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"❌ 测试 {api_name} 失败: {e}")


if __name__ == "__main__":
    try:
        logger.info("=== 启动 Universal MCP Tool ===")
        tool = UniversalMCPTool()
        tool.run()
    except Exception as e:
        logger.error(f"程序运行出错: {e}", exc_info=True)
        input("按 Enter 退出...")
        sys.exit(1)



# Universal MCP Tool

一个万能的MCP工具，能够将Web API接口轻松转化为MCP工具，供AI助手使用。

## 功能特点

- 通过简单配置，快速将API转化为MCP工具
- 支持GET和POST请求方法
- 可视化界面，操作简便
- 支持动态添加、删除和修改API配置
- 实时查看和编辑API描述和参数格式
- **API测试功能**，确保API可用性，提前验证请求和响应
- **API密钥管理**，支持多种密钥认证方式，AI助手可自动使用密钥调用API

## 安装要求

```
python 3.13
requests>=2.31.0
beautifulsoup4>=4.12.3
websockets>=12.0
python-dotenv>=1.0.0
fastmcp>=0.1.0
```

## 快速开始

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 启动应用

```bash
python 启动_universal_mcp.py
```

## 使用指南

### 基本配置

1. 在"基本配置"选项卡中设置MCP端点
2. 点击"保存配置"按钮保存设置

### API管理

1. 在"API管理"选项卡中，您可以添加、删除和修改API配置
2. 添加API时，需要提供以下信息：
   - API名称：将会成为MCP工具的名称
   - API URL：API的完整URL地址
   - 请求方法：GET或POST
   - API描述：对API功能的简短描述
   - API密钥：需要授权的API可以设置密钥
   - 密钥位置：header、query或body，指定密钥放在哪里
   - 密钥参数名：密钥的参数名称，如"Authorization"、"api_key"等
   - 请求参数格式：JSON格式的请求参数描述
   - 返回参数格式：JSON格式的返回参数描述

3. 添加完成后，点击"保存API"按钮

### API密钥管理

1. 对于需要密钥的API，可在添加时直接填写"API密钥"字段
2. 可选择密钥位置：
   - header：在HTTP请求头中添加密钥（如Authorization头）
   - query：在URL查询参数中添加密钥（如?api_key=xxx）
   - body：在请求体中添加密钥（适用于POST请求）
3. 密钥参数名根据API要求填写，例如"Authorization"、"api_key"、"token"等
4. 系统会自动处理密钥的添加，AI助手无需知道密钥即可调用API

### API测试

1. 选择已添加的API，点击"测试API"按钮
2. 在弹出的测试窗口中，填写API请求参数
3. 点击"发送请求"按钮测试API
4. 查看API响应结果和格式验证
   - 系统会自动验证响应是否符合预期格式
   - 如果有缺少的字段，会显示警告信息

### 启动服务

1. 在"日志"选项卡中，点击"启动服务"按钮启动MCP服务
2. 服务启动后，将在后台运行，可以与AI助手集成使用

## API配置示例

### 天气查询API

```json
{
  "api_name": "查询天气",
  "api_url": "https://api.example.com/weather",
  "method": "GET",
  "request_format": {
    "city": "string",
    "days": "number"
  },
  "response_format": {
    "temperature": "number",
    "weather": "string",
    "humidity": "number"
  },
  "description": "根据城市名称查询天气预报"
}
```

### 需要API密钥的翻译API

```json
{
  "api_name": "翻译文本",
  "api_url": "https://api.example.com/translate",
  "method": "POST",
  "api_key": "your-api-key-here",
  "key_location": "header",
  "key_name": "Authorization",
  "request_format": {
    "text": "string",
    "source": "string",
    "target": "string"
  },
  "response_format": {
    "translated": "string",
    "status": "number"
  },
  "description": "将文本从源语言翻译到目标语言"
}
```

## 高级使用

1. 直接注册API：MCP服务本身提供了`register_api`工具，可以通过AI助手直接调用注册新API
2. 查看已注册API：可以通过`list_registered_apis`工具查看所有已注册的API
3. 删除注册的API：可以通过`remove_registered_api`工具删除指定的API
4. 带密钥API调用：AI助手可以直接调用带密钥的API，无需知道密钥内容

## 注意事项

1. API配置保存在`api_configs.json`文件中
2. 基本配置保存在`~/.xiaozhi_mcp_config.json`文件中
3. 确保您使用的API端点允许跨域请求
4. 测试API功能中的参数类型会自动转换，例如数字类型、布尔类型等
5. API密钥会被保存在配置文件中，请确保配置文件的安全性 

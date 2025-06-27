import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import subprocess
import os
import sys
import tempfile
import requests
from config_manager import load_config, save_config

class APITestDialog:
    """API测试对话框"""
    def __init__(self, parent, api_config):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"测试API - {api_config['api_name']}")
        self.dialog.geometry("700x600")
        self.dialog.grab_set()  # 使对话框模态
        
        self.api_config = api_config
        self.params = {}
        
        self.create_widgets()
    
    def create_widgets(self):
        # 顶部信息框
        info_frame = ttk.LabelFrame(self.dialog, text="API信息")
        info_frame.pack(fill="x", padx=10, pady=10)
        
        # API基本信息
        ttk.Label(info_frame, text=f"名称: {self.api_config['api_name']}").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, text=f"URL: {self.api_config['api_url']}").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, text=f"方法: {self.api_config['method']}").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, text=f"描述: {self.api_config.get('description', '')}").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        
        # 显示API密钥（如果有）
        if self.api_config.get('api_key'):
            ttk.Label(info_frame, text=f"API密钥: {'*'*len(self.api_config['api_key'])}").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        
        # 参数输入框
        params_frame = ttk.LabelFrame(self.dialog, text="请求参数")
        params_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 创建参数输入字段
        self.param_entries = {}
        row = 0
        for param_name, param_type in self.api_config['request_format'].items():
            ttk.Label(params_frame, text=f"{param_name} ({param_type}):").grid(row=row, column=0, sticky="w", padx=5, pady=5)
            entry = ttk.Entry(params_frame, width=40)
            entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
            self.param_entries[param_name] = entry
            row += 1
        
        params_frame.columnconfigure(1, weight=1)
        
        # 如果没有参数，显示提示
        if not self.api_config['request_format']:
            ttk.Label(params_frame, text="此API没有定义请求参数").grid(row=0, column=0, columnspan=2, padx=5, pady=20)
        
        # 测试按钮
        ttk.Button(params_frame, text="发送请求", command=self.test_api).grid(row=row, column=1, sticky="e", padx=5, pady=10)
        
        # 响应结果
        response_frame = ttk.LabelFrame(self.dialog, text="响应结果")
        response_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.response_text = scrolledtext.ScrolledText(response_frame, wrap=tk.WORD, height=10)
        self.response_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 底部按钮
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(btn_frame, text="关闭", command=self.dialog.destroy).pack(side="right", padx=5)
    
    def test_api(self):
        """测试API"""
        # 收集参数
        params = {}
        for param_name, entry in self.param_entries.items():
            value = entry.get().strip()
            if not value and param_name in self.api_config['request_format']:
                # 如果参数为空，判断类型后给一个默认值
                param_type = self.api_config['request_format'][param_name]
                if param_type == "string":
                    value = ""
                elif param_type == "number":
                    value = 0
                elif param_type == "boolean":
                    value = False
                elif param_type == "object":
                    value = {}
                elif param_type == "array":
                    value = []
                else:
                    value = None
            
            # 尝试转换数据类型
            try:
                param_type = self.api_config['request_format'][param_name]
                if param_type == "number":
                    if value:  # 检查值不为空
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                elif param_type == "boolean":
                    if isinstance(value, str):
                        value = value.lower() in ('true', 'yes', '1', 'y')
                elif param_type in ("object", "array"):
                    if value and isinstance(value, str):  # 如果不为空才解析JSON
                        value = json.loads(value)
            except (ValueError, json.JSONDecodeError) as e:
                self.response_text.delete(1.0, tk.END)
                self.response_text.insert(tk.END, f"参数错误: {param_name} - {str(e)}")
                return
            
            params[param_name] = value
        
        # 清空之前的响应
        self.response_text.delete(1.0, tk.END)
        self.response_text.insert(tk.END, "正在发送请求...\n\n")
        self.dialog.update()
        
        # 发送请求
        try:
            method = self.api_config['method']
            url = self.api_config['api_url']
            
            # 检查API密钥
            api_key = self.api_config.get('api_key', '')
            headers = {}
            
            # 如果有API密钥，尝试解析密钥设置方法
            if api_key:
                key_location = self.api_config.get('key_location', 'header')
                key_name = self.api_config.get('key_name', 'Authorization')
                
                if key_location == 'header':
                    headers[key_name] = f"Bearer {api_key}" if key_name.lower() == 'authorization' else api_key
                elif key_location == 'query':
                    if '?' in url:
                        url += f"&{key_name}={api_key}"
                    else:
                        url += f"?{key_name}={api_key}"
                elif key_location == 'body':
                    params[key_name] = api_key
            
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=10)
            else:  # POST
                response = requests.post(url, json=params, headers=headers, timeout=10)
            
            # 显示响应状态
            status_text = f"Status Code: {response.status_code} ({response.reason})\n"
            status_text += f"Time: {response.elapsed.total_seconds():.2f}s\n\n"
            
            # 尝试解析响应为JSON
            try:
                json_response = response.json()
                formatted_json = json.dumps(json_response, ensure_ascii=False, indent=2)
                result_text = status_text + formatted_json
            except json.JSONDecodeError:
                # 非JSON响应
                result_text = status_text + response.text[:2000]
                if len(response.text) > 2000:
                    result_text += "\n\n... (响应内容过长，已截断) ..."
            
            # 更新响应文本
            self.response_text.delete(1.0, tk.END)
            self.response_text.insert(tk.END, result_text)
            
            # 检查响应是否符合预期格式
            self._validate_response(response)
            
        except requests.RequestException as e:
            self.response_text.delete(1.0, tk.END)
            self.response_text.insert(tk.END, f"请求错误: {str(e)}")
    
    def _validate_response(self, response):
        """验证响应是否符合预期格式"""
        try:
            json_response = response.json()
            expected_format = self.api_config['response_format']
            
            # 检查响应格式
            missing_fields = []
            for field, expected_type in expected_format.items():
                if field not in json_response:
                    missing_fields.append(field)
                else:
                    # 可以进一步检查类型，但先简单检查字段存在性
                    pass
            
            # 如果有缺少的字段，显示警告
            if missing_fields:
                self.response_text.insert(tk.END, "\n\n⚠️ 警告：响应缺少以下预期字段：\n")
                for field in missing_fields:
                    self.response_text.insert(tk.END, f"- {field}\n")
            
        except (ValueError, json.JSONDecodeError, AttributeError):
            self.response_text.insert(tk.END, "\n\n⚠️ 警告：响应不是有效的JSON格式，无法验证")

class UniversalMCPGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Universal MCP Tool")
        self.root.geometry("800x600")
        
        self.config = load_config()
        self.api_configs = self.load_api_configs()
        
        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def load_api_configs(self):
        """Load API configurations from file"""
        try:
            with open('api_configs.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
            
    def save_api_configs(self):
        """Save API configurations to file"""
        with open('api_configs.json', 'w', encoding='utf-8') as f:
            json.dump(self.api_configs, f, indent=2, ensure_ascii=False)
    
    def create_widgets(self):
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Create tabs
        self.create_config_tab()
        self.create_api_manager_tab()
        self.create_log_tab()
    
    def create_config_tab(self):
        # Create config tab
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="基本配置")
        
        # MCP端点
        ttk.Label(config_frame, text="MCP端点:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.mcp_entry = ttk.Entry(config_frame, width=50)
        self.mcp_entry.insert(0, self.config.get("MCP_ENDPOINT", ""))
        self.mcp_entry.grid(row=0, column=1, padx=10, pady=10)
        
        
        # 保存按钮
        ttk.Button(config_frame, text="保存配置", command=self.save_base_config).grid(
            row=2, column=1, sticky="e", padx=10, pady=20)
    
    def create_api_manager_tab(self):
        # Create API manager tab
        api_frame = ttk.Frame(self.notebook)
        self.notebook.add(api_frame, text="API管理")
        
        # Left side - API List
        left_frame = ttk.LabelFrame(api_frame, text="已注册API")
        left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        # Create treeview for API list
        self.api_tree = ttk.Treeview(left_frame, columns=("name", "method", "url"), show="headings")
        self.api_tree.heading("name", text="API名称")
        self.api_tree.heading("method", text="方法")
        self.api_tree.heading("url", text="URL")
        self.api_tree.column("name", width=100)
        self.api_tree.column("method", width=50)
        self.api_tree.column("url", width=200)
        self.api_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Populate API list
        self.refresh_api_list()
        
        # Add buttons for API management
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text="刷新", command=self.refresh_api_list).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="删除", command=self.delete_api).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="查看详情", command=self.view_api_details).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="测试API", command=self.test_api).pack(side="left", padx=5)
        
        # Right side - Add New API
        right_frame = ttk.LabelFrame(api_frame, text="添加/修改API")
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        # API name
        ttk.Label(right_frame, text="API名称:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.api_name_entry = ttk.Entry(right_frame, width=30)
        self.api_name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # API URL
        ttk.Label(right_frame, text="API URL:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.api_url_entry = ttk.Entry(right_frame, width=30)
        self.api_url_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        # API method
        ttk.Label(right_frame, text="请求方法:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.api_method_combobox = ttk.Combobox(right_frame, values=["GET", "POST"], state="readonly")
        self.api_method_combobox.current(1)  # Default to POST
        self.api_method_combobox.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        # API description
        ttk.Label(right_frame, text="API描述:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.api_description_entry = ttk.Entry(right_frame, width=30)
        self.api_description_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        
        # API key (新增)
        ttk.Label(right_frame, text="API密钥:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.api_key_entry = ttk.Entry(right_frame, width=30, show="*")
        self.api_key_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        
        # Key location (新增)
        ttk.Label(right_frame, text="密钥位置:").grid(row=5, column=0, sticky="w", padx=5, pady=5)
        self.key_location_combobox = ttk.Combobox(right_frame, values=["header", "query", "body"], state="readonly")
        self.key_location_combobox.current(0)  # Default to header
        self.key_location_combobox.grid(row=5, column=1, padx=5, pady=5, sticky="ew")
        
        # Key name (新增)
        ttk.Label(right_frame, text="密钥参数名:").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        self.key_name_entry = ttk.Entry(right_frame, width=30)
        self.key_name_entry.insert(0, "Authorization")
        self.key_name_entry.grid(row=6, column=1, padx=5, pady=5, sticky="ew")
        
        # Request format
        ttk.Label(right_frame, text="请求参数格式(JSON):").grid(row=7, column=0, sticky="w", padx=5, pady=5)
        self.request_format_text = scrolledtext.ScrolledText(right_frame, width=30, height=5, wrap=tk.WORD)
        self.request_format_text.grid(row=7, column=1, padx=5, pady=5, sticky="ew")
        self.request_format_text.insert(tk.END, '{\n  "param1": "string",\n  "param2": "number"\n}')
        
        # Response format
        ttk.Label(right_frame, text="返回参数格式(JSON):").grid(row=8, column=0, sticky="w", padx=5, pady=5)
        self.response_format_text = scrolledtext.ScrolledText(right_frame, width=30, height=5, wrap=tk.WORD)
        self.response_format_text.grid(row=8, column=1, padx=5, pady=5, sticky="ew")
        self.response_format_text.insert(tk.END, '{\n  "result": "string",\n  "status": "number"\n}')
        
        # Save button
        ttk.Button(right_frame, text="保存API", command=self.save_api).grid(
            row=9, column=1, sticky="e", padx=5, pady=10)
        
        # Configure grid to be resizable
        right_frame.columnconfigure(1, weight=1)
    
    def create_log_tab(self):
        # Create log tab
        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text="日志")
        
        # Log area
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.configure(state='disabled')
        
        # Control buttons
        control_frame = ttk.Frame(log_frame)
        control_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(control_frame, text="启动服务", command=self.start_service).pack(side="left", padx=5)
        ttk.Button(control_frame, text="清空日志", command=self.clear_log).pack(side="left", padx=5)
    
    def test_api(self):
        """测试选中的API"""
        selected = self.api_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请选择要测试的API")
            return
        
        # 获取API名称
        api_name = self.api_tree.item(selected[0])["values"][0]
        
        # 查找API配置
        api_config = None
        for config in self.api_configs:
            if config["api_name"] == api_name:
                api_config = config
                break
        
        if not api_config:
            messagebox.showerror("错误", f"找不到API '{api_name}' 的配置")
            return
        
        # 打开测试对话框
        test_dialog = APITestDialog(self.root, api_config)
    
    def refresh_api_list(self):
        # Clear existing items
        for item in self.api_tree.get_children():
            self.api_tree.delete(item)
        
        # Reload API configs
        self.api_configs = self.load_api_configs()
        
        # Add APIs to treeview
        for api in self.api_configs:
            has_key = "✓" if api.get('api_key') else ""
            self.api_tree.insert("", "end", values=(
                api["api_name"], 
                api["method"], 
                api["api_url"]
            ))
    
    def save_base_config(self):
        """Save MCP endpoint and API key"""
        self.log("正在保存基本配置...")
        new_config = {
            "MCP_ENDPOINT": self.mcp_entry.get(),
            "ZHIPU_API_KEY": self.api_entry.get()
        }
        save_config(new_config)
        self.config = new_config
        messagebox.showinfo("保存成功", "基本配置已保存！")
        self.log("基本配置保存成功")
    
    def save_api(self):
        """Save API configuration"""
        try:
            api_name = self.api_name_entry.get()
            if not api_name:
                messagebox.showerror("输入错误", "API名称不能为空")
                return
            
            api_url = self.api_url_entry.get()
            if not api_url:
                messagebox.showerror("输入错误", "API URL不能为空")
                return
            
            method = self.api_method_combobox.get()
            description = self.api_description_entry.get()
            
            # Get API key information
            api_key = self.api_key_entry.get()
            key_location = self.key_location_combobox.get()
            key_name = self.key_name_entry.get()
            
            # Parse JSON formats
            try:
                request_format = json.loads(self.request_format_text.get("1.0", tk.END))
                response_format = json.loads(self.response_format_text.get("1.0", tk.END))
            except json.JSONDecodeError as e:
                messagebox.showerror("格式错误", f"JSON格式错误: {str(e)}")
                return
            
            # Create API config
            api_config = {
                "api_name": api_name,
                "api_url": api_url,
                "method": method,
                "request_format": request_format,
                "response_format": response_format,
                "description": description
            }
            
            # 添加API密钥相关配置（如果有）
            if api_key:
                api_config["api_key"] = api_key
                api_config["key_location"] = key_location
                api_config["key_name"] = key_name
            
            # Check if API with this name already exists
            for i, config in enumerate(self.api_configs):
                if config["api_name"] == api_name:
                    # Update existing config
                    self.api_configs[i] = api_config
                    self.save_api_configs()
                    self.log(f"更新API配置: {api_name}")
                    self.refresh_api_list()
                    messagebox.showinfo("保存成功", f"API '{api_name}' 已更新")
                    return
            
            # Add new API config
            self.api_configs.append(api_config)
            self.save_api_configs()
            self.log(f"添加新API配置: {api_name}")
            self.refresh_api_list()
            messagebox.showinfo("保存成功", f"API '{api_name}' 已添加")
        
        except Exception as e:
            self.log(f"保存API配置出错: {str(e)}")
            messagebox.showerror("错误", str(e))
    
    def delete_api(self):
        """Delete selected API"""
        selected = self.api_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请选择要删除的API")
            return
        
        # Get API name from treeview
        api_name = self.api_tree.item(selected[0])["values"][0]
        
        # Confirm deletion
        if messagebox.askyesno("确认删除", f"确定要删除API '{api_name}' 吗?"):
            # Remove API from config
            self.api_configs = [config for config in self.api_configs if config["api_name"] != api_name]
            self.save_api_configs()
            self.log(f"删除API配置: {api_name}")
            self.refresh_api_list()
    
    def view_api_details(self):
        """View and edit details of selected API"""
        selected = self.api_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请选择要查看的API")
            return
        
        # Get API name from treeview
        api_name = self.api_tree.item(selected[0])["values"][0]
        
        # Find API config
        api_config = None
        for config in self.api_configs:
            if config["api_name"] == api_name:
                api_config = config
                break
        
        if not api_config:
            messagebox.showerror("错误", f"找不到API '{api_name}' 的配置")
            return
        
        # Populate form with API details
        self.api_name_entry.delete(0, tk.END)
        self.api_name_entry.insert(0, api_config["api_name"])
        
        self.api_url_entry.delete(0, tk.END)
        self.api_url_entry.insert(0, api_config["api_url"])
        
        self.api_method_combobox.set(api_config["method"])
        
        self.api_description_entry.delete(0, tk.END)
        self.api_description_entry.insert(0, api_config.get("description", ""))
        
        # 更新API密钥相关字段
        self.api_key_entry.delete(0, tk.END)
        if "api_key" in api_config:
            self.api_key_entry.insert(0, api_config["api_key"])
        
        # 更新密钥位置
        if "key_location" in api_config:
            self.key_location_combobox.set(api_config["key_location"])
        else:
            self.key_location_combobox.current(0)  # 默认header
        
        # 更新密钥参数名
        self.key_name_entry.delete(0, tk.END)
        if "key_name" in api_config:
            self.key_name_entry.insert(0, api_config["key_name"])
        else:
            self.key_name_entry.insert(0, "Authorization")
        
        self.request_format_text.delete("1.0", tk.END)
        self.request_format_text.insert("1.0", json.dumps(api_config["request_format"], indent=2))
        
        self.response_format_text.delete("1.0", tk.END)
        self.response_format_text.insert("1.0", json.dumps(api_config["response_format"], indent=2))
    
    def start_service(self):
        """Start the Universal MCP Tool service"""
        try:
            self.log("正在启动Universal MCP Tool服务...")
            # Get absolute path to the script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 修改为使用mcp_pipe.py作为启动脚本
            mcp_script = os.path.join(current_dir, "mcp_pipe.py")
            universal_mcp_script = os.path.join(current_dir, "universal_mcp_tool.py")
            
            # 创建批处理文件以避免PowerShell中的&字符问题
            batch_content = f'@echo off\ncd /d "{current_dir}"\npython "{mcp_script}" "{universal_mcp_script}"\npause'
            
            batch_file = os.path.join(tempfile.gettempdir(), "run_universal_mcp.bat")
            with open(batch_file, "w") as f:
                f.write(batch_content)
            
            # 启动进程
            if os.name == 'nt':
                subprocess.Popen(["cmd.exe", "/c", "start", "cmd", "/c", batch_file], shell=False)
            else:
                subprocess.Popen(["python", mcp_script, universal_mcp_script], cwd=current_dir)
            
            self.log("服务已在后台启动")
            messagebox.showinfo("启动成功", "Universal MCP Tool服务已在后台运行")
        except Exception as e:
            self.log(f"启动服务失败: {str(e)}")
            messagebox.showerror("启动失败", str(e))
    
    def log(self, message):
        """Add message to log"""
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.configure(state='disabled')
        self.log_text.see(tk.END)
    
    def clear_log(self):
        """Clear log"""
        self.log_text.configure(state='normal')
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state='disabled')
    
    def on_close(self):
        """Handle window close"""
        self.root.destroy()
    
    def run(self):
        """Run the application"""
        self.root.mainloop()

if __name__ == "__main__":
    app = UniversalMCPGUI()
    app.run() 
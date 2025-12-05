[根目录](../../CLAUDE.md) > [src](../) > **api**

# API 模块 - REST服务和WebSocket通信

## 模块职责

API模块负责处理所有HTTP请求和WebSocket连接，提供翻译任务的管理接口。它采用Flask Blueprint架构组织路由，确保代码的模块化和可维护性。

## 入口与启动

- **主入口**: `routes.py` - 路由编排器
- **服务器启动**: `../translation_api.py` - Flask应用初始化
- **状态管理**: `translation_state.py` - 线程安全的任务状态管理

## 对外接口

### REST API端点 (通过Blueprints)

1. **配置与健康检查** (`config_routes.py`)
   - `GET /api/health` - 健康检查
   - `GET /api/models` - 获取可用模型列表
   - `GET /api/config` - 获取当前配置
   - `POST /api/config` - 更新配置

2. **翻译任务管理** (`translation_routes.py`)
   - `POST /api/translate` - 创建翻译任务
   - `GET /api/translate` - 获取翻译任务列表
   - `GET /api/translate/<job_id>` - 获取任务状态
   - `DELETE /api/translate/<job_id>` - 取消翻译任务
   - `POST /api/translate/<job_id>/resume` - 恢复暂停的任务

3. **文件操作** (`file_routes.py`)
   - `GET /api/files` - 获取已翻译文件列表
   - `GET /api/files/download/<filename>` - 下载文件
   - `DELETE /api/files/<filename>` - 删除文件

4. **安全与上传** (`security_routes.py`)
   - `POST /api/upload` - 文件上传
   - 文件类型验证和安全检查

### WebSocket事件

- `connect` - 客户端连接
- `disconnect` - 客户端断开
- `start_translation` - 开始翻译任务
- `pause_translation` - 暂停翻译任务
- `cancel_translation` - 取消翻译任务
- `get_status` - 获取翻译状态

## 关键依赖与配置

### 内部依赖
- `src.core.translator` - 翻译引擎
- `src.core.llm_providers` - LLM提供商
- `src.utils.file_service` - 文件处理服务
- `src.persistence.database` - 数据库操作

### 外部依赖
- Flask 2.0+ - Web框架
- Flask-CORS - 跨域支持
- Flask-SocketIO - WebSocket支持
- python-socketio - WebSocket客户端

### 配置参数 (来自 src.config)
```python
PORT = 5000          # 服务器端口
HOST = '127.0.0.1'   # 服务器地址
OUTPUT_DIR = 'translated_files'  # 输出目录
```

## 核心组件

### 1. 路由编排器 (`routes.py`)
负责注册所有Blueprint和错误处理器：
```python
def configure_routes(app, state_manager, output_dir, start_translation_job):
    # 注册各种Blueprint
    config_bp = create_config_blueprint()
    translation_bp = create_translation_blueprint(state_manager, start_translation_job)
    file_bp = create_file_blueprint(output_dir)
    security_bp = create_security_blueprint(output_dir)
```

### 2. 翻译状态管理器 (`translation_state.py`)
线程安全的翻译任务状态管理：
- 任务创建、更新、删除
- 进度跟踪
- WebSocket状态广播
- 并发控制

### 3. WebSocket处理器 (`websocket.py`)
实时通信处理：
- 任务进度推送
- 错误消息广播
- 客户端状态同步
- 连接池管理

### 4. API处理器 (`handlers.py`)
翻译任务的业务逻辑：
- 任务队列管理
- 文件类型检测
- 翻译参数验证
- 错误处理和重试

## 数据模型

### TranslationJob (翻译任务)
```json
{
  "job_id": "uuid",
  "status": "pending|running|paused|completed|failed",
  "progress": 0-100,
  "source_file": "path",
  "target_file": "path",
  "source_lang": "English",
  "target_lang": "Chinese",
  "model": "qwen3:14b",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "error_message": null
}
```

### FileUpload (文件上传)
```json
{
  "filename": "example.epub",
  "size": 1024000,
  "type": "epub|srt|txt",
  "upload_time": "timestamp",
  "safe_path": "validated_path"
}
```

## 测试与质量

### 当前状态
❌ **缺少自动化测试**

### 建议的测试覆盖
1. **单元测试**
   - 各Blueprint路由的功能测试
   - 状态管理器的并发测试
   - WebSocket事件处理测试

2. **集成测试**
   - 完整翻译流程测试
   - 文件上传下载测试
   - 错误处理测试

3. **性能测试**
   - 并发翻译任务测试
   - 大文件处理测试
   - WebSocket连接数限制测试

### 测试工具建议
- `pytest` - 单元测试框架
- `pytest-asyncio` - 异步测试支持
- `pytest-flask` - Flask应用测试
- `pytest-websocket` - WebSocket测试

## 常见问题 (FAQ)

### Q: 如何处理大文件上传？
A: 使用流式上传和临时文件，避免内存溢出。文件大小限制在 `security_routes.py` 中配置。

### Q: WebSocket连接数有限制吗？
A: 有，默认最大1000个并发连接。可在 `websocket.py` 中调整。

### Q: 翻译任务如何保证幂等性？
A: 每个任务都有唯一UUID，重复请求会返回相同任务ID而不是创建新任务。

### Q: 如何处理翻译过程中的网络中断？
A: 使用检查点机制，中断后可从上次位置恢复。见 `checkpoint_manager.py`。

## 相关文件清单

### 核心文件
- `__init__.py` - 模块初始化
- `routes.py` - 路由编排器
- `handlers.py` - API业务逻辑
- `translation_state.py` - 状态管理器
- `websocket.py` - WebSocket处理器

### Blueprints
- `blueprints/__init__.py` - Blueprint工厂函数
- `blueprints/config_routes.py` - 配置和健康检查
- `blueprints/translation_routes.py` - 翻译任务管理
- `blueprints/file_routes.py` - 文件操作
- `blueprints/security_routes.py` - 安全和上传

### 服务层
- `services/file_service.py` - 文件操作服务
- `services/path_validator.py` - 路径验证服务

## 变更记录 (Changelog)

**2025-12-05**: 创建API模块文档，梳理接口架构和组件关系。
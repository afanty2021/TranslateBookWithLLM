[根目录](../../../CLAUDE.md) > [src](../../) > [api](../) > **blueprints**

# blueprints 子模块文档

## 模块职责

blueprints子模块采用Flask Blueprint架构模式，将API路由按功能分组管理，提供：
- 模块化的路由组织
- 清晰的功能边界
- 易于维护和扩展的代码结构
- 统一的错误处理和响应格式

## 入口与启动

蓝图在`../routes.py`中注册和初始化：
```python
from src.api.blueprints import (
    create_config_blueprint,
    create_translation_blueprint,
    create_file_blueprint,
    create_security_blueprint
)

# 注册蓝图
app.register_blueprint(config_bp)
app.register_blueprint(translation_bp)
app.register_blueprint(file_bp)
app.register_blueprint(security_bp)
```

## 对外接口

### config_routes.py - 配置与健康检查
```python
# 主要路由端点
GET  /                         # 主页面
GET  /api/health              # 健康检查
GET  /api/models?provider=    # 获取可用模型
GET  /api/config              # 获取当前配置
POST /api/config              # 更新配置
```

### translation_routes.py - 翻译任务管理
```python
# 核心翻译API
POST /api/translate           # 创建翻译任务
GET  /api/translate          # 获取任务列表
GET  /api/translate/<id>     # 获取任务状态
DELETE /api/translate/<id>   # 取消任务
POST /api/translate/<id>/resume  # 恢复任务

# 状态管理
POST /api/translate/<id>/pause    # 暂停任务
GET  /api/translate/<id>/progress # 获取进度
```

### file_routes.py - 文件操作
```python
# 文件管理API
GET  /api/files              # 文件列表
GET  /api/files/download/<name>  # 下载文件
DELETE /api/files/<name>     # 删除文件
POST /api/files/rename       # 重命名文件
```

### security_routes.py - 安全与上传
```python
# 上传和安全API
POST /api/upload             # 文件上传
POST /api/validate-upload    # 预验证文件
GET  /api/upload-limits      # 获取上传限制
```

## 关键依赖与配置

### 共同依赖
```python
# Flask核心
from flask import Blueprint, request, jsonify, send_from_directory

# 项目内部模块
from src.config import *
from src.utils.security import SecureFileHandler
from src.persistence.checkpoint_manager import CheckpointManager
```

### 环境变量
```python
# API配置
PORT = os.getenv('PORT', 5000)
HOST = os.getenv('HOST', '127.0.0.1')

# 翻译配置
MAIN_LINES_PER_CHUNK = int(os.getenv('MAIN_LINES_PER_CHUNK', 25))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 900))

# 文件限制
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
```

### 支持的LLM提供商
```python
LLM_PROVIDERS = {
    'ollama': {
        'endpoint_var': 'API_ENDPOINT',
        'model_var': 'DEFAULT_MODEL',
        'default_endpoint': 'http://localhost:11434/api/generate'
    },
    'gemini': {
        'key_var': 'GEMINI_API_KEY',
        'model_var': 'GEMINI_MODEL',
        'default_model': 'gemini-2.0-flash'
    },
    'openai': {
        'key_var': 'OPENAI_API_KEY',
        'endpoint_var': 'API_ENDPOINT',
        'model_var': 'DEFAULT_MODEL'
    }
}
```

## 数据模型

### 请求模型

#### 翻译请求 (POST /api/translate)
```json
{
  // 文本翻译
  "text": "Hello world",
  "source_language": "English",
  "target_language": "Chinese",
  "model": "qwen3:14b",
  "llm_api_endpoint": "http://localhost:11434/api/generate",
  "output_filename": "translated.txt",

  // 文件翻译
  "file_path": "/path/to/file.epub",
  "file_type": "epub|srt|txt",

  // 可选参数
  "epub_fast_mode": true,
  "signature_enabled": true,
  "config": {
    "chunk_size": 25,
    "context_window": 8192
  }
}
```

#### 配置更新 (POST /api/config)
```json
{
  "llm_provider": "ollama|gemini|openai",
  "api_endpoint": "http://...",
  "default_model": "model_name",
  "source_language": "English",
  "target_language": "Chinese",
  "chunk_size": 25,
  "request_timeout": 900
}
```

### 响应模型

#### 健康检查响应
```json
{
  "status": "ok",
  "message": "Translation API is running",
  "translate_module": "loaded",
  "supported_formats": ["txt", "epub", "srt"],
  "default_endpoint": "http://localhost:11434/api/generate"
}
```

#### 模型列表响应
```json
{
  "provider": "ollama",
  "models": [
    {
      "name": "qwen3:14b",
      "size": "8.2GB",
      "modified_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### 任务状态响应
```json
{
  "translation_id": "trans_1234567890",
  "status": "running|paused|completed|error",
  "progress": {
    "current": 45,
    "total": 100,
    "percentage": 45,
    "message": "Processing chunk 46/100"
  },
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:05:00Z",
  "error_message": null
}
```

#### 文件列表响应
```json
{
  "files": [
    {
      "name": "translated_book.epub",
      "size": 1024000,
      "created_at": "2024-01-01T12:00:00Z",
      "download_url": "/api/files/download/translated_book.epub"
    }
  ],
  "total_size": 1024000,
  "count": 1
}
```

### 错误响应模型
```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "value",
    "additional_info": "..."
  }
}
```

## 测试与质量

### 测试策略

#### 1. 单元测试 (每个蓝图)
```python
# test_config_routes.py
def test_health_check():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'

def test_get_models():
    response = client.get('/api/models?provider=ollama')
    assert response.status_code == 200
    assert 'models' in response.json

# test_translation_routes.py
def test_create_translation():
    data = {
        'text': 'Hello',
        'source_language': 'English',
        'target_language': 'Chinese',
        'model': 'qwen3:14b',
        'llm_api_endpoint': 'http://localhost:11434/api/generate',
        'output_filename': 'test.txt'
    }
    response = client.post('/api/translate', json=data)
    assert response.status_code == 200
    assert 'translation_id' in response.json
```

#### 2. 集成测试
```python
# test_full_workflow.py
def test_translation_workflow():
    # 1. 上传文件
    with open('test.txt', 'rb') as f:
        response = client.post('/api/upload', data={'file': f})
    file_path = response.json['file_path']

    # 2. 创建翻译任务
    response = client.post('/api/translate', json={
        'file_path': file_path,
        'source_language': 'English',
        'target_language': 'Chinese',
        'model': 'qwen3:14b',
        'output_filename': 'translated.txt'
    })
    translation_id = response.json['translation_id']

    # 3. 等待完成
    # ... wait for completion ...

    # 4. 下载结果
    response = client.get(f'/api/files/download/translated.txt')
    assert response.status_code == 200
```

#### 3. 错误处理测试
```python
def test_invalid_translation_request():
    # 缺少必需字段
    response = client.post('/api/translate', json={})
    assert response.status_code == 400
    assert 'Missing field' in response.json['error']

def test_file_not_found():
    response = client.get('/api/files/download/nonexistent.txt')
    assert response.status_code == 404
```

#### 4. 性能测试
```python
def test_concurrent_requests():
    # 并发创建多个翻译任务
    import threading
    import concurrent.futures

    def create_task():
        return client.post('/api/translate', json=test_data)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_task) for _ in range(10)]
        results = [f.result() for f in futures]

    # 验证所有任务都成功创建
    assert all(r.status_code == 200 for r in results)
```

### 测试文件结构
```
tests/
  api/
    blueprints/
      test_config_routes.py        # 配置路由测试
      test_translation_routes.py   # 翻译路由测试
      test_file_routes.py          # 文件路由测试
      test_security_routes.py      # 安全路由测试
      integration/
        test_full_workflow.py      # 完整流程测试
        test_error_handling.py     # 错误处理测试
        test_performance.py        # 性能测试
      fixtures/
        test_files/                # 测试文件
          sample.txt
          sample.epub
          sample.srt
        mock_responses/            # 模拟响应
          ollama_models.json
          gemini_models.json
```

### 质量保证
- 统一的响应格式
- 完善的错误处理
- 输入验证和清理
- 速率限制和防护
- 详细的日志记录
- 性能监控

## 常见问题 (FAQ)

### Q1: 如何添加新的API端点？
A: 在对应的蓝图文件中添加新路由，确保遵循现有的命名和响应格式约定。

### Q2: 文件上传大小限制在哪里配置？
A: 在security_routes.py中修改MAX_FILE_SIZE常量，或使用环境变量MAX_UPLOAD_SIZE。

### Q3: 如何处理跨域请求(CORS)？
A: 在主应用中配置Flask-CORS，蓝图继承CORS设置。

### Q4: 翻译任务的ID如何生成？
A: 使用时间戳+随机数的组合：`trans_{int(time.time() * 1000)}`

### Q5: WebSocket和REST API如何协调？
A: REST API创建和管理任务，WebSocket实时推送状态更新，通过translation_id关联。

## 相关文件清单

### 蓝图文件
- `__init__.py` - 蓝图工厂函数
- `config_routes.py` - 配置和健康检查路由
- `translation_routes.py` - 翻译任务管理路由
- `file_routes.py` - 文件操作路由
- `security_routes.py` - 安全和上传路由

### 父级模块
- `../routes.py` - 路由编排器
- `../handlers.py` - 业务逻辑处理器
- `../translation_state.py` - 状态管理器

### 依赖模块
- `../../config.py` - 配置常量
- `../../utils/security.py` - 安全工具
- `../../persistence/` - 持久化层

## 变更记录 (Changelog)

### 2025-12-05
- 初始化blueprints子模块文档
- 详细记录各蓝图的路由和数据模型
- 完善测试策略和错误处理
- 添加API使用示例和最佳实践
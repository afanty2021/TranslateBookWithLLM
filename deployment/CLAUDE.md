[根目录](../CLAUDE.md) > **deployment**

# deployment 模块文档

## 模块职责

deployment模块提供TranslateBookWithLLM的Docker容器化部署方案，包括：
- Docker镜像构建配置
- 容器编排和服务管理
- 多环境配置支持
- 自动化测试脚本
- 部署文档和故障排除

## 入口与启动

### 快速启动
```bash
cd deployment
# 复制环境配置
cp .env.docker.example .env
# 启动服务
docker-compose up -d
```

### 自动化测试
```bash
# Linux/macOS
./test_docker.sh

# Windows
test_docker.bat
```

## 对外接口

### Docker Compose配置
```yaml
services:
  translatebook:
    build:
      context: ..
      dockerfile: deployment/Dockerfile
    ports:
      - "${PORT:-5000}:${PORT:-5000}"
    volumes:
      - ./translated_files:/app/translated_files
      - ./logs:/app/logs
      - ./data:/app/data
    environment:
      - LLM_PROVIDER=${LLM_PROVIDER:-ollama}
      - API_ENDPOINT=${API_ENDPOINT}
      # ... 更多环境变量
```

### 健康检查
- **端点**: `http://localhost:5000/api/health`
- **间隔**: 30秒
- **超时**: 10秒
- **重试**: 3次
- **启动等待**: 40秒

### 端口映射
- **默认端口**: 5000
- **内部端口**: 5000
- **协议**: HTTP

## 关键依赖与配置

### 基础镜像
```dockerfile
FROM python:3.9-slim
```

### 系统依赖
```dockerfile
# 健康检查需要
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
```

### Python依赖
- 从项目根目录的`requirements.txt`安装
- 包含Web框架、LLM客户端、文件处理等依赖

### 环境变量配置
```bash
# 服务器配置
PORT=5000
HOST=0.0.0.0
OUTPUT_DIR=/app/translated_files

# LLM提供商
LLM_PROVIDER=ollama
API_ENDPOINT=http://host.docker.internal:11434/api/generate
DEFAULT_MODEL=qwen3:14b

# 翻译设置
DEFAULT_SOURCE_LANGUAGE=English
DEFAULT_TARGET_LANGUAGE=Chinese
MAIN_LINES_PER_CHUNK=25
MAIN_CHUNK_SIZE=1000
REQUEST_TIMEOUT=900

# 上下文管理
AUTO_ADJUST_CONTEXT=true
MIN_CHUNK_SIZE=5
MAX_CHUNK_SIZE=100

# SRT字幕设置
SRT_LINES_PER_BLOCK=5
SRT_MAX_CHARS_PER_BLOCK=500
```

### 数据卷挂载
```yaml
volumes:
  # 翻译输出文件
  - ./translated_files:/app/translated_files
  # 日志文件（可选）
  - ./logs:/app/logs
  # 数据库和检查点（必需）
  - ./data:/app/data
```

## 数据模型

### 目录结构
```
deployment/
├── Dockerfile              # Docker镜像构建配置
├── docker-compose.yml      # 容器编排配置
├── .env.docker.example     # 环境变量模板
├── .dockerignore          # Docker构建忽略文件
├── test_docker.sh         # Linux/macOS测试脚本
├── test_docker.bat        # Windows测试脚本
├── TESTING.md             # 测试指南文档
└── data/                  # 持久化数据目录
    └── jobs.db            # SQLite数据库文件
```

### 容器内路径
```yaml
# 工作目录
WORKDIR /app

# 数据目录
/app/translated_files  # 翻译输出
/app/logs             # 日志文件
/app/data             # 数据库和上传文件
/app/data/uploads     # 上传文件临时存储
```

### 健康检查响应
```json
{
  "message": "Translation API is running",
  "status": "ok",
  "supported_formats": ["txt", "epub", "srt"],
  "translate_module": "loaded"
}
```

## 测试与质量

### 测试策略

#### 1. 自动化测试
- **构建测试**
  - Docker镜像构建成功
  - 依赖安装完整
  - 启动脚本可执行

- **容器测试**
  - 容器正常启动
  - 健康检查通过
  - 端口映射正确

- **功能测试**
  - API端点响应
  - Web界面访问
  - 文件上传处理

#### 2. 多平台测试
- **Windows测试**
  - Docker Desktop兼容性
  - WSL 2支持
  - 路径映射正确

- **Linux测试**
  - 原生Docker支持
  - host网络访问
  - 权限管理

- **macOS测试**
  - Docker Desktop兼容性
  - 文件系统性能
  - 网络配置

#### 3. 集成测试
- **LLM提供商测试**
  - Ollama本地连接
  - Gemini API访问
  - OpenAI API访问

- **文件类型测试**
  - TXT文件处理
  - EPUB文件处理
  - SRT字幕处理

#### 4. 性能测试
- **资源使用监控**
  ```bash
  docker stats translatebook-llm
  ```

- **并发请求测试**
  - 多用户同时访问
  - 大文件处理能力
  - 内存使用稳定性

### 测试文件结构
```
deployment/
├── test_docker.sh          # Linux/macOS测试脚本
├── test_docker.bat         # Windows测试脚本
├── TESTING.md              # 详细测试指南
├── tests/                  # 测试用例目录
│   ├── test_build.py       # 构建测试
│   ├── test_health.py      # 健康检查测试
│   ├── test_api.py         # API功能测试
│   └── fixtures/           # 测试数据
│       ├── sample.txt
│       ├── sample.epub
│       └── sample.srt
```

### CI/CD集成
```yaml
# .github/workflows/docker-test.yml
name: Docker Build and Test
on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: docker-compose build
      - name: Start container
        run: docker-compose up -d
      - name: Wait for health
        run: sleep 45
      - name: Test health endpoint
        run: curl -f http://localhost:5000/api/health
```

### 质量保证
- 自动化测试覆盖
- 多平台验证
- 健康检查机制
- 日志记录完整
- 错误恢复机制
- 资源使用监控

## 常见问题 (FAQ)

### Q1: 容器无法启动，提示端口被占用？
A: 修改.env文件中的PORT变量，或停止占用5000端口的其他服务。

### Q2: 健康检查一直失败？
A: 检查日志`docker-compose logs`，确认Flask服务器正常启动，等待40秒启动时间。

### Q3: 无法访问host机器的Ollama服务？
A: Windows/Mac使用`host.docker.internal`，Linux需要配置extra_hosts或使用主机IP。

### Q4: 翻译文件没有持久化？
A: 确保正确挂载了volumes，检查`translated_files`目录权限。

### Q5: 容器重启后数据丢失？
A: 数据库在`data`目录中，确保该目录被挂载为volume。

## 相关文件清单

### 核心配置
- `Dockerfile` - Docker镜像构建定义 (35行)
- `docker-compose.yml` - 容器编排配置 (69行)
- `.env.docker.example` - 环境变量模板 (84行)
- `.dockerignore` - 构建忽略规则

### 测试工具
- `test_docker.sh` - Linux/macOS自动化测试脚本 (122行)
- `test_docker.bat` - Windows批处理测试脚本
- `TESTING.md` - 详细测试和故障排除指南 (368行)

### 数据和日志
- `data/jobs.db` - SQLite数据库文件
- `logs/` - 应用日志目录
- `translated_files/` - 翻译输出目录

### 文档
- `README.md` - 项目说明（根目录）
- `DOCKER_DEPLOYMENT.md` - Docker部署详细指南

## 变更记录 (Changelog)

### 2025-12-05
- 初始化deployment模块文档
- 详细记录Docker配置和测试策略
- 完善多平台部署说明
- 添加故障排除和性能优化建议

### 部署建议
1. 生产环境建议使用external database替代SQLite
2. 配置reverse proxy (nginx/Traefik)实现HTTPS
3. 设置log rotation避免日志文件过大
4. 定期备份data目录中的数据库文件
5. 监控容器资源使用情况
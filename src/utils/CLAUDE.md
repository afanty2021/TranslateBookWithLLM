[根目录](../../CLAUDE.md) > [src](../) > **utils**

# utils 模块文档

## 模块职责

utils模块提供项目所需的通用工具和辅助功能，包括：
- 文件操作和路径管理
- 文件类型检测和验证
- 安全文件处理
- 统一日志系统
- 环境配置管理

## 入口与启动

模块作为工具集合，无单一入口点，按功能组织：
- `file_utils.py` - 文件操作工具
- `file_detector.py` - 文件类型检测
- `security.py` - 安全文件处理
- `unified_logger.py` - 统一日志系统
- `env_helper.py` - 环境配置辅助

## 对外接口

### 文件操作工具 (file_utils.py)
```python
from src.utils.file_utils import get_unique_output_path

# 生成唯一输出路径
output_path = get_unique_output_path("output.txt")
```

### 文件类型检测 (file_detector.py)
```python
from src.utils.file_detector import detect_file_type, generate_output_filename

# 检测文件类型
file_type = detect_file_type("book.epub")  # 返回: "epub"

# 生成输出文件名
output_name = generate_output_filename("book.txt", "Chinese")  # 返回: "book_Chinese.txt"
```

### 安全文件处理 (security.py)
```python
from src.utils.security import SecureFileHandler

handler = SecureFileHandler()

# 验证上传文件
result = handler.validate_file(uploaded_file)
if result.is_valid:
    # 安全保存文件
    saved_path = handler.save_file(uploaded_file, upload_dir)
```

### 统一日志 (unified_logger.py)
```python
from src.utils.unified_logger import UnifiedLogger, LogLevel, LogType

logger = UnifiedLogger()

# 记录不同类型的日志
logger.info("Translation started", log_type=LogType.TRANSLATION_START)
logger.debug("Processing chunk", log_type=LogType.CHUNK_INFO, data={"chunk": 1})
```

### 环境配置 (env_helper.py)
```python
from src.utils.env_helper import create_env_from_template, validate_env_config

# 从模板创建.env文件
create_env_from_template()

# 验证环境配置
status = validate_env_config(verbose=True)
```

## 关键依赖与配置

### 内部依赖
- `pathlib` - 现代路径操作
- `secrets` - 安全随机数生成
- `mimetypes` - MIME类型检测
- `enum` - 枚举类型定义

### 外部依赖
- `aiofiles` - 异步文件操作
- `python-dotenv` - 环境变量加载

### 支持的文件类型
```python
# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'.txt', '.epub', '.srt'}

# 允许的MIME类型
ALLOWED_MIME_TYPES = {
    'text/plain',
    'application/epub+zip',
    'application/x-subrip',
    'text/srt',
}
```

### 安全配置
```python
# 文件大小限制
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# 文件名安全规则
SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')

# 路径遍历防护
forbidden_paths = {'..', '~', '/', '\\'}
```

### 日志配置
```python
# 日志级别
class LogLevel(Enum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

# 日志类型
class LogType(Enum):
    GENERAL = "general"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    PROGRESS = "progress"
    CHUNK_INFO = "chunk_info"
    FILE_OPERATION = "file_operation"
    TRANSLATION_START = "translation_start"
    TRANSLATION_END = "translation_end"
    ERROR_DETAIL = "error_detail"
```

## 数据模型

### FileValidationResult
```python
@dataclass
class FileValidationResult:
    """文件验证结果"""
    is_valid: bool
    file_path: Optional[Path] = None
    error_message: Optional[str] = None
    warnings: list = None
```

### 安全处理结果
```python
# 文件安全扫描结果
security_result = {
    'is_safe': bool,
    'threats_detected': list,
    'warnings': list,
    'recommended_action': str
}
```

### 日志条目结构
```python
log_entry = {
    'timestamp': datetime,
    'level': LogLevel,
    'type': LogType,
    'message': str,
    'data': dict,  # 附加数据
    'source': str   # 日志来源
}
```

## 测试与质量

### 测试策略

#### 1. 单元测试
- **file_utils.py**
  - 唯一路径生成逻辑
  - 文件名冲突处理
  - 异步文件操作

- **file_detector.py**
  - 文件类型检测准确性
  - 边界文件名处理
  - 大小写敏感性

- **security.py**
  - 文件验证逻辑
  - 恶意文件检测
  - 路径遍历防护
  - 文件大小限制

- **unified_logger.py**
  - 日志级别过滤
  - 不同输出格式
  - 异步日志记录
  - 性能影响测试

- **env_helper.py**
  - .env文件创建
  - 配置验证逻辑
  - 交互式设置向导

#### 2. 安全测试
- **恶意文件测试**
  - 可执行文件上传尝试
  - 脚本注入检测
  - 路径遍历攻击
  - 文件类型伪造

- **文件大小测试**
  - 大文件上传处理
  - 磁盘空间检查
  - 内存使用监控

#### 3. 性能测试
- **日志性能**
  - 高频日志记录
  - 大量数据序列化
  - 异步vs同步性能

- **文件操作性能**
  - 大文件处理速度
  - 并发文件操作
  - 磁盘I/O优化

#### 4. 集成测试
- **完整上传流程**
  - 文件验证→保存→处理→清理
  - 错误恢复机制
  - 资源清理验证

- **配置系统集成**
  - 环境变量加载
  - 默认值回退
  - 配置热重载

### 测试文件结构
```
tests/
  utils/
    test_file_utils.py      # 文件操作测试
    test_file_detector.py   # 文件检测测试
    test_security.py        # 安全功能测试
    test_unified_logger.py  # 日志系统测试
    test_env_helper.py      # 环境配置测试
    fixtures/               # 测试数据
      safe_files/
      malicious_files/
      config_samples/
```

### 质量保证
- 输入验证和清理
- 异常处理和错误恢复
- 资源自动清理
- 安全最佳实践
- 性能基准测试

## 常见问题 (FAQ)

### Q1: 如何添加新的文件类型支持？
A: 修改file_detector.py中的FileType和detect_file_type函数，同时更新security.py中的ALLOWED_EXTENSIONS和ALLOWED_MIME_TYPES。

### Q2: 日志系统是否支持远程日志收集？
A: 当前版本仅支持本地文件和控制台输出，可通过扩展UnifiedLogger类添加远程传输支持。

### Q3: 如何处理大文件上传而避免内存溢出？
A: 使用流式处理，分块读取和验证， security.py已实现大文件的安全检查机制。

### Q4: 环境配置是否支持加密存储？
A: 当前使用明文.env文件，敏感信息建议使用环境变量或密钥管理服务。

### Q5: 如何自定义日志格式？
A: 继承UnifiedLogger类并重写format_message方法，或修改Colors类中的颜色配置。

## 相关文件清单

### 核心文件
- `file_utils.py` - 文件操作工具 (文件路径管理)
- `file_detector.py` - 文件类型检测 (48行)
- `security.py` - 安全文件处理 (文件验证和保存)
- `unified_logger.py` - 统一日志系统 (多级日志和颜色支持)
- `env_helper.py` - 环境配置辅助 (239行，包含交互式设置)
- `__init__.py` - 模块初始化

### 依赖文件
- `.env.example` - 环境配置模板
- `requirements.txt` - Python依赖列表

### 使用示例
- `scripts/setup_config.py` - 使用env_helper的配置脚本
- `src/api/routes.py` - 使用security和logger的API示例

## 变更记录 (Changelog)

### 2025-12-05
- 初始化utils模块文档
- 详细记录各工具类的功能和接口
- 完善安全处理和测试策略
- 添加环境配置向导说明
[根目录](../../CLAUDE.md) > **scripts**

# scripts 模块文档

## 模块职责

scripts模块提供项目安装和配置的辅助脚本，帮助用户：
- 快速配置环境变量
- 诊断和修复安装问题
- 验证系统兼容性
- 提供交互式设置向导

## 入口与启动

模块包含独立的可执行脚本：
- `setup_config.py` - 配置设置主程序
- `fix_installation.py` - 安装问题诊断和修复工具

执行方式：
```bash
# 运行配置向导
python scripts/setup_config.py

# 运行安装诊断
python scripts/fix_installation.py
```

## 对外接口

### setup_config.py - 配置设置程序
```python
# 直接运行交互式设置
python scripts/setup_config.py

# 或导入使用
from scripts.setup_config import main
main()
```

主要功能菜单：
1. **快速设置** - 从.env.example复制模板
2. **交互式设置** - 引导式配置向导
3. **验证配置** - 检查当前配置状态
4. **退出** - 离开程序

### fix_installation.py - 安装诊断工具
```python
# 直接运行诊断
python scripts/fix_installation.py

# 或单独调用各项检查
from scripts.fix_installation import check_python_version, fix_prompts_file
```

诊断功能：
- Python版本检查（需要3.8+）
- prompts.py语法修复
- Python缓存清理
- 环境配置检查
- 模块导入测试

## 关键依赖与配置

### 内部依赖
- `sys` - 系统信息和路径管理
- `os` - 操作系统接口
- `pathlib` - 现代路径操作
- `re` - 正则表达式处理

### 外部依赖
- `python-dotenv` - 环境变量加载（运行时）
- `src.utils.env_helper` - 环境配置辅助函数

### 检查项目
```python
# Python版本要求
MIN_PYTHON_VERSION = (3, 8)
RECOMMENDED_PYTHON_VERSION = (3, 11)

# 检查的关键文件
CRITICAL_FILES = [
    'prompts.py',
    '.env.example',
    'requirements.txt'
]

# 环境变量检查清单
REQUIRED_ENV_VARS = {
    'API_ENDPOINT': 'LLM API端点',
    'LLM_PROVIDER': 'LLM提供商',
    'DEFAULT_MODEL': '默认模型'
}
```

### 修复规则
```python
# prompts.py自动修复规则
FIX_RULES = {
    'windows_paths': {
        'pattern': r'C:\\Users\\Documents\\',
        'replacement': 'C:/Users/Documents/',
        'description': '修复Windows路径中的反斜杠'
    },
    'f_string_newlines': {
        'pattern': r'additional_rules="\\n',
        'action': 'manual',  # 需要手动修复
        'description': 'f-string中的换行符问题'
    }
}
```

## 数据模型

### 诊断结果结构
```python
diagnostic_result = {
    'python_version': {
        'status': 'ok' | 'warning' | 'error',
        'version': str,
        'message': str
    },
    'prompts_file': {
        'status': 'ok' | 'warning' | 'error',
        'fixes_applied': list,
        'issues_remaining': list
    },
    'env_config': {
        'exists': bool,
        'configured': bool,
        'missing_vars': list
    },
    'import_test': {
        'status': 'ok' | 'error',
        'error_details': str
    }
}
```

### 配置选项映射
```python
# LLM提供商配置映射
PROVIDER_CONFIG = {
    'ollama': {
        'required_vars': ['API_ENDPOINT', 'DEFAULT_MODEL'],
        'optional_vars': ['OLLAMA_NUM_CTX'],
        'default_endpoint': 'http://localhost:11434/api/generate'
    },
    'gemini': {
        'required_vars': ['GEMINI_API_KEY', 'GEMINI_MODEL'],
        'optional_vars': [],
        'default_model': 'gemini-2.0-flash'
    },
    'openai': {
        'required_vars': ['OPENAI_API_KEY', 'API_ENDPOINT', 'DEFAULT_MODEL'],
        'optional_vars': [],
        'default_endpoint': 'https://api.openai.com/v1/chat/completions',
        'default_model': 'gpt-4o'
    }
}
```

## 测试与质量

### 测试策略

#### 1. 单元测试
- **setup_config.py测试**
  - 菜单选择逻辑
  - 用户输入处理
  - 错误处理和异常捕获
  - 配置文件创建

- **fix_installation.py测试**
  - 版本检查准确性
  - 文件修复逻辑
  - 缓存清理功能
  - 导入测试可靠性

#### 2. 集成测试
- **完整设置流程**
  - 运行setup_config.py创建配置
  - 验证配置文件内容
  - 测试应用启动

- **问题修复流程**
  - 模拟常见安装问题
  - 运行修复脚本
  - 验证修复效果

#### 3. 系统测试
- **跨平台兼容性**
  - Windows路径处理
  - Unix权限处理
  - 不同Python版本

- **边界条件测试**
  - 最小Python版本
  - 缺失依赖项
  - 权限不足场景

#### 4. 用户体验测试
- **交互流程**
  - 菜单导航清晰度
  - 错误信息易懂性
  - 操作步骤简便性

- **错误恢复**
  - Ctrl+C中断处理
  - 无效输入处理
  - 异常情况恢复

### 测试文件结构
```
tests/
  scripts/
    test_setup_config.py        # 配置脚本测试
    test_fix_installation.py    # 修复脚本测试
    fixtures/                   # 测试用例
      broken_prompts.py        # 损坏的prompts.py示例
      sample_env.example       # 环境模板示例
      version_scenarios.json   # Python版本测试场景
    integration/                # 集成测试
      test_full_setup.py       # 完整设置流程测试
      test_error_recovery.py   # 错误恢复测试
```

### 质量保证
- 全面的错误处理
- 清晰的用户提示
- 操作确认机制
- 回滚和恢复选项
- 详细的日志记录

## 常见问题 (FAQ)

### Q1: setup_config.py无法找到.env.example？
A: 确保在项目根目录运行脚本，.env.example文件应与README.md在同一目录。

### Q2: Python版本检查失败怎么办？
A: 升级到Python 3.8+，推荐使用Python 3.11+以获得更好的f-string支持。

### Q3: prompts.py的f-string错误需要手动修复？
A: 是的，某些复杂的f-string问题需要手动处理或从git拉取最新修复。

### Q4: 脚本运行后仍无法启动应用？
A: 检查是否安装了所有依赖：`pip install -r requirements.txt`

### Q5: 如何在非交互式环境中使用这些脚本？
A: 可以通过环境变量或参数文件传递配置，具体实现需要扩展脚本功能。

## 相关文件清单

### 核心脚本
- `setup_config.py` - 配置设置主程序 (89行，包含交互式菜单)
- `fix_installation.py` - 安装诊断和修复工具 (270行，包含多项检查)

### 支持文件
- `.env.example` - 环境配置模板
- `requirements.txt` - Python依赖列表
- `README.md` - 项目说明文档

### 依赖模块
- `src/utils/env_helper.py` - 环境配置辅助函数
- `prompts.py` - 修复目标文件

### 生成文件
- `.env` - 生成的环境配置文件
- `__pycache__/` - Python缓存（会被清理）

## 变更记录 (Changelog)

### 2025-12-05
- 初始化scripts模块文档
- 详细记录安装诊断和配置功能
- 完善测试策略和常见问题
- 添加系统兼容性说明

### 使用建议
1. 新用户先运行`fix_installation.py`确保环境正确
2. 然后运行`setup_config.py`进行配置
3. 配置完成后再次运行诊断工具验证
4. 定期运行诊断工具检查系统状态
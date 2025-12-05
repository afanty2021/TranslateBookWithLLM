[根目录](../CLAUDE.md) > **prompts**

# Prompts 模块 - AI提示词模板

## 模块职责

Prompts模块负责生成和优化与大语言模型(LLM)交互的提示词，确保翻译质量和一致性。支持系统提示词和用户提示词分离，提供多语言翻译的专业模板。

## 入口与启动

- **主入口**: `prompts.py` - 所有提示词生成函数
- **模块初始化**: `__init__.py` - 导出公共接口

## 对外接口

### 核心提示词生成函数
```python
def generate_translation_prompt(
    main_content: str,
    context_before: str,
    context_after: str,
    previous_translation: str,
    source_language: str,
    target_language: str,
    fast_mode: bool = False
) -> PromptPair
```

### 字幕翻译提示词
```python
def generate_subtitle_block_prompt(
    subtitle_block: str,
    source_language: str,
    target_language: str,
    context: str = None
) -> PromptPair
```

## 关键依赖与配置

### 内部依赖
- `src.config` - 获取标签配置和默认设置

### 配置参数
```python
TRANSLATE_TAG_IN = "<TRANSLATE_THIS>"
TRANSLATE_TAG_OUT = "</TRANSLATE_THIS>"
THINKING_TAG_IN = "<think>"
THINKING_TAG_OUT = "</think>"
```

## 核心组件

### 1. 提示词对结构
```python
@dataclass
class PromptPair:
    system: str  # 系统提示词（角色定义）
    user: str    # 用户提示词（具体任务）
```

### 2. 翻译提示词模板

#### 系统提示词特点
- 定义AI角色为专业翻译
- 设置翻译原则和标准
- 指定输出格式要求
- 处理特殊情况指导

#### 用户提示词特点
- 提供具体翻译内容
- 包含上下文信息
- 设置翻译标签边界
- 添加格式要求

### 3. 字幕翻译特殊处理
- 时间轴保留
- 字符数限制处理
- 说话人标识处理
- 格式标记保留

## 提示词策略

### 翻译质量保证机制

#### 1. 标签系统
- `<TRANSLATE_THIS>` 标记需要翻译的内容
- `<think>` 标记用于AI内部推理
- 严格的标签匹配提取

#### 2. 上下文传递
```python
context_example = f"""
上下文信息：
前文：{context_before}
后文：{context_after}
前一段翻译：{previous_translation}
"""
```

#### 3. 专业指导原则
- 忠于原文意思
- 保持语言自然流畅
- 专业术语一致性
- 文化差异考虑

### 快速模式优化
- 简化提示词结构
- 减少推理开销
- 提高处理速度
- 保持基本质量

## 提示词示例

### 标准翻译提示词对
```python
# 系统提示词
system_prompt = """你是一个专业的文学翻译家..."""

# 用户提示词
user_prompt = f"""
请将以下内容从{source_language}翻译成{target_language}：

{context_before}

<TRANSLATE_THIS>
{main_content}
</TRANSLATE_THIS>

{context_after}
"""
```

### 字幕翻译提示词对
```python
# 系统提示词
system_prompt = """你是专业的影视字幕翻译家..."""

# 用户提示词
user_prompt = f"""
翻译以下字幕块，保持时间轴格式：

{context if context else ""}

<TRANSLATE_THIS>
{subtitle_block}
</TRANSLATE_THIS>
"""
```

## 多语言支持

### 语言映射
支持任意语言对的翻译，使用语言名称而非代码：
- 中文、英文、日文、韩文等
- 支持方言和地区变体
- 自动检测语言方向

### 文化适配
- 习惯用语转换
- 日期时间格式
- 货币和度量衡
- 文化引用处理

## 质量优化

### 提示词优化策略

#### 1. 清晰性
- 明确的指令格式
- 具体的输出要求
- 避免歧义表达

#### 2. 一致性
- 统一的标签系统
- 固定的格式要求
- 标准的示例结构

#### 3. 灵活性
- 支持不同文本类型
- 适应多种LLM提供商
- 可配置的参数选项

### 评估指标
- 翻译准确性
- 格式保留度
- 术语一致性
- 语言自然度

## 测试与质量

### 当前状态
❌ **缺少自动化测试**

### 建议的测试覆盖
1. **单元测试**
   - 提示词生成函数测试
   - 标签提取测试
   - 格式验证测试

2. **集成测试**
   - 不同LLM提供商测试
   - 多语言对测试
   - 快速模式测试

3. **质量测试**
   - 翻译结果评估
   - 上下文保持测试
   - 错误处理测试

### 测试用例建议
- 简单句子翻译
- 段落上下文翻译
- 专业术语翻译
- 格式化文本翻译

## 扩展性

### 添加新提示词类型
1. 在 `prompts.py` 中添加新函数
2. 遵循 `PromptPair` 返回格式
3. 添加适当的文档字符串

### 自定义提示词
支持通过配置文件自定义提示词：
- 系统提示词模板
- 用户提示词模板
- 标签定义
- 格式要求

## 常见问题 (FAQ)

### Q: 如何修改翻译风格？
A: 调整系统提示词中的翻译原则，可以改变正式度、风格偏好等。

### Q: 标签提取失败怎么办？
A: 检查标签是否正确闭合，确保使用标准的 `<TRANSLATE_THIS>` 格式。

### Q: 如何添加新的文本类型支持？
A: 创建专门的提示词生成函数，处理特定格式的翻译需求。

### Q: 快速模式会影响质量吗？
A: 快速模式简化提示词结构，可能略微影响质量但显著提高速度。

## 相关文件清单

- `__init__.py` - 模块初始化
- `prompts.py` - 提示词生成函数

## 变更记录 (Changelog)

**2025-12-05**: 创建Prompts模块文档，梳理提示词生成架构。
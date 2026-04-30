# TranslateBookWithLLM 全面质量审查报告

> 审查日期：2026-04-30
> 审查范围：191 个 Python 文件，~52,896 行代码
> 审查工具：三路并行 AI 代码审查（核心架构 + API/安全 + 根级脚本/测试）
> 发现问题总计：73 个（P0: 12 | P1: 19 | P2: 24 | P3: 18）

---

## 目录

- [P0 — 必须立即修复（12 个）](#p0--必须立即修复12-个)
- [P1 — 重要问题，下次迭代修复（19 个）](#p1--重要问题下次迭代修复19-个)
- [P2 — 一般问题（24 个）](#p2--一般问题24-个)
- [P3 — 改进建议（18 个）](#p3--改进建议18-个)
- [关键数据](#关键数据)
- [修复优先级建议](#修复优先级建议)

---

## P0 — 必须立即修复（12 个）

### 安全漏洞

#### P0-01: API 密钥硬编码在源代码中

**文件**: `check_poe_models.py:5`, `test_cleanup.py:10`, `test_epub_translation.py:27`, `test_simple_api.py:13`

**问题**: POE API 密钥 `rEhgyNjIWdnUh-v_-9t1UKO3R-eWA5WA_5rrfvpuiYo` 和 MLX API 密钥 `siRfoz-giffab-muqko4` 直接硬编码在源代码中。这些文件在 `git status` 中显示为未跟踪文件，但如果被误提交到版本库，密钥将永久泄露。

**严重程度**: P0 — 凭据泄露可导致未授权访问
**修复建议**: 立即将这些文件加入 `.gitignore`，并将密钥迁移到 `.env` 文件中通过 `os.getenv()` 读取。已泄露的密钥应立即轮换。

---

#### P0-02: `to_dict()` 泄露所有 API 密钥

**文件**: `src/config.py:539-561`

**问题**: `TranslationConfig.to_dict()` 方法将以下字段原封不动地序列化为字典：
- `gemini_api_key`, `openai_api_key`, `openrouter_api_key`, `mistral_api_key`
- `deepseek_api_key`, `poe_api_key`, `nim_api_key`, `mlx_api_key`

如果该方法返回的字典被日志记录、发送到前端、或保存到检查点数据库，所有 API 密钥将直接泄露。

**严重程度**: P0 — 安全漏洞
**修复建议**: `to_dict()` 中将密钥字段替换为脱敏后的值（如 `***{last4}`），或者添加一个 `to_safe_dict()` 方法。

---

#### P0-03: API 密钥通过 GET 请求明文传输

**文件**: `src/api/blueprints/config_routes.py:111-113`

```python
api_key = request.args.get('api_key')
```

API 密钥作为 URL 查询参数传递，意味着密钥会出现在浏览器历史记录、服务器日志、Referer header 中。

**严重程度**: P0 — 密钥泄露
**修复建议**: 移除 GET 方法中对 `api_key` 参数的支持，强制使用 POST 方法。

---

#### P0-04: CORS + WebSocket 完全开放

**文件**: `translation_api.py:76-77`

```python
CORS(app)  # 默认允许所有来源
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
```

任何网页都可以向此 API 发起请求，任何 WebSocket 客户端都能连接并接收所有翻译数据。

**严重程度**: P0 — 远程攻击者可读取/控制全部功能
**修复建议**:
```python
CORS(app, origins=[f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"])
socketio = SocketIO(app, cors_allowed_origins=[f"http://localhost:{PORT}"])
```

---

#### P0-05: `/api/uploads/verify` 任意文件探测漏洞

**文件**: `src/api/blueprints/security_routes.py:198-227`

```python
for file_path_str in file_paths:
    file_path = Path(file_path_str)
    if file_path.exists():
        existing_files.append(file_path_str)
```

该端点接受任意路径列表并检查文件是否存在，没有任何路径限制。攻击者可以探测 `/etc/passwd`、`/root/.ssh/id_rsa` 等。

**严重程度**: P0 — 服务器文件系统信息泄露
**修复建议**: 添加路径白名单验证，仅允许检查 `uploads_dir` 下的文件。

---

#### P0-06: 路径遍历检测使用字符串前缀匹配可被绕过

**文件**: `security_routes.py:247,295`, `security.py:249`, `file_service.py:156`

```python
if not str(resolved).startswith(str(upload_resolved)):
```

`startswith()` 前缀匹配可通过符号链接或类似目录名（如 `/app/uploads_evil/`）绕过。

**严重程度**: P0 — 潜在路径遍历绕过
**修复建议**: 使用 `pathlib.PurePath.is_relative_to()` (Python 3.9+) 或添加尾部分隔符后再比较。

---

### 架构缺陷

#### P0-07: 重复的异常类定义导致捕获失效

**文件**: `src/core/llm/exceptions.py` 与 `src/core/adapters/exceptions.py`

`ContextOverflowError` 和 `RepetitionLoopError` 在两个文件中被独立定义，且继承体系完全不同。`llm/exceptions.py` 中它们继承自 `Exception`，而 `adapters/exceptions.py` 中它们继承自 `LLMError -> TranslationError`。

- `ollama.py:15` 导入自 `llm/exceptions.py`
- `error_handler.py:29` 导入自 `adapters/exceptions.py`
- 当代码试图 `isinstance(e, ContextOverflowError)` 时，取决于导入来源不同，同一异常可能不被识别

**严重程度**: P0 — 异常处理可能完全失效
**修复建议**: 建立统一的异常层次结构，在 `src/core/exceptions.py` 中集中定义所有异常。

---

#### P0-08: MLX 子进程命令注入风险

**文件**: `src/core/llm/providers/mlx_direct.py:104-109`

```python
cmd = ["mlx_lm.generate", "--model", self.model, "--prompt", full_prompt, ...]
process = await asyncio.create_subprocess_exec(*cmd, ...)
```

`self.model` 和 `full_prompt`（包含用户可控的翻译文本）直接传入子进程参数。虽然 `create_subprocess_exec` 使用列表模式减轻了部分风险，但 `full_prompt` 可能非常长，直接作为命令行参数可能超过操作系统限制。

**严重程度**: P0 — 安全风险 + 功能可靠性问题
**修复建议**: 对 `model` 参数进行严格校验（白名单字符），限制 prompt 长度，考虑使用 Python API 直接调用 mlx-lm。

---

#### P0-09: 硬编码本地用户路径

**文件**: 7 个根级翻译脚本

多个脚本将用户路径硬编码为默认值，例如 `/Users/berton/Downloads/The Great Mathematical Problems (Ian Stewart) .epub`。这些脚本在除原作者之外的任何机器上都无法直接运行。

**涉及文件**: `merge_chapters_to_epub.py`, `translate_epub_by_chapter.py`, `translate_epub_isolated.py`, `translate_epub_parallel_robust.py`, `translate_epub_robust.py`, `translate_pdf_test.py`, `test_epub_mlx.py`

**严重程度**: P0 — 脚本在其他人环境下完全不可用
**修复建议**: 将所有文件路径改为命令行必需参数（不提供默认值）。

---

#### P0-10: `config.py` 模块级 `time.sleep(5)` 阻塞程序启动

**文件**: `src/config.py:72`

```python
import time
time.sleep(5)
```

当 `.env` 文件不存在时，整个 Python 进程被阻塞 5 秒。对于自动化测试、CI/CD 流水线或库导入场景不可接受。

**严重程度**: P0 — 影响 CI/CD 和自动化流程
**修复建议**: 改为警告日志，不阻塞。或者只在交互模式下暂停。

---

#### P0-11: 翻译状态响应泄露全部 API 密钥

**文件**: `src/api/blueprints/translation_routes.py:144`

```python
"config": job_data.get('config'),
```

GET `/api/translation/<translation_id>` 返回完整的 `config` 对象，其中包含所有 API 密钥。配合可预测的翻译 ID（基于时间戳），攻击者可获取所有已配置的 API 密钥。

**严重程度**: P0 — API 密钥泄露
**修复建议**: 在返回 config 之前，脱敏所有 API 密钥字段。

---

#### P0-12: OllamaProvider 缺 `_context_detector` 初始化

**文件**: `src/core/llm/providers/ollama.py:661-667`

```python
return await self._context_detector.detect_ollama(...)
```

`self._context_detector` 在 `__init__` 中从未初始化（对比 `openai.py:35` 有 `self._context_detector = ContextDetector()`）。调用此方法将抛出 `AttributeError`。

**严重程度**: P0 — 运行时异常
**修复建议**: 在 `OllamaProvider.__init__` 中添加 `self._context_detector = ContextDetector()`。

---

## P1 — 重要问题，下次迭代修复（19 个）

### 代码重复（最大技术债）

#### P1-01: Provider 间 ~1500 行重复代码

**涉及文件**: `ollama.py`, `openai.py`, `gemini.py`, `deepseek.py`, `mistral.py`, `openrouter.py`, `poe.py`, `mlx.py`

以下代码模式在几乎所有 provider 中重复出现（每个文件约 100-200 行）：
- `httpx.TimeoutException` 处理 + 重试逻辑
- `httpx.HTTPStatusError` 处理 + 429 速率限制检测
- `json.JSONDecodeError` 处理
- `Exception` 兜底处理
- 速率限制上下溢关键词检测列表

**严重程度**: P1 — 严重违反 DRY 原则
**修复建议**: 在 `LLMProvider` 基类中实现通用的 `_execute_with_retry()` 方法，各 provider 只需实现 `_make_request()` 和 `_parse_response()`。

---

#### P1-02: 4 个翻译脚本 ~200 行重复代码

**文件**: `translate_epub_by_chapter.py`, `translate_epub_isolated.py`, `translate_epub_parallel_robust.py`, `translate_epub_robust.py`

以下方法在 4 个文件中完全相同：
- `_extract_translatable_nodes()`
- `_translate_text()`
- `_replace_in_html()`
- `_log_callback()`
- MLX Provider 初始化代码

**严重程度**: P1 — 任何 bug 修复需要同步 4 个文件
**修复建议**: 将公共逻辑提取到 `src/core/epub/` 下的共享模块中。

---

#### P1-03: `_language_to_code()` 在两个文件中完全重复

**文件**: `mlx.py:191-208`, `mlx_direct.py:50-67`

完全相同的 `lang_map` 字典和方法体，且语言列表极其有限（仅 12 种）。

**修复建议**: 将语言映射提取到 `src/core/common/` 或 `src/utils/` 中的共享模块。

---

#### P1-04: `context_overflow_keywords` 列表在 6 个 provider 中分别定义且内容不同

**涉及文件**: `openai.py:220-222`, `deepseek.py:285-289`, `mistral.py:302-306`, `openrouter.py:355-358`, `poe.py:452-456`, `mlx.py:475-476`

每个列表略有不同，维护困难且容易遗漏新关键词。

**修复建议**: 统一定义在基类中，各 provider 可扩展而非重写。

---

### 安全 & 错误处理

#### P1-05: 翻译 ID 可预测 + 无授权检查

**文件**: `translation_routes.py:64`

```python
translation_id = f"trans_{int(time.time() * 1000)}"
```

仅基于毫秒时间戳，完全可预测。任何人可获取翻译任务的完整配置（含 API 密钥）、输出文件路径、中断或恢复翻译。

**修复建议**: 使用 `uuid.uuid4()` 生成不可预测的 ID，API 密钥不在状态查询中返回。

---

#### P1-06: 500 错误响应泄露内部实现细节

**文件**: `routes.py:70-75`, `file_routes.py` 6 处, `translation_routes.py:483-497`

```python
return jsonify({"error": "Internal server error", "details": str(error)}), 500
```

`str(error)` 可能包含文件路径、数据库结构、内部模块名称等敏感信息。

**修复建议**: 生产环境不返回异常详情，仅在 DEBUG 模式下返回 `details`。

---

#### P1-07: innerHTML 注入未转义的外部数据

**文件**: `src/web/static/js/index.js:177-201`

```javascript
ttsStatusText.innerHTML = `<span ...>${result.message}</span>`;
```

`result.message` 和 `result.error` 直接来自服务器响应，未经 `escapeHtml()` 处理就插入到 `innerHTML` 中，可能导致 XSS。

**修复建议**: 所有 `innerHTML` 中使用外部数据的地方都应使用 `DomHelpers.escapeHtml()` 进行转义。

---

#### P1-08: 裸 `except:` 吞掉所有异常

**文件**: `ollama.py:540`, `mlx.py:472`, `deepseek.py:198`, 4 个根级翻译脚本

```python
except:
    pass
```

会吞掉所有异常（包括 `KeyboardInterrupt`、`SystemExit`），使调试极其困难。

**修复建议**: 改为 `except Exception:` 并添加基本的错误日志。

---

#### P1-09: `SrtAdapter` O(n²) 性能问题

**文件**: `srt_adapter.py:95-120`

```python
async def save_unit_translation(self, unit_id: str, translated_content: str) -> bool:
    units = self.get_translation_units()  # 每次保存都重新生成全部单元
```

`get_translation_units()` 对每个块调用 `self.subtitles.index(subtitle)`（O(n) 操作），总复杂度 O(n²)。

**修复建议**: 缓存翻译单元或预先建立索引映射。

---

#### P1-10: `MAX_PLACEHOLDER_RETRIES` 重复定义，后者覆盖前者

**文件**: `config.py:173→317`, `config.py:176→320`

- 第173行定义 `MAX_PLACEHOLDER_RETRIES = 3`（注释说最大3次重试）
- 第317行定义 `MAX_PLACEHOLDER_RETRIES = 0`（覆盖了前面的值）

代码行为与注释不符，placeholder 验证功能被意外禁用。

**修复建议**: 删除第173-176行的重复定义，只保留第317-320行的定义，确保注释与值一致。

---

### 项目组织

#### P1-11: 7 个 test_*.py 散落在根目录

**文件**: `test_cleanup.py`, `test_mlx_provider.py`, `test_epub_mlx.py`, `test_epub_translation.py`, `test_simple_api.py`, `test_epub_refinement_progress.py`, `test_openai_server.py`

大部分是临时调试脚本而非真正的单元测试。根目录已有正规的 `tests/` 目录结构。

**修复建议**: 有价值的测试迁移到 `tests/` 对应子目录。纯临时调试脚本应删除或移入 `scripts/`。

---

#### P1-12: 14 个未跟踪脚本形成"影子代码库"

项目根目录包含至少 14 个未跟踪的 `.py` 文件，没有在 `src/` 结构中，也没有被项目文档索引。

**修复建议**: 将有长期价值的脚本移入 `scripts/` 目录并添加到版本管理。一次性实验脚本应删除或移入 `experiments/` 目录。

---

#### P1-13: `tests/` 被 `.gitignore` 排除

**文件**: `.gitignore:25`

`.gitignore` 中包含 `/tests` 规则，意味着整个测试目录不会被提交到版本库。但项目已有完整的测试结构和有价值的测试用例。

**修复建议**: 如果 tests 目录下的测试应该纳入版本管理，需从 `.gitignore` 中移除 `/tests` 规则。

---

#### P1-14: `MLXProvider._clean_model_artifacts()` 方法过长（80行）

**文件**: `mlx.py:224-305`

包含多层嵌套正则表达式匹配、多种策略的循环处理。正则表达式存在潜在的回溯风险。

**修复建议**: 将该方法拆分为多个小方法（`_remove_end_of_turn_tags()`, `_remove_thinking_prefix()`, `_remove_thinking_blocks()` 等）。

---

#### P1-15: `TranslationExtractor` 正则可能截断合法翻译内容

**文件**: `extraction.py:154-182`

第176行的正则会删除从文本开头到第一个 `</think` 标签之间的所有内容，包括合法的翻译内容。

**修复建议**: 改为只匹配开头位置的 `</think`（使用 `^` 锚定），或者添加更严格的上下文条件。

---

### 日志系统

#### P1-16: ANSI 颜色代码硬编码在业务逻辑中

**涉及文件**: 所有 provider 的 `generate()` 方法

颜色代码如 `RED = '\033[91m'` 在 `generate()` 方法内部被反复定义。如果日志输出到文件或非 TTY 终端，这些 ANSI 转义序列会造成垃圾字符。

**修复建议**: 使用 Python 标准 `logging` 模块，或创建统一的日志工具类来处理颜色输出。

---

#### P1-17: 三种日志方式混用

`print()`、`log_callback()`、`logging` 三种方式混用，无统一日志抽象。

**修复建议**: 统一使用 Python `logging` 模块或自定义的日志抽象层。

---

#### P1-18: `/api/security/info` 泄露服务器内部信息

**文件**: `security_routes.py:179-196`

该端点公开了上传目录的绝对路径、速率限制的内部参数等。这是一个无需认证的 GET 端点。

**修复建议**: 移除 `upload_directory` 字段。

---

#### P1-19: Flask 使用开发服务器

**文件**: `translation_api.py:250`

```python
socketio.run(app, debug=False, host=HOST, port=PORT, allow_unsafe_werkzeug=True)
```

`allow_unsafe_werkzeug=True` 表明使用了 Werkzeug 开发服务器，不适合生产环境。

**修复建议**: 生产环境应使用 gunicorn 或 waitress 等 WSGI 服务器。

---

## P2 — 一般问题（24 个）

### 安全类

| # | 问题 | 文件 | 建议 |
|---|------|------|------|
| P2-01 | 速率限制仅覆盖上传端点，其他 API 无限制 | `security_routes.py:29-34` | 为所有写操作端点添加速率限制 |
| P2-02 | `get_client_ip()` 信任 `X-Forwarded-For` 可被伪造 | `security.py:641-651` | 仅在确认反向代理时信任，否则仅用 `remote_addr` |
| P2-03 | 上传文件一次性读取到内存（100MB），高并发 OOM 风险 | `security_routes.py:50` | 使用流式处理或分块读取 |
| P2-04 | SQLite 线程本地连接从不关闭 | `database.py:37-46` | 添加连接池管理或超时机制 |
| P2-05 | `/api/settings` 缺 CSRF 保护 | `config_routes.py:879-938` | 添加 CSRF token 机制 |
| P2-06 | 翻译创建响应也返回完整 config | `translation_routes.py:104-108` | 移除 `config_received` 或脱敏 |
| P2-07 | WebSocket 全局广播所有任务状态 | `websocket.py:48` | 使用 SocketIO room 机制 |
| P2-08 | 18 处 `str(e)` 直接返回客户端 | `file_routes.py` 等多处 | 统一错误处理中间件 |

### 代码质量类

| # | 问题 | 文件 | 建议 |
|---|------|------|------|
| P2-09 | `OpenRouterProvider`/`PoeProvider` 用类变量跟踪成本（多实例数据混乱） | `openrouter.py:61-63`, `poe.py:75-77` | 改为实例变量 |
| P2-10 | `detect_repetition_loop()` O(n²) 复杂度 | `detection.py:56-93` | 考虑使用后缀数组或 Rabin-Karp |
| P2-11 | `TokenChunker` 硬编码 GPT-4 tokenizer 对其他模型不准 | `token_chunker.py:32` | 添加可选 `encoding` 参数 |
| P2-12 | 适配器 `except Exception: return False` 无日志 | `epub_adapter.py`, `srt_adapter.py`, `txt_adapter.py` | 至少记录异常信息 |
| P2-13 | `epub_adapter.py` 使用已弃用的 `tempfile.mktemp()` | `epub_adapter.py:228` | 改用 `NamedTemporaryFile(delete=False)` |
| P2-14 | 测试文件内重写被测代码而非导入 | `test_proportional_fallback_fix.py:9-88` | 从源模块导入被测函数 |
| P2-15 | `NIM Provider` 使用 `OpenAICompatibleProvider` 脆弱隐式依赖 | `factory.py:145-155` | 为 NIM 创建独立 provider |
| P2-16 | `config.py` 信任前端传入的 API 密钥无验证 | `config.py:509-537` | 添加基本格式验证 |

### 测试 & 工具类

| # | 问题 | 文件 | 建议 |
|---|------|------|------|
| P2-17 | `prompt_optimizer/` 完全无测试（10 个文件） | `prompt_optimizer/` | 为核心组件添加单元测试 |
| P2-18 | `benchmark/` 无独立测试 | `benchmark/` | 添加基本功能测试 |
| P2-19 | `benchmark/` 缺示例配置文件 | `benchmark/` | 添加 `config.example.yaml` |
| P2-20 | `translate_epub_isolated.py` 访问 `zip_out.fp` 在 Python 3.12+ 崩溃 | `translate_epub_isolated.py:219` | 使用 `close()` 后重新打开 |
| P2-21 | `translate_pdf_test.py` 运行时 `pip install` | `translate_pdf_test.py:17-20` | 移除自动安装，在 requirements.txt 声明 |
| P2-22 | `test_token_variation.py` 包含 Windows 硬编码路径 | `test_token_variation.py:170` | 改为命令行参数 |
| P2-23 | `.env` 需检查是否有被提交的历史 | `.env` | 运行 `git log --all --full-history -- .env` |
| P2-24 | `GeminiProvider` 缩进不一致 | `gemini.py:205-252` | 统一缩进为 4 空格倍数 |

---

## P3 — 改进建议（18 个）

### 安全加固

| # | 建议 | 说明 |
|---|------|------|
| P3-01 | 添加安全 HTTP 响应头 | `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy` 等 |
| P3-02 | 设置 Flask `MAX_CONTENT_LENGTH` | 作为上传大小第一层防御 |
| P3-03 | `/api/settings` 添加 CSRF 保护 | 使用 Flask-WTF 的 CSRFProtect |
| P3-04 | 审计前端 50 处 `innerHTML` | 确保所有外部数据都经过 `escapeHtml()` |

### 架构改进

| # | 建议 | 说明 |
|---|------|------|
| P3-05 | 拆分 `config.py`（595 行） | 分为 `settings.py`, `translation_config.py`, `placeholders.py` |
| P3-06 | Provider 添加 `__aenter__`/`__aexit__` | 支持异步上下文管理器 |
| P3-07 | 添加请求审计日志 | 记录所有写操作的调用者 IP、时间戳和操作类型 |
| P3-08 | `RetryManager` 不应操作 `CircuitBreaker` 私有属性 | 为 `CircuitBreaker` 添加 `reset()` 方法 |
| P3-09 | 添加 `pyproject.toml` | 消除 `sys.path` hack，规范化包管理 |
| P3-10 | `MLXProvider._build_messages()` 过长（~110行） | 拆分为 `_build_translategemma_messages()` 和 `_build_standard_messages()` |

### 测试 & 文档

| # | 建议 | 说明 |
|---|------|------|
| P3-11 | 补充测试边界用例 | 超大文件、损坏文件、空文件、全角/半角混合文本 |
| P3-12 | `test_epub_refinement_progress.py` 移入 `tests/` | 有价值的测试但位置不当 |
| P3-13 | `tests/standalone/` 重命名 | 不含 `test_` 前缀，避免与 pytest 混淆 |
| P3-14 | 统一 `scripts/fix_installation.py` | 引用的文件结构已过时 |
| P3-15 | `test_openai_server.py` 统一语言 | 法语注释与项目风格不一致 |

### 其他

| # | 建议 | 说明 |
|---|------|------|
| P3-16 | 统一日志系统 | 移除业务代码中的 ANSI 颜色代码 |
| P3-17 | 服务器会话 ID 改用 `uuid.uuid4()` | 当前基于秒级时间戳可预测 |
| P3-18 | WebSocket 日志过滤敏感字段 | 确保不包含 API 密钥 |

---

## 关键数据

```
文件总数:     191 个 Python 文件
代码总量:     ~52,896 行
P0 问题:      12 个（6 安全 + 4 架构 + 2 代码）
P1 问题:      19 个
P2 问题:      24 个
P3 建议:      18 个
问题总计:     73 个

测试覆盖率:   核心翻译逻辑有单元测试（tests/unit/epub/ 较完善）
              Provider 层 8 个提供商无单元测试
              API 路由层无测试
              prompt_optimizer/benchmark 无测试
              根目录 7 个 test_*.py 不在正规框架中

最大技术债:   Provider 代码重复（~1500行）
              根目录影子代码库（14个文件）
              API 密钥安全（多处泄露风险）
```

---

## 修复优先级建议

### 第一阶段：安全加固（1-2 天）

1. 轮换已泄露的 API 密钥，将硬编码密钥迁移到 `.env`
2. 限制 CORS 和 WebSocket origins
3. `to_dict()` 脱敏所有密钥字段
4. `/api/uploads/verify` 添加路径白名单
5. 移除 GET 方法中的 `api_key` 参数支持
6. 翻译状态响应中脱敏 config

### 第二阶段：架构修复（3-5 天）

1. 统一异常体系（合并 `llm/exceptions.py` 和 `adapters/exceptions.py`）
2. 将 Provider 通用逻辑上提到基类 `_execute_with_retry()`
3. 提取翻译脚本公共代码到 `src/core/epub/`
4. 清理根目录，脚本归入 `scripts/`
5. 修复 `OllamaProvider._context_detector` 缺失
6. 移除 `config.py` 模块级 `time.sleep(5)`

### 第三阶段：持续改进

1. 为 Provider 层补充单元测试
2. 统一日志系统（移除 ANSI 颜色硬编码）
3. 补充 `pyproject.toml` 规范化包管理
4. 为 `prompt_optimizer`/`benchmark` 补充测试
5. 审计前端 `innerHTML` XSS 风险

---

## 正面发现

审查中也发现了许多值得肯定的设计：

1. **清晰的模块划分** — `llm/providers/`、`adapters/`、`chunking/` 职责边界基本清晰
2. **良好的抽象设计** — `FormatAdapter` 和 `LLMProvider` 的抽象接口设计合理
3. **完善的错误恢复体系** — `ErrorHandler` + `RetryManager` + `ErrorRecoveryManager` 三层架构
4. **详尽的异常分类** — `adapters/exceptions.py` 中异常包含恢复标记
5. **翻译提取器** — `TranslationExtractor` 处理了多种边界情况
6. **文件上传安全** — `SecureFileHandler` 实现了多层验证（扩展名、MIME、内容扫描）
7. **SQLite 参数化查询** — 所有数据库操作使用 `?` 占位符，无 SQL 注入风险
8. **前端 XSS 防护意识** — 定义了 `DomHelpers.escapeHtml()` 并在大部分关键位置使用
9. **测试结构清晰** — `tests/` 目录 unit/integration/standalone 分层合理
10. **EPUB 测试充分** — `tests/unit/epub/` 下 8 个测试文件质量较高

---

*本报告由 AI 自动生成，建议结合人工复查确认所有发现。*

[根目录](../../CLAUDE.md) > [src](../) > **persistence**

# persistence 模块文档

## 模块职责

persistence模块负责翻译任务的持久化存储和恢复功能，提供：
- SQLite数据库管理
- 翻译检查点机制
- 任务状态跟踪
- 文件存储和恢复
- 断点续译支持

## 入口与启动

- 主入口：`database.py` - Database类
- 管理器：`checkpoint_manager.py` - CheckpointManager类
- 数据库位置：`data/jobs.db`
- 上传文件存储：`data/uploads/`

## 对外接口

### Database类
```python
# 初始化数据库
db = Database(db_path="data/jobs.db")

# 任务管理
db.create_job(translation_id, file_type, config)
db.get_job(translation_id)
db.update_job_progress(translation_id, ...)
db.delete_job(translation_id)

# 块管理
db.save_chunk(translation_id, chunk_index, ...)
db.get_chunks(translation_id)

# 上下文管理
db.update_translation_context(translation_id, context)
```

### CheckpointManager类
```python
# 初始化管理器
cpm = CheckpointManager(db_path="data/jobs.db")

# 任务生命周期
cpm.start_job(translation_id, file_type, config, input_file_path)
cpm.save_checkpoint(translation_id, ...)
cpm.load_checkpoint(translation_id)
cpm.mark_paused/completed/interrupted(translation_id)

# 恢复功能
cpm.get_resumable_jobs()
cpm.build_translated_output(translation_id, file_type)
```

## 关键依赖与配置

### 内部依赖
- `sqlite3` - 数据库引擎
- `pathlib` - 文件路径操作
- `json` - 数据序列化

### 外部依赖
- `src.core.srt_processor` - SRT文件重构
- `src.core.epub.epub_fast_processor` - EPUB文件重建

### 配置参数
```python
# 数据库配置
db_path = "data/jobs.db"  # SQLite数据库文件路径

# 文件存储配置
uploads_dir = "data/uploads"  # 上传文件存储目录
```

## 数据模型

### 数据库表结构

#### translation_jobs表
```sql
CREATE TABLE translation_jobs (
    translation_id TEXT PRIMARY KEY,      # 任务唯一标识
    status TEXT NOT NULL,                  # 状态: running/paused/completed/error
    file_type TEXT NOT NULL,              # 文件类型: txt/srt/epub
    config JSON NOT NULL,                 # 翻译配置
    progress JSON NOT NULL,               # 进度信息
    translation_context JSON,             # 翻译上下文
    created_at TIMESTAMP,                 # 创建时间
    updated_at TIMESTAMP,                 # 更新时间
    paused_at TIMESTAMP,                  # 暂停时间
    completed_at TIMESTAMP                # 完成时间
);
```

#### checkpoint_chunks表
```sql
CREATE TABLE checkpoint_chunks (
    translation_id TEXT NOT NULL,         # 任务ID
    chunk_index INTEGER NOT NULL,         # 块索引
    original_text TEXT NOT NULL,          # 原始文本
    translated_text TEXT,                 # 翻译文本
    chunk_data JSON,                      # 块元数据
    status TEXT NOT NULL,                 # 状态: completed/failed
    completed_at TIMESTAMP,               # 完成时间
    PRIMARY KEY (translation_id, chunk_index)
);
```

### 进度数据结构
```python
progress = {
    'current_chunk_index': int,    # 当前块索引
    'total_chunks': int,           # 总块数
    'completed_chunks': int,       # 已完成块数
    'failed_chunks': int,          # 失败块数
    'start_time': float            # 开始时间戳
}
```

## 测试与质量

### 测试策略

#### 1. 单元测试
- **Database类测试**
  - 数据库初始化和schema创建
  - 任务CRUD操作
  - 块存储和检索
  - 并发访问安全性
  - 事务完整性

- **CheckpointManager类测试**
  - 任务生命周期管理
  - 文件保存和恢复
  - 检查点保存和加载
  - 输出重构功能

#### 2. 集成测试
- **翻译流程集成**
  - 完整翻译任务的检查点保存
  - 任务中断后的恢复
  - 不同文件类型的输出重构

- **文件系统集成**
  - 临时文件保存
  - 大文件处理
  - 磁盘空间管理

#### 3. 性能测试
- **数据库性能**
  - 大量任务的查询性能
  - 块插入和更新速度
  - 索引效果验证

- **内存使用**
  - 大文件的内存占用
  - 长时间运行的内存泄漏检查

#### 4. 恢复测试
- **断点续译场景**
  - 正常暂停恢复
  - 异常中断恢复
  - 部分失败恢复
  - 配置变更恢复

### 测试文件结构
```
tests/
  persistence/
    test_database.py          # Database类测试
    test_checkpoint_manager.py # CheckpointManager类测试
    test_integration.py       # 集成测试
    fixtures/                 # 测试数据
      sample_jobs.json
      test_chunks.db
```

### 质量保证
- 线程安全的数据库操作
- 自动事务管理
- 错误处理和恢复
- 数据完整性约束
- 定期清理机制

## 常见问题 (FAQ)

### Q1: 如何处理数据库锁定问题？
A: Database类使用线程本地存储和RLock确保线程安全，每个线程获得独立连接。

### Q2: 检查点文件多大？
A: 取决于文本大小，通常每个块保存原文和译文，建议定期清理完成的任务。

### Q3: 如何迁移到新版本？
A: Database类会在初始化时自动创建表结构，新增字段需要手动迁移脚本。

### Q4: EPUB文件的恢复为什么有限制？
A: 标准EPUB模式需要复杂的XML结构重组，目前仅支持快速模式的文本恢复。

### Q5: 如何批量清理旧任务？
A: 使用CheckpointManager的cleanup_completed_job方法，或直接删除数据库记录。

## 相关文件清单

### 核心文件
- `database.py` - SQLite数据库管理类 (470行)
- `checkpoint_manager.py` - 检查点管理器 (528行)
- `__init__.py` - 模块初始化

### 数据文件
- `data/jobs.db` - SQLite数据库文件
- `data/uploads/{translation_id}/` - 上传文件存储目录

### 依赖模块
- `src/core/srt_processor.py` - SRT处理依赖
- `src/core/epub/epub_fast_processor.py` - EPUB处理依赖

## 变更记录 (Changelog)

### 2025-12-05
- 初始化persistence模块文档
- 详细记录数据库架构和API
- 完善测试策略和质量保证方案
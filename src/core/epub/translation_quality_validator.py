"""
翻译质量验证模块

用于检测翻译不完整或有问题的chunks。
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class QualityIssue:
    """质量问题"""
    severity: str  # 'error', 'warning', 'info'
    issue_type: str  # 'empty', 'incomplete', 'mixed_language', 'too_short', 'entity_preserved'
    message: str
    original_text: str
    translated_text: str
    metrics: Dict


class TranslationQualityValidator:
    """翻译质量验证器"""

    def __init__(
        self,
        source_language: str = "English",
        target_language: str = "Chinese",
        min_length_ratio: float = 0.1,  # 翻译文本最小长度比（翻译/原始）
        max_length_ratio: float = 2.0,  # 翻译文本最大长度比
        min_completeness: float = 0.5,  # 最小完整性（句子数比）
        allow_mixed_language: bool = False  # 是否允许混合语言（如保留人名）
    ):
        """
        初始化验证器

        Args:
            source_language: 源语言
            target_language: 目标语言
            min_length_ratio: 最小长度比（防止翻译过短）
            max_length_ratio: 最大长度比（防止翻译过长）
            min_completeness: 最小完整性（句子数比）
            allow_mixed_language: 是否允许混合语言
        """
        self.source_language = source_language
        self.target_language = target_language
        self.min_length_ratio = min_length_ratio
        self.max_length_ratio = max_length_ratio
        self.min_completeness = min_completeness
        self.allow_mixed_language = allow_mixed_language

        # 中文范围
        self.chinese_pattern = re.compile(r'[一-鿿]')
        # 英文范围
        self.english_pattern = re.compile(r'[a-zA-Z]')

    def validate_translation(
        self,
        original_text: str,
        translated_text: str,
        chunk_index: int = 0
    ) -> Tuple[bool, List[QualityIssue]]:
        """
        验证翻译质量

        Args:
            original_text: 原始文本
            translated_text: 翻译文本
            chunk_index: chunk索引

        Returns:
            (is_valid, issues) - 是否通过验证，问题列表
        """
        issues = []

        # 1. 检查空翻译
        if not translated_text or not translated_text.strip():
            issues.append(QualityIssue(
                severity='error',
                issue_type='empty',
                message='翻译结果为空',
                original_text=original_text[:100],
                translated_text=translated_text,
                metrics={'original_length': len(original_text), 'translated_length': 0}
            ))
            return False, issues

        # 2. 检查长度比
        length_ratio = len(translated_text) / max(len(original_text), 1)
        if length_ratio < self.min_length_ratio:
            issues.append(QualityIssue(
                severity='error',
                issue_type='too_short',
                message=f'翻译过短 (长度比: {length_ratio:.2f} < {self.min_length_ratio})',
                original_text=original_text[:100],
                translated_text=translated_text[:100],
                metrics={'length_ratio': length_ratio}
            ))
        elif length_ratio > self.max_length_ratio:
            issues.append(QualityIssue(
                severity='warning',
                issue_type='too_long',
                message=f'翻译过长 (长度比: {length_ratio:.2f} > {self.max_length_ratio})',
                original_text=original_text[:100],
                translated_text=translated_text[:100],
                metrics={'length_ratio': length_ratio}
            ))

        # 3. 检查语言混合
        has_chinese = bool(self.chinese_pattern.search(translated_text))
        has_english = bool(self.english_pattern.search(translated_text))

        if self.target_language == "Chinese":
            if not has_chinese:
                issues.append(QualityIssue(
                    severity='error',
                    issue_type='no_target_language',
                    message='翻译结果不包含中文',
                    original_text=original_text[:100],
                    translated_text=translated_text[:100],
                    metrics={'has_chinese': False, 'has_english': has_english}
                ))
            elif has_english and not self.allow_mixed_language:
                # 检查英文是否只是实体（人名、日期等）
                english_ratio = sum(1 for c in translated_text if self.english_pattern.match(c)) / len(translated_text)
                if english_ratio > 0.3:  # 如果英文超过30%
                    issues.append(QualityIssue(
                        severity='warning',
                        issue_type='mixed_language',
                        message=f'翻译包含大量英文 (英文占比: {english_ratio:.1%})',
                        original_text=original_text[:100],
                        translated_text=translated_text[:100],
                        metrics={'has_chinese': True, 'has_english': True, 'english_ratio': english_ratio}
                    ))

        # 4. 检查完整性（句子数比）
        original_sentences = self._count_sentences(original_text)
        translated_sentences = self._count_sentences(translated_text)

        if original_sentences > 0:
            completeness = min(translated_sentences / original_sentences, 1.0)
            if completeness < self.min_completeness:
                issues.append(QualityIssue(
                    severity='warning',
                    issue_type='incomplete',
                    message=f'翻译可能不完整 (句子数比: {completeness:.2f} < {self.min_completeness})',
                    original_text=original_text[:100],
                    translated_text=translated_text[:100],
                    metrics={
                        'original_sentences': original_sentences,
                        'translated_sentences': translated_sentences,
                        'completeness': completeness
                    }
                ))

        # 5. 检查是否完全相同（未翻译）
        if original_text.strip() == translated_text.strip():
            issues.append(QualityIssue(
                severity='error',
                issue_type='not_translated',
                message='翻译结果与原始文本完全相同',
                original_text=original_text[:100],
                translated_text=translated_text[:100],
                metrics={}
            ))

        # 判断是否通过验证
        has_errors = any(issue.severity == 'error' for issue in issues)
        return not has_errors, issues

    def _count_sentences(self, text: str) -> int:
        """计算句子数量（简单实现）"""
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', ' ', text)
        # 按句号、问号、感叹号、分号分割
        sentences = re.split(r'[。.!?！？；;]\s*', text)
        # 过滤空句子
        return len([s for s in sentences if s.strip()])

    def validate_chunk_batch(
        self,
        chunks: List[Dict],
        translated_chunks: List[str]
    ) -> Dict[str, any]:
        """
        批量验证多个chunks

        Args:
            chunks: 原始chunk列表
            translated_chunks: 翻译后的chunk列表

        Returns:
            验证结果统计
        """
        total_chunks = len(chunks)
        valid_chunks = 0
        all_issues = []

        for i, (chunk, translated) in enumerate(zip(chunks, translated_chunks)):
            original_text = chunk.get('text', '')
            is_valid, issues = self.validate_translation(original_text, translated, i)

            if is_valid:
                valid_chunks += 1
            else:
                all_issues.extend(issues)

        # 统计问题类型
        issue_counts = {}
        for issue in all_issues:
            issue_type = issue.issue_type
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        return {
            'total_chunks': total_chunks,
            'valid_chunks': valid_chunks,
            'invalid_chunks': total_chunks - valid_chunks,
            'validation_rate': valid_chunks / total_chunks if total_chunks > 0 else 0,
            'issue_counts': issue_counts,
            'all_issues': all_issues
        }

    def format_validation_report(
        self,
        validation_result: Dict,
        verbose: bool = False
    ) -> str:
        """
        格式化验证报告

        Args:
            validation_result: validate_chunk_batch的返回值
            verbose: 是否显示详细信息

        Returns:
            格式化的报告字符串
        """
        lines = []
        lines.append("=" * 80)
        lines.append("📊 翻译质量验证报告")
        lines.append("=" * 80)

        lines.append(f"总chunk数: {validation_result['total_chunks']}")
        lines.append(f"有效chunk: {validation_result['valid_chunks']}")
        lines.append(f"无效chunk: {validation_result['invalid_chunks']}")
        lines.append(f"验证通过率: {validation_result['validation_rate']:.1%}")

        if validation_result['issue_counts']:
            lines.append("\n问题统计:")
            for issue_type, count in validation_result['issue_counts'].items():
                lines.append(f"  {issue_type}: {count}")

        if verbose and validation_result['all_issues']:
            lines.append("\n详细问题列表:")
            for i, issue in enumerate(validation_result['all_issues'][:20], 1):  # 最多显示20个
                lines.append(f"\n{i}. [{issue.severity.upper()}] {issue.message}")
                lines.append(f"   类型: {issue.issue_type}")
                if issue.metrics:
                    lines.append(f"   指标: {issue.metrics}")

            if len(validation_result['all_issues']) > 20:
                lines.append(f"\n... 还有 {len(validation_result['all_issues']) - 20} 个问题")

        lines.append("=" * 80)
        return '\n'.join(lines)


# 便捷函数
def validate_translation_result(
    original_text: str,
    translated_text: str,
    source_language: str = "English",
    target_language: str = "Chinese"
) -> Tuple[bool, List[QualityIssue]]:
    """
    便捷的翻译验证函数

    Args:
        original_text: 原始文本
        translated_text: 翻译文本
        source_language: 源语言
        target_language: 目标语言

    Returns:
        (is_valid, issues)
    """
    validator = TranslationQualityValidator(
        source_language=source_language,
        target_language=target_language
    )
    return validator.validate_translation(original_text, translated_text)

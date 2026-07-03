"""
風格引擎
Style Engine

負責載入、解析和應用風格模板
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class StyleConfig:
    """風格配置"""
    name: str
    name_en: str
    description: str
    icon: str
    system_prompt: str
    vocabulary: Dict[str, Any] = field(default_factory=dict)
    sentence_rules: Dict[str, Any] = field(default_factory=dict)
    reference_materials: List[Dict[str, str]] = field(default_factory=list)
    chapter_templates: Dict[str, List[str]] = field(default_factory=dict)
    sub_styles: Dict[str, Dict[str, str]] = field(default_factory=dict)


class StyleEngine:
    """風格引擎"""

    # 支援的風格列表
    AVAILABLE_STYLES = [
        "ancient_chinese",   # 古文風
        "modern",            # 現代風
        "abstract",          # 抽象風
        "wuxia",             # 武俠風
        "scifi",             # 科幻風
        "mystery",           # 懸疑風
        "fantasy_eastern",   # 東方奇幻
        "fantasy_western",   # 西方奇幻
        "children",          # 兒童文學風
        "romance",           # 言情風
        "horror",            # 恐怖風
        "historical",        # 歷史風
        "urban",             # 都市風
        "noir",              # 黑色電影風
        "humor",             # 幽默風
        "war",               # 戰爭風
    ]

    # 風格顯示名稱
    STYLE_DISPLAY_NAMES = {
        "ancient_chinese": "📜 古文風",
        "modern": "🏙️ 現代風",
        "abstract": "🌀 抽象風",
        "wuxia": "⚔️ 武俠風",
        "scifi": "🚀 科幻風",
        "mystery": "🔍 懸疑風",
        "fantasy_eastern": "🐉 東方奇幻",
        "fantasy_western": "🧙 西方奇幻",
        "children": "🧒 兒童文學風",
        "romance": "💕 言情風",
        "horror": "👻 恐怖風",
        "historical": "📜 歷史風",
        "urban": "🏙️ 都市風",
        "noir": "🎬 黑色電影風",
        "humor": "😂 幽默風",
        "war": "⚔️ 戰爭風",
    }

    def __init__(self, styles_dir: Optional[Path] = None):
        """
        初始化風格引擎
        
        Args:
            styles_dir: 風格模板目錄
        """
        if styles_dir is None:
            styles_dir = Path(__file__).parent.parent / "templates" / "styles"
        
        self.styles_dir = Path(styles_dir)
        self._styles_cache: Dict[str, StyleConfig] = {}

    def get_style(self, style_name: str) -> StyleConfig:
        """
        獲取風格配置
        
        Args:
            style_name: 風格名稱
            
        Returns:
            風格配置
        """
        if style_name not in self._styles_cache:
            self._styles_cache[style_name] = self._load_style(style_name)
        return self._styles_cache[style_name]

    def _load_style(self, style_name: str) -> StyleConfig:
        """載入風格配置文件"""
        style_file = self.styles_dir / f"{style_name}.yaml"
        
        if not style_file.exists():
            raise ValueError(f"風格 '{style_name}' 不存在: {style_file}")
        
        with open(style_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return StyleConfig(
            name=data.get('name', style_name),
            name_en=data.get('name_en', ''),
            description=data.get('description', ''),
            icon=data.get('icon', '📝'),
            system_prompt=data.get('system_prompt', ''),
            vocabulary=data.get('vocabulary', {}),
            sentence_rules=data.get('sentence_rules', {}),
            reference_materials=data.get('reference_materials', []),
            chapter_templates=data.get('chapter_templates', {}),
            sub_styles=data.get('sub_styles', {}),
        )

    def get_system_prompt(self, style_name: str) -> str:
        """
        獲取風格的系統提示詞
        
        Args:
            style_name: 風格名稱
            
        Returns:
            系統提示詞
        """
        style = self.get_style(style_name)
        return style.system_prompt

    def get_vocabulary_replacements(self, style_name: str) -> Dict[str, List[str]]:
        """
        獲取詞彙替換表
        
        Args:
            style_name: 風格名稱
            
        Returns:
            詞彙替換表
        """
        style = self.get_style(style_name)
        return style.vocabulary.get('replacements', {})

    def get_banned_words(self, style_name: str) -> List[str]:
        """
        獲取禁用詞彙列表
        
        Args:
            style_name: 風格名稱
            
        Returns:
            禁用詞彙列表
        """
        style = self.get_style(style_name)
        return style.vocabulary.get('banned', [])

    def get_sentence_rules(self, style_name: str) -> Dict[str, Any]:
        """
        獲取句式規則
        
        Args:
            style_name: 風格名稱
            
        Returns:
            句式規則
        """
        style = self.get_style(style_name)
        return style.sentence_rules

    def get_reference_materials(self, style_name: str) -> List[Dict[str, str]]:
        """
        獲取參考素材
        
        Args:
            style_name: 風格名稱
            
        Returns:
            參考素材列表
        """
        style = self.get_style(style_name)
        return style.reference_materials

    def get_chapter_templates(self, style_name: str) -> Dict[str, List[str]]:
        """
        獲取章節模板
        
        Args:
            style_name: 風格名稱
            
        Returns:
            章節模板
        """
        style = self.get_style(style_name)
        return style.chapter_templates

    def get_sub_styles(self, style_name: str) -> Dict[str, Dict[str, str]]:
        """
        獲取子風格
        
        Args:
            style_name: 風格名稱
            
        Returns:
            子風格配置
        """
        style = self.get_style(style_name)
        return style.sub_styles

    def list_styles(self) -> List[Dict[str, str]]:
        """
        列出所有可用風格
        
        Returns:
            風格列表
        """
        styles = []
        for style_name in self.AVAILABLE_STYLES:
            try:
                style = self.get_style(style_name)
                styles.append({
                    "id": style_name,
                    "name": style.name,
                    "name_en": style.name_en,
                    "icon": style.icon,
                    "description": style.description[:100] + "..." if len(style.description) > 100 else style.description,
                })
            except Exception as e:
                # 如果載入失敗，跳過
                print(f"Warning: 無法載入風格 '{style_name}': {e}")
                continue
        return styles

    def get_style_display_name(self, style_name: str) -> str:
        """
        獲取風格的顯示名稱
        
        Args:
            style_name: 風格名稱
            
        Returns:
            顯示名稱
        """
        return self.STYLE_DISPLAY_NAMES.get(style_name, style_name)

    def get_random_reference(self, style_name: str) -> Optional[Dict[str, str]]:
        """
        隨機獲取一個參考素材
        
        Args:
            style_name: 風格名稱
            
        Returns:
            參考素材
        """
        import random
        materials = self.get_reference_materials(style_name)
        if materials:
            return random.choice(materials)
        return None


# ═══════════════════════════════════════════════════════════════
# 全局實例
# ═══════════════════════════════════════════════════════════════

_style_engine: Optional[StyleEngine] = None


def get_style_engine() -> StyleEngine:
    """獲取風格引擎實例"""
    global _style_engine
    if _style_engine is None:
        _style_engine = StyleEngine()
    return _style_engine

"""
後處理過濾器
Post-Processor for De-AI and Traditional Chinese

生成後的文字處理：
1. 去除AI套話
2. 簡體轉繁體
3. 台灣用語替換
4. 格式清理
"""

import re
from typing import Optional

try:
    import opencc
    HAS_OPENCC = True
except ImportError:
    HAS_OPENCC = False


class PostProcessor:
    """後處理過濾器"""

    # ──────────────────────────────────────────────
    # AI高頻詞替換表
    # ──────────────────────────────────────────────
    AI_PHRASES_DELETE = [
        # 直接刪除的詞語
        "值得注意的是",
        "值得一提的是",
        "眾所周知",
        "眾所皆知",
        "顯而易見",
        "毫無疑問",
        "不得不說",
        "必須承認",
        "事實上",
        "實際上",
    ]

    AI_PHRASES_REPLACE = {
        # 替換為更自然的表達
        "總的來說": "總之",
        "綜上所述": "總之",
        "不僅如此": "而且",
        "本質上": "其實",
        "從根本上說": "說到底",
        "在這個意義上": "這樣看來",
        "讓我們": "",  # 刪除
        "我們來看看": "",  # 刪除
        "我們需要": "",  # 刪除
        "換句話說": "也就是",
        "也就是說": "就是",
        "一方面...另一方面": "",  # 刪除
        "不僅...而且": "不但...還",
        "通過...的方式": "",  # 刪除
        "以...為例": "",  # 刪除
        "就...而言": "",  # 刪除
        "從...的角度來看": "",  # 刪除
        "在...的背景下": "",  # 刪除
        "隨著...的發展": "",  # 刪除
        "在...的過程中": "",  # 刪除
    }

    # ──────────────────────────────────────────────
    # 台灣用語對照表
    # ──────────────────────────────────────────────
    TAIWAN_TERMS = {
        # 科技
        "視頻": "影片",
        "網絡": "網路",
        "信息": "資訊",
        "質量": "品質",
        "硬件": "硬體",
        "軟件": "軟體",
        "服務器": "伺服器",
        "內存": "記憶體",
        "數據": "資料",
        "芯片": "晶片",
        "激光": "雷射",
        "博客": "部落格",
        "快遞": "宅配",
        "打印": "列印",
        "鼠標": "滑鼠",
        "光盤": "光碟",
        "U盤": "隨身碟",
        "視頻通話": "視訊",
        "外賣": "外送",
        
        # 交通
        "地鐵": "捷運",
        "出租車": "計程車",
        "公交車": "公車",
        "摩托車": "機車",
        "自行車": "腳踏車",
        
        # 日常
        "盒飯": "便當",
        "土豆": "馬鈴薯",  # 台灣的土豆是花生
        "鳳梨": "鳳梨",  # 保持
        "優酪乳": "優酪乳",  # 保持
        
        # 其他
        "視頻": "影片",
        "軟體": "軟體",  # 保持
        "硬體": "硬體",  # 保持
    }

    # ──────────────────────────────────────────────
    # 「了」字過度使用規則
    # ──────────────────────────────────────────────
    LE_PATTERNS = [
        # 連續多個「了」結尾
        (r'了{3,}$', '了'),
        # 每句都以「了」結尾（需要上下文判斷）
        # 這裡用簡單的統計方法
    ]

    def __init__(self, use_opencc: bool = True):
        """
        初始化後處理器
        
        Args:
            use_opencc: 是否使用OpenCC進行簡繁轉換
        """
        self.use_opencc = use_opencc and HAS_OPENCC
        
        # 初始化OpenCC轉換器
        if self.use_opencc:
            try:
                # s2t: 簡體到繁體
                # tw: 台灣用語
                self.converter = opencc.OpenCC('s2twp')
            except Exception:
                self.converter = None
                self.use_opencc = False
        else:
            self.converter = None

    def process(self, text: str, strength: float = 1.0) -> str:
        """
        處理文字
        
        Args:
            text: 原始文字
            strength: 處理強度 (0.0-1.0)
            
        Returns:
            處理後的文字
        """
        if not text:
            return text
        
        # 1. 去AI味
        text = self._remove_ai_phrases(text, strength)
        
        # 2. 簡轉繁
        if self.use_opencc:
            text = self._convert_to_traditional(text)
        
        # 3. 台灣用語替換
        text = self._apply_taiwan_terms(text, strength)
        
        # 4. 清理過度的「了」
        text = self._clean_le_particles(text, strength)
        
        # 5. 清理多餘空白
        text = self._clean_whitespace(text)
        
        return text

    def _remove_ai_phrases(self, text: str, strength: float) -> str:
        """移除AI套話"""
        if strength < 0.3:
            return text
        
        # 刪除直接刪除的詞語
        for phrase in self.AI_PHRASES_DELETE:
            if strength >= 0.8:
                # 強模式：直接刪除
                text = text.replace(phrase, "")
            elif strength >= 0.5:
                # 中模式：替換為空（可能會留下不自然的空白）
                text = text.replace(phrase, "")
            # 弱模式：不處理
        
        # 替換的詞語
        for original, replacement in self.AI_PHRASES_REPLACE.items():
            if strength >= 0.5:
                text = text.replace(original, replacement)
        
        return text

    def _convert_to_traditional(self, text: str) -> str:
        """簡體轉繁體"""
        if self.converter:
            try:
                return self.converter.convert(text)
            except Exception:
                return text
        return text

    def _apply_taiwan_terms(self, text: str, strength: float) -> str:
        """應用台灣用語"""
        if strength < 0.5:
            return text
        
        for simplified, traditional in self.TAIWAN_TERMS.items():
            text = text.replace(simplified, traditional)
        
        return text

    def _clean_le_particles(self, text: str, strength: float) -> str:
        """清理過度的「了」字"""
        if strength < 0.6:
            return text
        
        # 處理連續多個「了」結尾
        text = re.sub(r'了{3,}$', '了', text, flags=re.MULTILINE)
        
        # 統計「了」的使用頻率
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            if line.strip():
                # 計算這行中「了」的數量
                le_count = line.count('了')
                word_count = len(line)
                
                # 如果「了」的比例過高（超過20%），進行清理
                if word_count > 0 and le_count / word_count > 0.2:
                    # 保留第一個和最後一個「了」，刪除中間多餘的
                    # 這是一個簡單的策略，實際可能需要更複雜的NLP
                    pass
                
                cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    def _clean_whitespace(self, text: str) -> str:
        """清理多餘空白"""
        # 移除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        
        # 移除多餘的空行（保留最多一個空行）
        cleaned = []
        prev_empty = False
        for line in lines:
            if not line:
                if not prev_empty:
                    cleaned.append("")
                prev_empty = True
            else:
                cleaned.append(line)
                prev_empty = False
        
        # 移除開頭和結尾的空行
        while cleaned and not cleaned[0]:
            cleaned.pop(0)
        while cleaned and not cleaned[-1]:
            cleaned.pop()
        
        return '\n'.join(cleaned)


class StyleAwarePostProcessor(PostProcessor):
    """風格感知的後處理器"""

    # 不同風格的特殊處理規則
    STYLE_RULES = {
        "ancient_chinese": {
            # 古文風：允許文言詞彙
            "allow_classical": True,
            "le_tolerance": 0.1,  # 對「了」的容忍度更低
        },
        "modern": {
            # 現代風：口語化
            "allow_classical": False,
            "le_tolerance": 0.3,
        },
        "abstract": {
            # 抽象風：實驗性
            "allow_classical": False,
            "le_tolerance": 0.5,  # 對「了」的容忍度較高
        },
        "wuxia": {
            # 武俠風：半文半白
            "allow_classical": True,
            "le_tolerance": 0.2,
        },
    }

    def process(self, text: str, strength: float = 1.0, style: str = "modern") -> str:
        """
        根據風格處理文字
        
        Args:
            text: 原始文字
            strength: 處理強度
            style: 風格名稱
        """
        # 獲取風格規則
        style_rules = self.STYLE_RULES.get(style, {})
        
        # 應用風格特定的處理
        if style_rules.get("allow_classical"):
            # 古文風/武俠風：不處理文言詞彙
            pass
        
        # 調整「了」的容忍度
        le_tolerance = style_rules.get("le_tolerance", 0.3)
        
        # 基礎處理
        return super().process(text, strength)


# ═══════════════════════════════════════════════════════════════
# 便捷函數
# ═══════════════════════════════════════════════════════════════

# 全局實例
_default_processor = None
_style_processor = None


def get_post_processor(style_aware: bool = False) -> PostProcessor:
    """獲取後處理器實例"""
    global _default_processor, _style_processor
    
    if style_aware:
        if _style_processor is None:
            _style_processor = StyleAwarePostProcessor()
        return _style_processor
    else:
        if _default_processor is None:
            _default_processor = PostProcessor()
        return _default_processor


def clean_text(text: str, strength: float = 1.0, style: str = "modern") -> str:
    """
    清理文字的便捷函數
    
    Args:
        text: 原始文字
        strength: 處理強度 (0.0-1.0)
        style: 風格名稱
        
    Returns:
        清理後的文字
    """
    processor = get_post_processor(style_aware=True)
    return processor.process(text, strength=strength, style=style)

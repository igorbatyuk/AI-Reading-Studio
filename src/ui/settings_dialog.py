"""Settings dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.backup_service import BackupService
from ..core.database import Database
from ..core.i18n import UI_LANGUAGES, tr
from .api_usage_meter import ApiUsageMeter
from .styles import DARK_THEME, LIGHT_THEME
from ..core.apify_translate_usage import ApifyTranslateUsage
from ..core.azure_tts_usage import AzureTTSUsage
from ..core.deepl_translate_usage import DeepLTranslateUsage
from ..core.murf_tts_usage import MurfTTSUsage
from ..core.cartesia_tts_usage import CartesiaTTSUsage
from ..core.elevenlabs_tts_usage import ElevenLabsTTSUsage
from ..core.google_tts_usage import GoogleTTSUsage
from ..core.google_translate_usage import GoogleTranslateUsage
from ..core.secrets import (
    get_api_key,
    get_apify_api_token,
    get_azure_speech_key,
    get_deepl_api_key,
    get_murf_api_key,
    get_cartesia_api_key,
    get_elevenlabs_api_key,
    get_google_api_key,
    get_google_tts_api_key,
)
from ..core.tts_voices import (
    active_tts_engine,
    default_voice_for_tts_context,
    format_stored_voice,
    get_languages,
    get_voices_for_tts_context,
    is_voice_valid_for_tts_context,
    language_for_stored_voice,
    voice_preview_sample,
)
from ..core.voice_sort_prefs import (
    GENDER_FEMALE,
    GENDER_MALE,
    GENDER_MIX,
    PRESET_BOOK,
    PRESET_CUSTOM,
    PRESET_FAST,
    PRESET_NEWS,
    REGION_ANY,
    REGION_AU,
    REGION_UK,
    REGION_US,
    VoiceSortPrefs,
)
from ..core.tts_engine import TTSEngine
from ..core.tts_policy import is_slow_offline_engine, recommended_block_words
from ..core.user_errors import humanize_error
from ..core.text_splitter import BLOCK_WORD_OPTIONS
from ..core.word_highlight import (
    HIGHLIGHT_PALETTE_CUSTOM,
    HIGHLIGHT_PALETTE_PRESETS,
    HIGHLIGHT_STYLES,
    detect_palette_preset,
    normalize_highlight_style,
    palette_colors_as_settings,
    palette_preset_by_id,
)
from .settings_options import GOAL_BLOCK_OPTIONS, GOAL_TIME_OPTIONS
from .wheel_guard import disable_wheel_unless_focused


class SettingsDialog(QDialog):
    GOAL_BLOCK_OPTIONS = GOAL_BLOCK_OPTIONS
    GOAL_TIME_OPTIONS = GOAL_TIME_OPTIONS
    TRANSLATION_ENGINES = (
        "auto", "apify", "google", "deepl", "openai", "bergamot", "ollama", "free"
    )

    @staticmethod
    def _normalize_engine(value: str) -> str:
        if value in SettingsDialog.TRANSLATION_ENGINES:
            return value
        return "auto"
    MIN_WIDTH = 720
    MIN_HEIGHT = 560
    PREFERRED_WIDTH = 900
    PREFERRED_HEIGHT = 740

    def __init__(self, db: Database, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.backup = BackupService(db)
        self.library_cleared = False
        self.apify_usage = ApifyTranslateUsage(db)
        self.google_cloud_usage = GoogleTranslateUsage(db)
        self.deepl_usage = DeepLTranslateUsage(db)
        self.azure_tts_usage = AzureTTSUsage(db)
        self.google_tts_usage = GoogleTTSUsage(db)
        self.elevenlabs_tts_usage = ElevenLabsTTSUsage(db)
        self.cartesia_tts_usage = CartesiaTTSUsage(db)
        self.murf_tts_usage = MurfTTSUsage(db)
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.resize(self.PREFERRED_WIDTH, self.PREFERRED_HEIGHT)

        settings = db.get_all_settings()
        theme = settings.get("theme", "light")
        self.setStyleSheet(DARK_THEME if theme == "dark" else LIGHT_THEME)
        self._stored_elevenlabs_api_key = get_elevenlabs_api_key(
            settings.get("elevenlabs_api_key", "")
        )
        self._stored_cartesia_api_key = get_cartesia_api_key(
            settings.get("cartesia_api_key", "")
        )
        self._stored_murf_api_key = get_murf_api_key(
            settings.get("murf_api_key", "")
        )
        self.preview_tts = TTSEngine()
        self.preview_tts.set_app_dir(db.app_dir)
        self.preview_tts.generating_changed.connect(self._on_preview_generating)
        self.preview_tts.playback_error.connect(self._on_preview_error)
        self.preview_tts.sample_finished.connect(self._on_preview_finished)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        general_tab = QWidget()
        general_form = self._form_layout(general_tab)

        self.ui_lang_combo = QComboBox()
        self._wide_combo(self.ui_lang_combo)
        for code, name in UI_LANGUAGES:
            self.ui_lang_combo.addItem(name, code)
        current_ui = settings.get("ui_language", "uk")
        for i in range(self.ui_lang_combo.count()):
            if self.ui_lang_combo.itemData(i) == current_ui:
                self.ui_lang_combo.setCurrentIndex(i)
                break
        general_form.addRow(tr("settings.ui_language"), self.ui_lang_combo)

        self.theme_combo = QComboBox()
        self._wide_combo(self.theme_combo)
        self.theme_combo.addItem(tr("settings.theme.light"), "light")
        self.theme_combo.addItem(tr("settings.theme.dark"), "dark")
        current_theme = settings.get("theme", "light")
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_theme:
                self.theme_combo.setCurrentIndex(i)
                break
        general_form.addRow(tr("settings.theme"), self.theme_combo)

        self.update_check = QComboBox()
        self._wide_combo(self.update_check)
        self.update_check.addItem(tr("dialog.yes"), "1")
        self.update_check.addItem(tr("dialog.no"), "0")
        update_on = settings.get("update_check", "1")
        for i in range(self.update_check.count()):
            if self.update_check.itemData(i) == update_on:
                self.update_check.setCurrentIndex(i)
                break
        general_form.addRow(tr("settings.update_check"), self.update_check)

        self.github_repo_edit = QLineEdit(settings.get("github_repo", ""))
        self.github_repo_edit.setPlaceholderText("owner/repo")
        self.github_repo_edit.setMinimumWidth(320)
        general_form.addRow(tr("settings.github_repo"), self.github_repo_edit)

        repo_hint = self._hint_label(tr("settings.github_repo_hint"))
        general_form.addRow("", repo_hint)

        tabs.addTab(self._scroll_tab(general_tab), tr("settings.tab.general"))

        translation_tab = QWidget()
        translation_form = self._form_layout(translation_tab)

        intro = self._hint_label(tr("settings.translation_intro"))
        translation_form.addRow("", intro)

        self.language_combo = QComboBox()
        self._wide_combo(self.language_combo)
        for lang_code, lang_name in get_languages():
            self.language_combo.addItem(lang_name, lang_code)
        current_lang = settings.get("book_language", "en")
        stored_voice = settings.get("tts_voice", "")
        if stored_voice and ":" not in stored_voice:
            stored_voice = format_stored_voice("edge", stored_voice)
        if stored_voice and not is_voice_valid_for_tts_context(
            stored_voice,
            current_lang,
            settings.get("tts_mode", "auto"),
            settings.get("offline_engine", "system"),
            online_engine=settings.get("online_engine", "edge"),
            app_dir=db.app_dir,
            piper_model_path=settings.get("piper_model_path", ""),
            styletts2_model_path=settings.get("styletts2_model_path", ""),
        ):
            current_lang = language_for_stored_voice(stored_voice)
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == current_lang:
                self.language_combo.setCurrentIndex(i)
                break
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        translation_form.addRow(tr("settings.book_language"), self.language_combo)

        book_lang_hint = self._hint_label(tr("settings.book_language_hint"))
        translation_form.addRow("", book_lang_hint)

        self.translation_lang_combo = QComboBox()
        self._wide_combo(self.translation_lang_combo)
        for code, name in UI_LANGUAGES:
            self.translation_lang_combo.addItem(name, code)
        current_tr_lang = settings.get(
            "translation_language", settings.get("ui_language", "uk")
        )
        for i in range(self.translation_lang_combo.count()):
            if self.translation_lang_combo.itemData(i) == current_tr_lang:
                self.translation_lang_combo.setCurrentIndex(i)
                break
        translation_form.addRow(
            tr("settings.translation_language"), self.translation_lang_combo
        )

        legacy_provider = settings.get("translation_provider", "auto")
        self.block_provider_combo, self.block_provider_hint = (
            self._add_translation_provider_row(
                translation_form,
                tr("settings.translation_block_engine"),
                self._normalize_engine(
                    settings.get("translation_block_provider", legacy_provider)
                ),
                "settings.translation_block.hint",
            )
        )
        self.word_provider_combo, self.word_provider_hint = (
            self._add_translation_provider_row(
                translation_form,
                tr("settings.translation_word_engine"),
                self._normalize_engine(settings.get("translation_word_provider", "free")),
                "settings.translation_word.hint",
            )
        )
        self.selection_provider_combo, self.selection_provider_hint = (
            self._add_translation_provider_row(
                translation_form,
                tr("settings.translation_selection_engine"),
                self._normalize_engine(
                    settings.get("translation_selection_provider", "apify")
                ),
                "settings.translation_selection.hint",
            )
        )

        api_keys_hint = self._hint_label(tr("settings.translation_api_keys_hint"))
        translation_form.addRow("", api_keys_hint)

        tabs.addTab(self._scroll_tab(translation_tab), tr("settings.tab.translation"))

        reading_tab = QWidget()
        reading_form = self._form_layout(reading_tab)

        self.pdf_ocr_combo = QComboBox()
        self._wide_combo(self.pdf_ocr_combo)
        for mode, label_key in (
            ("auto", "settings.pdf_ocr.auto"),
            ("always", "settings.pdf_ocr.always"),
            ("off", "settings.pdf_ocr.off"),
        ):
            self.pdf_ocr_combo.addItem(tr(label_key), mode)
        ocr_mode = settings.get("pdf_ocr_mode", "auto")
        for i in range(self.pdf_ocr_combo.count()):
            if self.pdf_ocr_combo.itemData(i) == ocr_mode:
                self.pdf_ocr_combo.setCurrentIndex(i)
                break
        reading_form.addRow(tr("settings.pdf_ocr"), self.pdf_ocr_combo)

        self.pdf_ocr_pages_spin = QSpinBox()
        self.pdf_ocr_pages_spin.setRange(5, 120)
        self.pdf_ocr_pages_spin.setValue(int(settings.get("pdf_ocr_max_pages", "40")))
        reading_form.addRow(tr("settings.pdf_ocr_pages"), self.pdf_ocr_pages_spin)

        ocr_hint = self._hint_label(tr("settings.pdf_ocr_hint"))
        reading_form.addRow("", ocr_hint)

        self.goal_type_combo = QComboBox()
        for goal_type, label_key in (
            ("blocks", "settings.daily_goal_type.blocks"),
            ("time", "settings.daily_goal_type.time"),
        ):
            self.goal_type_combo.addItem(tr(label_key), goal_type)
        current_goal_type = settings.get("daily_goal_type", "blocks")
        for i in range(self.goal_type_combo.count()):
            if self.goal_type_combo.itemData(i) == current_goal_type:
                self.goal_type_combo.setCurrentIndex(i)
                break
        self.goal_type_combo.currentIndexChanged.connect(self._on_goal_type_changed)
        self._wide_combo(self.goal_type_combo)
        reading_form.addRow(tr("settings.daily_goal_type"), self.goal_type_combo)

        self.goal_combo = QComboBox()
        self._populate_goal_combo(settings)
        self._wide_combo(self.goal_combo)
        self.goal_combo.setMinimumWidth(310)
        reading_form.addRow(tr("settings.daily_goal"), self.goal_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 32)
        self.font_size_spin.setValue(int(settings.get("font_size", "18")))
        reading_form.addRow(tr("settings.font_size"), self.font_size_spin)

        self.font_combo = QComboBox()
        for font in ["Segoe UI", "Georgia", "Merriweather", "Literata", "Arial"]:
            self.font_combo.addItem(font)
        current_font = settings.get("font_family", "Segoe UI")
        idx = self.font_combo.findText(current_font)
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        reading_form.addRow(tr("settings.font"), self.font_combo)

        self.block_size_combo = QComboBox()
        current_block_target = int(settings.get("block_words_target", "55"))
        for words in BLOCK_WORD_OPTIONS:
            self.block_size_combo.addItem(
                tr("settings.block_size_words", n=words), words
            )
        if current_block_target in BLOCK_WORD_OPTIONS:
            idx = BLOCK_WORD_OPTIONS.index(current_block_target)
            self.block_size_combo.setCurrentIndex(idx)
        else:
            closest = min(
                BLOCK_WORD_OPTIONS,
                key=lambda w: abs(w - current_block_target),
            )
            self.block_size_combo.setCurrentIndex(
                BLOCK_WORD_OPTIONS.index(closest)
            )
        self.block_size_combo.currentIndexChanged.connect(self._update_offline_block_hint)
        reading_form.addRow(tr("settings.block_size"), self.block_size_combo)

        block_hint = self._hint_label(tr("settings.block_size_hint"))
        reading_form.addRow("", block_hint)

        self.offline_block_hint_label = self._hint_label("")
        reading_form.addRow("", self.offline_block_hint_label)

        self.line_width_spin = QSpinBox()
        self.line_width_spin.setRange(400, 3600)
        self.line_width_spin.setSingleStep(20)
        self.line_width_spin.setValue(int(settings.get("line_width", "680")))
        reading_form.addRow(tr("settings.line_width"), self.line_width_spin)

        tabs.addTab(self._scroll_tab(reading_tab), tr("settings.tab.reading"))

        highlight_tab = QWidget()
        highlight_form = self._form_layout(highlight_tab)

        self.word_highlight_combo = QComboBox()
        self._wide_combo(self.word_highlight_combo)
        self.word_highlight_combo.addItem(tr("dialog.yes"), "1")
        self.word_highlight_combo.addItem(tr("dialog.no"), "0")
        highlight_on = settings.get("word_highlight", "1")
        for i in range(self.word_highlight_combo.count()):
            if self.word_highlight_combo.itemData(i) == highlight_on:
                self.word_highlight_combo.setCurrentIndex(i)
                break
        highlight_form.addRow(tr("settings.word_highlight"), self.word_highlight_combo)

        highlight_hint = self._hint_label(tr("settings.word_highlight_hint"))
        highlight_form.addRow("", highlight_hint)

        self.word_highlight_style_combo = QComboBox()
        self._wide_combo(self.word_highlight_style_combo)
        for key in HIGHLIGHT_STYLES:
            self.word_highlight_style_combo.addItem(
                tr(f"settings.word_highlight_style.{key}"), key
            )
        current_style = normalize_highlight_style(
            settings.get("word_highlight_style", "gradient")
        )
        for i in range(self.word_highlight_style_combo.count()):
            if self.word_highlight_style_combo.itemData(i) == current_style:
                self.word_highlight_style_combo.setCurrentIndex(i)
                break
        highlight_form.addRow(
            tr("settings.word_highlight_style"), self.word_highlight_style_combo
        )

        style_hint = self._hint_label(tr("settings.word_highlight_style_hint"))
        highlight_form.addRow("", style_hint)

        self.whisper_align_combo = QComboBox()
        self._wide_combo(self.whisper_align_combo)
        for mode in ("auto", "on", "off"):
            self.whisper_align_combo.addItem(
                tr(f"settings.whisper_word_align.{mode}"), mode
            )
        whisper_mode = settings.get("whisper_word_align", "auto")
        for i in range(self.whisper_align_combo.count()):
            if self.whisper_align_combo.itemData(i) == whisper_mode:
                self.whisper_align_combo.setCurrentIndex(i)
                break
        highlight_form.addRow(
            tr("settings.whisper_word_align"), self.whisper_align_combo
        )
        whisper_hint = self._hint_label(tr("settings.whisper_word_align_hint"))
        highlight_form.addRow("", whisper_hint)

        self.highlight_palette_combo = QComboBox()
        self._wide_combo(self.highlight_palette_combo)
        for preset in HIGHLIGHT_PALETTE_PRESETS:
            self.highlight_palette_combo.addItem(
                tr(f"settings.word_highlight_palette.{preset.id}"), preset.id
            )
        self.highlight_palette_combo.addItem(
            tr("settings.word_highlight_palette.custom"), HIGHLIGHT_PALETTE_CUSTOM
        )
        saved_palette = settings.get("word_highlight_palette", "").strip()
        if not saved_palette or saved_palette == HIGHLIGHT_PALETTE_CUSTOM:
            saved_palette = detect_palette_preset(settings)
        palette_index = self.highlight_palette_combo.findData(saved_palette)
        self.highlight_palette_combo.setCurrentIndex(
            palette_index if palette_index >= 0 else 0
        )
        self.highlight_palette_combo.currentIndexChanged.connect(
            self._on_highlight_palette_changed
        )
        highlight_form.addRow(
            tr("settings.word_highlight_palette"), self.highlight_palette_combo
        )

        palette_hint = self._hint_label(tr("settings.word_highlight_palette_hint"))
        highlight_form.addRow("", palette_hint)

        self._hl_palette_sync_guard = False
        self._hl_color_refreshers: list = []
        self._hl_color_primary = self._add_color_picker(
            highlight_form,
            tr("settings.word_highlight_color"),
            settings.get("word_highlight_color", "#ffe08a"),
            on_changed=self._on_highlight_color_manual_change,
        )
        self._hl_color_secondary = self._add_color_picker(
            highlight_form,
            tr("settings.word_highlight_color_2"),
            settings.get("word_highlight_color_2", "#8ec5ff"),
            on_changed=self._on_highlight_color_manual_change,
        )
        self._hl_color_accent = self._add_color_picker(
            highlight_form,
            tr("settings.word_highlight_color_3"),
            settings.get("word_highlight_color_3", "#c4a8ff"),
            on_changed=self._on_highlight_color_manual_change,
        )
        self._hl_color_text = self._add_color_picker(
            highlight_form,
            tr("settings.word_highlight_text_color"),
            settings.get("word_highlight_text_color", "#1a1a1a"),
            on_changed=self._on_highlight_color_manual_change,
        )
        color_hint = self._hint_label(tr("settings.word_highlight_colors_hint"))
        highlight_form.addRow("", color_hint)

        tabs.addTab(self._scroll_tab(highlight_tab), tr("settings.tab.highlight"))

        audio_tab = QWidget()
        audio_form = self._form_layout(audio_tab)

        self.speed_combo = QComboBox()
        self._wide_combo(self.speed_combo)
        self.speed_combo.currentIndexChanged.connect(self._on_speech_speed_changed)
        audio_form.addRow(tr("settings.voice_speed"), self.speed_combo)

        voice_row = QHBoxLayout()
        self.voice_combo = QComboBox()
        self._wide_combo(self.voice_combo)
        self._stored_tts_voice = stored_voice
        voice_row.addWidget(self.voice_combo, stretch=1)
        self.voice_preview_btn = QPushButton(tr("settings.voice_preview"))
        self.voice_preview_btn.setObjectName("secondaryBtn")
        self.voice_preview_btn.setFixedWidth(110)
        self.voice_preview_btn.clicked.connect(self._preview_voice)
        voice_row.addWidget(self.voice_preview_btn)
        audio_form.addRow(tr("settings.voice"), voice_row)

        preview_hint = self._hint_label(tr("settings.voice_preview_hint"))
        audio_form.addRow("", preview_hint)
        voice_sort_hint = self._hint_label(tr("settings.voice_sort_hint"))
        audio_form.addRow("", voice_sort_hint)

        self._voice_sort_prefs_loaded = VoiceSortPrefs.from_settings(settings)
        self._voice_sort_custom_order_draft = dict(self._voice_sort_prefs_loaded.custom_order)

        self.tts_mode_combo = QComboBox()
        self._wide_combo(self.tts_mode_combo)
        for mode, label_key in (
            ("auto", "settings.tts_mode.auto"),
            ("online", "settings.tts_mode.online"),
            ("offline", "settings.tts_mode.offline"),
        ):
            self.tts_mode_combo.addItem(tr(label_key), mode)
        current_mode = settings.get("tts_mode", "auto")
        for i in range(self.tts_mode_combo.count()):
            if self.tts_mode_combo.itemData(i) == current_mode:
                self.tts_mode_combo.setCurrentIndex(i)
                break
        self.tts_mode_combo.currentIndexChanged.connect(self._on_tts_engine_changed)
        audio_form.addRow(tr("settings.tts_mode"), self.tts_mode_combo)

        self.online_engine_combo = QComboBox()
        self._wide_combo(self.online_engine_combo)
        for engine, label_key in (
            ("edge", "settings.online_engine.edge"),
            ("azure", "settings.online_engine.azure"),
            ("google", "settings.online_engine.google"),
            ("elevenlabs", "settings.online_engine.elevenlabs"),
            ("cartesia", "settings.online_engine.cartesia"),
            ("murf", "settings.online_engine.murf"),
        ):
            self.online_engine_combo.addItem(tr(label_key), engine)
        online_engine = settings.get("online_engine", "edge")
        for i in range(self.online_engine_combo.count()):
            if self.online_engine_combo.itemData(i) == online_engine:
                self.online_engine_combo.setCurrentIndex(i)
                break
        self.online_engine_combo.currentIndexChanged.connect(self._on_tts_engine_changed)
        self.online_engine_label = QLabel(tr("settings.online_engine"))
        audio_form.addRow(self.online_engine_label, self.online_engine_combo)

        self.offline_engine_combo = QComboBox()
        self._wide_combo(self.offline_engine_combo)
        for engine, label_key in (
            ("system", "settings.offline_engine.system"),
            ("piper", "settings.offline_engine.piper"),
            ("kokoro", "settings.offline_engine.kokoro"),
            ("xtts", "settings.offline_engine.xtts"),
            ("styletts2", "settings.offline_engine.styletts2"),
        ):
            self.offline_engine_combo.addItem(tr(label_key), engine)
        offline_engine = settings.get("offline_engine", "system")
        for i in range(self.offline_engine_combo.count()):
            if self.offline_engine_combo.itemData(i) == offline_engine:
                self.offline_engine_combo.setCurrentIndex(i)
                break
        self.offline_engine_combo.currentIndexChanged.connect(self._on_tts_engine_changed)
        self.offline_engine_label = QLabel(tr("settings.offline_engine"))
        audio_form.addRow(self.offline_engine_label, self.offline_engine_combo)

        self.piper_hint_label = self._hint_label(tr("settings.piper_hint"))
        audio_form.addRow("", self.piper_hint_label)
        self.piper_model_edit = QLineEdit("")
        self.piper_model_edit.hide()

        self.kokoro_hint_label = self._hint_label(tr("settings.kokoro_hint"))
        audio_form.addRow("", self.kokoro_hint_label)

        self.xtts_hint_label = self._hint_label(tr("settings.xtts_hint"))
        audio_form.addRow("", self.xtts_hint_label)

        self.styletts2_model_label = QLabel(tr("settings.styletts2_model"))
        styletts2_row = QHBoxLayout()
        self.styletts2_model_edit = QLineEdit(settings.get("styletts2_model_path", ""))
        self.styletts2_model_edit.setPlaceholderText("model.pth")
        self.styletts2_model_edit.setMinimumWidth(260)
        self.styletts2_model_edit.textChanged.connect(self._on_tts_engine_changed)
        styletts2_browse = QPushButton(tr("settings.styletts2_browse"))
        styletts2_browse.setFixedWidth(100)
        styletts2_browse.clicked.connect(self._browse_styletts2_model)
        styletts2_row.addWidget(self.styletts2_model_edit, stretch=1)
        styletts2_row.addWidget(styletts2_browse)
        self.styletts2_model_row = styletts2_row
        audio_form.addRow(self.styletts2_model_label, styletts2_row)

        self.styletts2_hint_label = self._hint_label(tr("settings.styletts2_hint"))
        audio_form.addRow("", self.styletts2_hint_label)

        word_section = self._hint_label(tr("settings.word_tts_section"))
        word_section.setStyleSheet("font-weight: 600; margin-top: 8px;")
        audio_form.addRow("", word_section)

        self.word_tts_combo = QComboBox()
        self._wide_combo(self.word_tts_combo)
        self.word_tts_combo.addItem(tr("dialog.yes"), "1")
        self.word_tts_combo.addItem(tr("dialog.no"), "0")
        word_tts = settings.get("word_tts", "1")
        for i in range(self.word_tts_combo.count()):
            if self.word_tts_combo.itemData(i) == word_tts:
                self.word_tts_combo.setCurrentIndex(i)
                break
        self.word_tts_combo.currentIndexChanged.connect(self._on_word_tts_engine_changed)
        audio_form.addRow(tr("settings.word_tts"), self.word_tts_combo)

        self.word_tts_profile_combo = QComboBox()
        self._wide_combo(self.word_tts_profile_combo)
        self.word_tts_profile_combo.addItem(
            tr("settings.word_tts_profile.same"), "same"
        )
        self.word_tts_profile_combo.addItem(
            tr("settings.word_tts_profile.custom"), "custom"
        )
        word_profile = settings.get("word_tts_profile", "same")
        for i in range(self.word_tts_profile_combo.count()):
            if self.word_tts_profile_combo.itemData(i) == word_profile:
                self.word_tts_profile_combo.setCurrentIndex(i)
                break
        self.word_tts_profile_combo.currentIndexChanged.connect(
            self._on_word_tts_engine_changed
        )
        self.word_tts_profile_label = QLabel(tr("settings.word_tts_profile"))
        audio_form.addRow(self.word_tts_profile_label, self.word_tts_profile_combo)

        stored_word_voice = settings.get("word_tts_voice", "")
        if stored_word_voice and ":" not in stored_word_voice:
            stored_word_voice = format_stored_voice("edge", stored_word_voice)
        self._stored_word_tts_voice = stored_word_voice

        self.word_tts_mode_combo = QComboBox()
        self._wide_combo(self.word_tts_mode_combo)
        for mode, label_key in (
            ("auto", "settings.tts_mode.auto"),
            ("online", "settings.tts_mode.online"),
            ("offline", "settings.tts_mode.offline"),
        ):
            self.word_tts_mode_combo.addItem(tr(label_key), mode)
        word_mode = settings.get("word_tts_mode", "auto")
        for i in range(self.word_tts_mode_combo.count()):
            if self.word_tts_mode_combo.itemData(i) == word_mode:
                self.word_tts_mode_combo.setCurrentIndex(i)
                break
        self.word_tts_mode_combo.currentIndexChanged.connect(
            self._on_word_tts_engine_changed
        )
        self.word_tts_mode_label = QLabel(tr("settings.word_tts_mode"))
        audio_form.addRow(self.word_tts_mode_label, self.word_tts_mode_combo)

        self.word_online_engine_combo = QComboBox()
        self._wide_combo(self.word_online_engine_combo)
        for engine, label_key in (
            ("edge", "settings.online_engine.edge"),
            ("azure", "settings.online_engine.azure"),
            ("google", "settings.online_engine.google"),
            ("elevenlabs", "settings.online_engine.elevenlabs"),
            ("cartesia", "settings.online_engine.cartesia"),
            ("murf", "settings.online_engine.murf"),
        ):
            self.word_online_engine_combo.addItem(tr(label_key), engine)
        word_online = settings.get("word_tts_online_engine", "edge")
        for i in range(self.word_online_engine_combo.count()):
            if self.word_online_engine_combo.itemData(i) == word_online:
                self.word_online_engine_combo.setCurrentIndex(i)
                break
        self.word_online_engine_combo.currentIndexChanged.connect(
            self._on_word_tts_engine_changed
        )
        self.word_online_engine_label = QLabel(tr("settings.word_online_engine"))
        audio_form.addRow(self.word_online_engine_label, self.word_online_engine_combo)

        self.word_offline_engine_combo = QComboBox()
        self._wide_combo(self.word_offline_engine_combo)
        for engine, label_key in (
            ("system", "settings.offline_engine.system"),
            ("piper", "settings.offline_engine.piper"),
            ("kokoro", "settings.offline_engine.kokoro"),
            ("xtts", "settings.offline_engine.xtts"),
            ("styletts2", "settings.offline_engine.styletts2"),
        ):
            self.word_offline_engine_combo.addItem(tr(label_key), engine)
        word_offline = settings.get("word_tts_offline_engine", "system")
        for i in range(self.word_offline_engine_combo.count()):
            if self.word_offline_engine_combo.itemData(i) == word_offline:
                self.word_offline_engine_combo.setCurrentIndex(i)
                break
        self.word_offline_engine_combo.currentIndexChanged.connect(
            self._on_word_tts_engine_changed
        )
        self.word_offline_engine_label = QLabel(tr("settings.word_offline_engine"))
        audio_form.addRow(self.word_offline_engine_label, self.word_offline_engine_combo)

        word_voice_row = QHBoxLayout()
        self.word_voice_combo = QComboBox()
        self._wide_combo(self.word_voice_combo)
        word_voice_row.addWidget(self.word_voice_combo, stretch=1)
        self.word_voice_preview_btn = QPushButton(tr("settings.voice_preview"))
        self.word_voice_preview_btn.setObjectName("secondaryBtn")
        self.word_voice_preview_btn.setFixedWidth(110)
        self.word_voice_preview_btn.clicked.connect(self._preview_word_voice)
        word_voice_row.addWidget(self.word_voice_preview_btn)
        self.word_voice_label = QLabel(tr("settings.word_voice"))
        audio_form.addRow(self.word_voice_label, word_voice_row)

        word_tts_hint = self._hint_label(tr("settings.word_tts_hint"))
        audio_form.addRow("", word_tts_hint)

        self._refresh_voices(self._stored_tts_voice)
        self._refresh_word_voices(self._stored_word_tts_voice)
        self._refresh_speed_combo()
        self._update_offline_engine_fields()
        self._update_word_tts_fields()
        self._update_offline_block_hint()

        tabs.addTab(self._scroll_tab(audio_tab), tr("settings.tab.audio"))

        voice_prefs_tab = QWidget()
        voice_prefs_form = self._form_layout(voice_prefs_tab)

        voice_prefs_intro = self._hint_label(tr("settings.voice_prefs.intro"))
        voice_prefs_form.addRow("", voice_prefs_intro)

        self.voice_sort_preset_combo = QComboBox()
        self._wide_combo(self.voice_sort_preset_combo)
        for preset, label_key in (
            (PRESET_BOOK, "settings.voice_prefs.preset.book"),
            (PRESET_NEWS, "settings.voice_prefs.preset.news"),
            (PRESET_FAST, "settings.voice_prefs.preset.fast"),
            (PRESET_CUSTOM, "settings.voice_prefs.preset.custom"),
        ):
            self.voice_sort_preset_combo.addItem(tr(label_key), preset)
        for i in range(self.voice_sort_preset_combo.count()):
            if self.voice_sort_preset_combo.itemData(i) == self._voice_sort_prefs_loaded.preset:
                self.voice_sort_preset_combo.setCurrentIndex(i)
                break
        self.voice_sort_preset_combo.currentIndexChanged.connect(
            self._on_voice_sort_preset_changed
        )
        voice_prefs_form.addRow(
            tr("settings.voice_prefs.preset"), self.voice_sort_preset_combo
        )

        self.voice_gender_pref_combo = QComboBox()
        self._wide_combo(self.voice_gender_pref_combo)
        for gender, label_key in (
            (GENDER_FEMALE, "settings.voice_prefs.gender.female"),
            (GENDER_MALE, "settings.voice_prefs.gender.male"),
            (GENDER_MIX, "settings.voice_prefs.gender.mix"),
        ):
            self.voice_gender_pref_combo.addItem(tr(label_key), gender)
        for i in range(self.voice_gender_pref_combo.count()):
            if self.voice_gender_pref_combo.itemData(i) == self._voice_sort_prefs_loaded.gender_pref:
                self.voice_gender_pref_combo.setCurrentIndex(i)
                break
        self.voice_gender_pref_combo.currentIndexChanged.connect(
            self._on_voice_sort_pref_changed
        )
        voice_prefs_form.addRow(
            tr("settings.voice_prefs.gender"), self.voice_gender_pref_combo
        )

        self.voice_region_pref_combo = QComboBox()
        self._wide_combo(self.voice_region_pref_combo)
        for region, label_key in (
            (REGION_US, "settings.voice_prefs.region.us"),
            (REGION_UK, "settings.voice_prefs.region.uk"),
            (REGION_AU, "settings.voice_prefs.region.au"),
            (REGION_ANY, "settings.voice_prefs.region.any"),
        ):
            self.voice_region_pref_combo.addItem(tr(label_key), region)
        for i in range(self.voice_region_pref_combo.count()):
            if (
                self.voice_region_pref_combo.itemData(i)
                == self._voice_sort_prefs_loaded.region_pref
            ):
                self.voice_region_pref_combo.setCurrentIndex(i)
                break
        self.voice_region_pref_combo.currentIndexChanged.connect(
            self._on_voice_sort_pref_changed
        )
        self.voice_region_pref_label = QLabel(tr("settings.voice_prefs.region"))
        voice_prefs_form.addRow(
            self.voice_region_pref_label, self.voice_region_pref_combo
        )

        self.voice_hide_unsuitable_check = QCheckBox(
            tr("settings.voice_prefs.hide_unsuitable")
        )
        self.voice_hide_unsuitable_check.setChecked(
            self._voice_sort_prefs_loaded.hide_unsuitable
        )
        self.voice_hide_unsuitable_check.toggled.connect(
            self._on_voice_sort_pref_changed
        )
        voice_prefs_form.addRow("", self.voice_hide_unsuitable_check)

        self.voice_show_recommended_badge_check = QCheckBox(
            tr("settings.voice_prefs.show_badge")
        )
        self.voice_show_recommended_badge_check.setChecked(
            self._voice_sort_prefs_loaded.show_recommended_badge
        )
        self.voice_show_recommended_badge_check.toggled.connect(
            self._on_voice_sort_pref_changed
        )
        voice_prefs_form.addRow("", self.voice_show_recommended_badge_check)

        self.voice_order_list = QListWidget()
        self.voice_order_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.voice_order_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.voice_order_list.setMinimumHeight(180)
        self.voice_order_list.model().rowsMoved.connect(self._on_custom_voice_order_changed)
        voice_prefs_form.addRow(tr("settings.voice_prefs.custom_order"), self.voice_order_list)
        voice_order_hint = self._hint_label(tr("settings.voice_prefs.custom_order_hint"))
        voice_prefs_form.addRow("", voice_order_hint)

        self._refresh_voice_order_list()
        self._update_voice_region_pref_visibility()

        tabs.addTab(
            self._scroll_tab(voice_prefs_tab), tr("settings.tab.voice_prefs")
        )

        data_tab = QWidget()
        data_layout = QVBoxLayout(data_tab)
        data_layout.setContentsMargins(4, 8, 4, 8)
        data_layout.setSpacing(14)

        data_info = self._hint_label(tr("settings.data_info"))
        data_layout.addWidget(data_info)

        data_btns = QHBoxLayout()
        export_btn = QPushButton(tr("settings.export"))
        export_btn.clicked.connect(self._export_backup)
        data_btns.addWidget(export_btn)

        import_btn = QPushButton(tr("settings.import"))
        import_btn.setObjectName("secondaryBtn")
        import_btn.clicked.connect(self._import_backup)
        data_btns.addWidget(import_btn)
        data_layout.addLayout(data_btns)

        sync_row = QHBoxLayout()
        self.sync_folder_edit = QLineEdit(settings.get("sync_folder", ""))
        self.sync_folder_edit.setPlaceholderText(tr("settings.sync_folder_hint"))
        self.sync_folder_edit.setMinimumWidth(280)
        sync_row.addWidget(self.sync_folder_edit, stretch=1)
        sync_browse_btn = QPushButton(tr("settings.sync_folder_browse"))
        sync_browse_btn.setObjectName("secondaryBtn")
        sync_browse_btn.setFixedWidth(110)
        sync_browse_btn.clicked.connect(self._browse_sync_folder)
        sync_row.addWidget(sync_browse_btn)
        data_layout.addWidget(QLabel(tr("settings.sync_folder")))
        data_layout.addLayout(sync_row)

        sync_hint = self._hint_label(tr("settings.sync_folder_hint"))
        data_layout.addWidget(sync_hint)

        sync_now_btn = QPushButton(tr("settings.sync_now"))
        sync_now_btn.setObjectName("secondaryBtn")
        sync_now_btn.clicked.connect(self._sync_now)
        data_layout.addWidget(sync_now_btn)

        clear_data_btn = QPushButton(tr("settings.clear_data"))
        clear_data_btn.setObjectName("secondaryBtn")
        clear_data_btn.clicked.connect(self._clear_user_data)
        data_layout.addWidget(clear_data_btn)

        clear_data_hint = self._hint_label(tr("settings.clear_data_hint"))
        data_layout.addWidget(clear_data_hint)
        data_layout.addStretch()

        tabs.addTab(self._scroll_tab(data_tab), tr("settings.tab.data"))

        api_tab = QWidget()
        api_form = self._form_layout(api_tab)
        self.api_key_edit = QLineEdit(get_api_key(settings.get("openai_api_key", "")))
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText(tr("settings.api_placeholder"))
        self.api_key_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.api_key"), self.api_key_edit)

        self.apify_api_token_edit = QLineEdit(
            get_apify_api_token(settings.get("apify_api_token", ""))
        )
        self.apify_api_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.apify_api_token_edit.setPlaceholderText(tr("settings.apify_api_placeholder"))
        self.apify_api_token_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.apify_api_token"), self.apify_api_token_edit)

        apify_key_hint = self._hint_label(tr("settings.apify_api_token_hint"))
        api_form.addRow("", apify_key_hint)

        self.apify_usage_meter = ApiUsageMeter()
        self._refresh_apify_usage_label()
        api_form.addRow(tr("settings.apify_api_usage"), self.apify_usage_meter)

        apify_usage_hint = self._hint_label(tr("settings.apify_api_usage_hint"))
        api_form.addRow("", apify_usage_hint)

        self.google_api_key_edit = QLineEdit(
            get_google_api_key(settings.get("google_api_key", ""))
        )
        self.google_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.google_api_key_edit.setPlaceholderText(tr("settings.google_api_placeholder"))
        self.google_api_key_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.google_api_key"), self.google_api_key_edit)

        google_key_hint = self._hint_label(tr("settings.google_api_key_hint"))
        api_form.addRow("", google_key_hint)

        self.google_usage_meter = ApiUsageMeter()
        self._refresh_google_usage_label()
        api_form.addRow(tr("settings.google_api_usage"), self.google_usage_meter)

        google_usage_hint = self._hint_label(tr("settings.google_api_usage_hint"))
        api_form.addRow("", google_usage_hint)

        self.deepl_api_key_edit = QLineEdit(
            get_deepl_api_key(settings.get("deepl_api_key", ""))
        )
        self.deepl_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepl_api_key_edit.setPlaceholderText(tr("settings.deepl_api_placeholder"))
        self.deepl_api_key_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.deepl_api_key"), self.deepl_api_key_edit)

        deepl_key_hint = self._hint_label(tr("settings.deepl_api_key_hint"))
        api_form.addRow("", deepl_key_hint)

        self.deepl_usage_meter = ApiUsageMeter()
        self._refresh_deepl_usage_label()
        api_form.addRow(tr("settings.deepl_api_usage"), self.deepl_usage_meter)

        deepl_usage_hint = self._hint_label(tr("settings.deepl_api_usage_hint"))
        api_form.addRow("", deepl_usage_hint)

        api_audio_heading = QLabel(tr("settings.api_audio_heading"))
        api_audio_heading.setStyleSheet("font-weight: 600; margin-top: 8px;")
        api_form.addRow("", api_audio_heading)

        self.azure_speech_key_edit = QLineEdit(
            get_azure_speech_key(settings.get("azure_speech_key", ""))
        )
        self.azure_speech_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.azure_speech_key_edit.setPlaceholderText(tr("settings.azure_speech_key_placeholder"))
        self.azure_speech_key_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.azure_speech_key"), self.azure_speech_key_edit)

        self.azure_speech_region_edit = QLineEdit(
            settings.get("azure_speech_region", "")
        )
        self.azure_speech_region_edit.setPlaceholderText("eastus, westeurope…")
        self.azure_speech_region_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.azure_speech_region"), self.azure_speech_region_edit)

        azure_key_hint = self._hint_label(tr("settings.azure_speech_key_hint"))
        api_form.addRow("", azure_key_hint)

        self.azure_tts_usage_meter = ApiUsageMeter()
        self._refresh_azure_tts_usage_label()
        api_form.addRow(tr("settings.azure_tts_usage"), self.azure_tts_usage_meter)

        azure_usage_hint = self._hint_label(tr("settings.azure_tts_usage_hint"))
        api_form.addRow("", azure_usage_hint)

        self.google_tts_api_key_edit = QLineEdit(
            get_google_tts_api_key(settings.get("google_tts_api_key", ""))
        )
        self.google_tts_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.google_tts_api_key_edit.setPlaceholderText(tr("settings.google_tts_api_placeholder"))
        self.google_tts_api_key_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.google_tts_api_key"), self.google_tts_api_key_edit)

        google_tts_key_hint = self._hint_label(tr("settings.google_tts_api_key_hint"))
        api_form.addRow("", google_tts_key_hint)

        self.google_tts_usage_meter = ApiUsageMeter()
        self._refresh_google_tts_usage_label()
        api_form.addRow(tr("settings.google_tts_usage"), self.google_tts_usage_meter)

        google_tts_usage_hint = self._hint_label(tr("settings.google_tts_usage_hint"))
        api_form.addRow("", google_tts_usage_hint)

        self.elevenlabs_api_key_edit = QLineEdit(
            get_elevenlabs_api_key(settings.get("elevenlabs_api_key", ""))
        )
        self.elevenlabs_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.elevenlabs_api_key_edit.setPlaceholderText(
            tr("settings.elevenlabs_api_placeholder")
        )
        self.elevenlabs_api_key_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.elevenlabs_api_key"), self.elevenlabs_api_key_edit)

        elevenlabs_key_hint = self._hint_label(tr("settings.elevenlabs_api_key_hint"))
        api_form.addRow("", elevenlabs_key_hint)

        self.elevenlabs_tts_usage_meter = ApiUsageMeter()
        elevenlabs_usage_row = QHBoxLayout()
        elevenlabs_usage_row.addWidget(self.elevenlabs_tts_usage_meter, stretch=1)
        self.elevenlabs_refresh_btn = QPushButton(tr("settings.elevenlabs_refresh_usage"))
        self.elevenlabs_refresh_btn.setObjectName("secondaryBtn")
        self.elevenlabs_refresh_btn.setFixedWidth(110)
        self.elevenlabs_refresh_btn.clicked.connect(self._refresh_elevenlabs_usage_from_api)
        elevenlabs_usage_row.addWidget(self.elevenlabs_refresh_btn)
        api_form.addRow(tr("settings.elevenlabs_tts_usage"), elevenlabs_usage_row)

        elevenlabs_usage_hint = self._hint_label(tr("settings.elevenlabs_tts_usage_hint"))
        api_form.addRow("", elevenlabs_usage_hint)

        self.cartesia_api_key_edit = QLineEdit(
            get_cartesia_api_key(settings.get("cartesia_api_key", ""))
        )
        self.cartesia_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.cartesia_api_key_edit.setPlaceholderText(
            tr("settings.cartesia_api_placeholder")
        )
        self.cartesia_api_key_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.cartesia_api_key"), self.cartesia_api_key_edit)

        cartesia_key_hint = self._hint_label(tr("settings.cartesia_api_key_hint"))
        api_form.addRow("", cartesia_key_hint)

        self.cartesia_tts_usage_meter = ApiUsageMeter()
        self._refresh_cartesia_tts_usage_label()
        api_form.addRow(tr("settings.cartesia_tts_usage"), self.cartesia_tts_usage_meter)

        cartesia_usage_hint = self._hint_label(tr("settings.cartesia_tts_usage_hint"))
        api_form.addRow("", cartesia_usage_hint)

        self.murf_api_key_edit = QLineEdit(
            get_murf_api_key(settings.get("murf_api_key", ""))
        )
        self.murf_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.murf_api_key_edit.setPlaceholderText(tr("settings.murf_api_placeholder"))
        self.murf_api_key_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.murf_api_key"), self.murf_api_key_edit)

        murf_key_hint = self._hint_label(tr("settings.murf_api_key_hint"))
        api_form.addRow("", murf_key_hint)

        self.murf_tts_usage_meter = ApiUsageMeter()
        self._refresh_murf_tts_usage_label()
        api_form.addRow(tr("settings.murf_tts_usage"), self.murf_tts_usage_meter)

        murf_usage_hint = self._hint_label(tr("settings.murf_tts_usage_hint"))
        api_form.addRow("", murf_usage_hint)

        self.ollama_url_edit = QLineEdit(
            settings.get("ollama_url", "http://127.0.0.1:11434")
        )
        self.ollama_url_edit.setPlaceholderText("http://127.0.0.1:11434")
        self.ollama_url_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.ollama_url"), self.ollama_url_edit)

        self.ollama_model_edit = QLineEdit(settings.get("ollama_model", ""))
        self.ollama_model_edit.setPlaceholderText("llama3.2, mistral, gemma2…")
        self.ollama_model_edit.setMinimumWidth(320)
        api_form.addRow(tr("settings.ollama_model"), self.ollama_model_edit)

        ollama_hint = self._hint_label(tr("settings.ollama_hint"))
        api_form.addRow("", ollama_hint)

        api_info = self._hint_label(tr("settings.api_info"))
        api_form.addRow("", api_info)

        tabs.addTab(self._scroll_tab(api_tab), tr("settings.tab.api"))

        tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(tabs, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("dialog.save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("dialog.cancel"))
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._fit_to_parent(parent)
        disable_wheel_unless_focused(self)
        self._refresh_elevenlabs_tts_usage_label()
        self._refresh_cartesia_tts_usage_label()
        self._refresh_murf_tts_usage_label()

    def _refresh_elevenlabs_usage_from_api(self) -> None:
        key = self.elevenlabs_api_key_edit.text().strip()
        if not key:
            self._refresh_elevenlabs_tts_usage_label()
            return
        self.elevenlabs_refresh_btn.setEnabled(False)
        synced = self.elevenlabs_tts_usage.sync_from_api(key, force=True)
        self._refresh_elevenlabs_tts_usage_label()
        self.elevenlabs_refresh_btn.setEnabled(True)
        if not synced:
            QMessageBox.warning(
                self,
                tr("settings.elevenlabs_tts_usage"),
                tr("settings.elevenlabs_sync_failed"),
            )

    def _apply_usage_meter(
        self, meter: ApiUsageMeter, stats: dict[str, int | str], fmt_key: str, **extra
    ) -> None:
        meter.set_usage(
            used=int(stats["used"]),
            limit=int(stats["limit"]),
            remaining=int(stats["remaining"]),
            percent=int(stats["percent"]),
            detail=tr(
                fmt_key,
                remaining=stats["remaining"],
                limit=stats["limit"],
                used=stats["used"],
                month=stats["month"],
                percent=stats["percent"],
                **extra,
            ),
        )

    def _refresh_apify_usage_label(self) -> None:
        stats = self.apify_usage.status()
        self._apply_usage_meter(
            self.apify_usage_meter, stats, "settings.apify_api_usage_fmt"
        )

    def _refresh_google_usage_label(self) -> None:
        stats = self.google_cloud_usage.status()
        self._apply_usage_meter(
            self.google_usage_meter, stats, "settings.google_api_usage_fmt"
        )

    def _refresh_deepl_usage_label(self) -> None:
        stats = self.deepl_usage.status()
        self._apply_usage_meter(
            self.deepl_usage_meter, stats, "settings.deepl_api_usage_fmt"
        )

    def _refresh_azure_tts_usage_label(self) -> None:
        stats = self.azure_tts_usage.status()
        self._apply_usage_meter(
            self.azure_tts_usage_meter, stats, "settings.azure_tts_usage_fmt"
        )

    def _refresh_google_tts_usage_label(self) -> None:
        stats = self.google_tts_usage.status()
        self._apply_usage_meter(
            self.google_tts_usage_meter, stats, "settings.google_tts_usage_fmt"
        )

    def _refresh_cartesia_tts_usage_label(self) -> None:
        stats = self.cartesia_tts_usage.status()
        self._apply_usage_meter(
            self.cartesia_tts_usage_meter, stats, "settings.cartesia_tts_usage_fmt"
        )

    def _refresh_murf_tts_usage_label(self) -> None:
        stats = self.murf_tts_usage.status()
        if stats.get("source") == "api":
            self._apply_usage_meter(
                self.murf_tts_usage_meter,
                stats,
                "settings.murf_tts_usage_fmt_api",
                local_used=stats.get("local_used", stats["used"]),
            )
        else:
            self._apply_usage_meter(
                self.murf_tts_usage_meter, stats, "settings.murf_tts_usage_fmt"
            )

    def _refresh_elevenlabs_tts_usage_label(self) -> None:
        stats = self.elevenlabs_tts_usage.status()
        if stats.get("source") == "api":
            self._apply_usage_meter(
                self.elevenlabs_tts_usage_meter,
                stats,
                "settings.elevenlabs_tts_usage_fmt_api",
                local_used=stats.get("local_used", 0),
            )
        else:
            self._apply_usage_meter(
                self.elevenlabs_tts_usage_meter,
                stats,
                "settings.elevenlabs_tts_usage_fmt"
            )

    def _add_translation_provider_row(
        self,
        form: QFormLayout,
        label: str,
        current: str,
        hint_prefix: str,
    ) -> tuple[QComboBox, QLabel]:
        combo = QComboBox()
        self._wide_combo(combo)
        for mode in self.TRANSLATION_ENGINES:
            combo.addItem(tr(f"settings.translation_engine.{mode}"), mode)
        for i in range(combo.count()):
            if combo.itemData(i) == current:
                combo.setCurrentIndex(i)
                break
        hint = self._hint_label("")

        def update_hint() -> None:
            mode = combo.currentData() or "auto"
            hint.setText(tr(f"{hint_prefix}.{mode}"))

        combo.currentIndexChanged.connect(lambda _index: update_hint())
        update_hint()
        form.addRow(label, combo)
        form.addRow("", hint)
        return combo, hint

    @staticmethod
    def _form_layout(parent: QWidget) -> QFormLayout:
        form = QFormLayout(parent)
        form.setSpacing(12)
        form.setContentsMargins(8, 12, 12, 16)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        return form

    @staticmethod
    def _scroll_tab(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _wide_combo(combo: QComboBox) -> None:
        combo.setMinimumWidth(360)
        combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    @staticmethod
    def _hint_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("hintLabel")
        label.setWordWrap(True)
        label.setMinimumWidth(420)
        return label

    def _add_color_picker(
        self,
        form: QFormLayout,
        label: str,
        initial: str,
        *,
        on_changed=None,
    ) -> QColor:
        color = QColor(initial if initial.startswith("#") else f"#{initial}")
        if not color.isValid():
            color = QColor("#ffe08a")
        button = QPushButton(color.name())
        button.setFixedHeight(32)
        button.setMinimumWidth(120)

        def refresh() -> None:
            button.setText(color.name())
            luminance = (
                0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
            )
            fg = "#111" if luminance > 150 else "#f5f5f5"
            button.setStyleSheet(
                f"background-color: {color.name()}; color: {fg};"
                " border: 1px solid #888; border-radius: 4px;"
            )

        def pick() -> None:
            chosen = QColorDialog.getColor(color, self, label)
            if chosen.isValid():
                color.setRgb(chosen.rgb())
                refresh()
                if on_changed is not None:
                    on_changed()

        button.clicked.connect(pick)
        refresh()
        form.addRow(label, button)
        if not hasattr(self, "_hl_color_refreshers"):
            self._hl_color_refreshers = []
        self._hl_color_refreshers.append(refresh)
        return color

    def _set_highlight_palette_combo(self, palette_id: str) -> None:
        index = self.highlight_palette_combo.findData(palette_id)
        if index < 0:
            index = self.highlight_palette_combo.findData(HIGHLIGHT_PALETTE_CUSTOM)
        self._hl_palette_sync_guard = True
        self.highlight_palette_combo.setCurrentIndex(index)
        self._hl_palette_sync_guard = False

    def _apply_highlight_palette(self, palette_id: str) -> None:
        preset = palette_preset_by_id(palette_id)
        if preset is None:
            return
        colors = palette_colors_as_settings(preset)
        self._hl_color_primary.setNamedColor(colors["word_highlight_color"])
        self._hl_color_secondary.setNamedColor(colors["word_highlight_color_2"])
        self._hl_color_accent.setNamedColor(colors["word_highlight_color_3"])
        self._hl_color_text.setNamedColor(colors["word_highlight_text_color"])
        self._refresh_highlight_color_buttons()

    def _refresh_highlight_color_buttons(self) -> None:
        for refresh in getattr(self, "_hl_color_refreshers", []):
            refresh()

    def _on_highlight_palette_changed(self) -> None:
        if self._hl_palette_sync_guard:
            return
        palette_id = self.highlight_palette_combo.currentData()
        if palette_id and palette_id != HIGHLIGHT_PALETTE_CUSTOM:
            self._apply_highlight_palette(palette_id)

    def _on_highlight_color_manual_change(self) -> None:
        if self._hl_palette_sync_guard:
            return
        settings = {
            "word_highlight_color": self._hl_color_primary.name(),
            "word_highlight_color_2": self._hl_color_secondary.name(),
            "word_highlight_color_3": self._hl_color_accent.name(),
            "word_highlight_text_color": self._hl_color_text.name(),
        }
        self._set_highlight_palette_combo(detect_palette_preset(settings))

    def _fit_to_parent(self, parent) -> None:
        if parent is None:
            return
        max_w = max(self.MIN_WIDTH, min(self.PREFERRED_WIDTH, int(parent.width() * 0.82)))
        max_h = max(self.MIN_HEIGHT, min(self.PREFERRED_HEIGHT, int(parent.height() * 0.9)))
        self.resize(max_w, max_h)
        frame = self.frameGeometry()
        center = parent.frameGeometry().center()
        frame.moveCenter(center)
        self.move(frame.topLeft())

    def _browse_piper_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("settings.piper_model"),
            "",
            "ONNX model (*.onnx);;All files (*.*)",
        )
        if path:
            self.piper_model_edit.setText(path)
            self._on_tts_engine_changed()

    def _browse_styletts2_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("settings.styletts2_model"),
            "",
            "PyTorch model (*.pth);;All files (*.*)",
        )
        if path:
            self.styletts2_model_edit.setText(path)
            self._on_tts_engine_changed()

    def _refresh_speed_combo(self, *, apply_live: bool = False) -> None:
        from ..core.tts_speed import (
            allowed_ui_speech_rates,
            clamp_ui_speech_rate_for_context,
            speech_rate_limits_for_tts_context,
        )

        _lang, tts_mode, online_engine, offline_engine, _, _ = self._tts_context()
        min_rate, max_rate = speech_rate_limits_for_tts_context(
            tts_mode, offline_engine, online_engine
        )
        allowed = allowed_ui_speech_rates(min_rate, max_rate)
        if not allowed:
            allowed = allowed_ui_speech_rates(1.0, 1.0)

        previous = float(
            self.speed_combo.currentData()
            or self.db.get_setting("tts_speed", "1.0")
        )
        target = clamp_ui_speech_rate_for_context(
            previous, tts_mode, offline_engine, online_engine
        )

        self.speed_combo.blockSignals(True)
        self.speed_combo.clear()
        for speed in sorted(allowed.keys()):
            self.speed_combo.addItem(f"{speed}x", speed)
        for index in range(self.speed_combo.count()):
            if self.speed_combo.itemData(index) == target:
                self.speed_combo.setCurrentIndex(index)
                break
        self.speed_combo.blockSignals(False)

        if target != previous or apply_live:
            self._on_speech_speed_changed()

    def _tts_context(self) -> tuple[str, str, str, str, str, str]:
        lang_code = self.language_combo.currentData() or "en"
        tts_mode = self.tts_mode_combo.currentData() or "auto"
        online_engine = self.online_engine_combo.currentData() or "edge"
        offline_engine = self.offline_engine_combo.currentData() or "system"
        piper_model_path = self.piper_model_edit.text().strip()
        styletts2_model_path = self.styletts2_model_edit.text().strip()
        return (
            lang_code,
            tts_mode,
            online_engine,
            offline_engine,
            piper_model_path,
            styletts2_model_path,
        )

    def _elevenlabs_api_key_for_voices(self) -> str:
        if hasattr(self, "elevenlabs_api_key_edit"):
            return self.elevenlabs_api_key_edit.text().strip()
        return self._stored_elevenlabs_api_key

    def _cartesia_api_key_for_voices(self) -> str:
        if hasattr(self, "cartesia_api_key_edit"):
            return self.cartesia_api_key_edit.text().strip()
        return self._stored_cartesia_api_key

    def _murf_api_key_for_voices(self) -> str:
        if hasattr(self, "murf_api_key_edit"):
            return self.murf_api_key_edit.text().strip()
        return self._stored_murf_api_key

    def _voice_sort_prefs_from_ui(self) -> VoiceSortPrefs:
        custom_order = dict(getattr(self, "_voice_sort_custom_order_draft", {}))
        if hasattr(self, "voice_order_list") and self.voice_order_list.count():
            lang_code, tts_mode, online_engine, offline_engine, _, _ = self._tts_context()
            engine = active_tts_engine(tts_mode, offline_engine, online_engine)
            order: list[str] = []
            for i in range(self.voice_order_list.count()):
                item = self.voice_order_list.item(i)
                if item:
                    voice_id = item.data(Qt.ItemDataRole.UserRole)
                    if voice_id:
                        order.append(str(voice_id))
            if order:
                custom_order[engine] = order
        return VoiceSortPrefs(
            preset=self.voice_sort_preset_combo.currentData() or PRESET_BOOK,
            gender_pref=self.voice_gender_pref_combo.currentData() or GENDER_FEMALE,
            region_pref=self.voice_region_pref_combo.currentData() or REGION_US,
            hide_unsuitable=self.voice_hide_unsuitable_check.isChecked(),
            show_recommended_badge=self.voice_show_recommended_badge_check.isChecked(),
            custom_order=custom_order,
        )

    def _set_voice_sort_combo(self, combo: QComboBox, value: str) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.blockSignals(True)
                combo.setCurrentIndex(i)
                combo.blockSignals(False)
                return

    def _on_voice_sort_preset_changed(self) -> None:
        preset = self.voice_sort_preset_combo.currentData() or PRESET_BOOK
        if preset == PRESET_BOOK:
            self._set_voice_sort_combo(self.voice_gender_pref_combo, GENDER_FEMALE)
            self._set_voice_sort_combo(self.voice_region_pref_combo, REGION_US)
            self.voice_hide_unsuitable_check.setChecked(True)
        elif preset == PRESET_NEWS:
            self._set_voice_sort_combo(self.voice_gender_pref_combo, GENDER_MALE)
            self.voice_hide_unsuitable_check.setChecked(True)
        elif preset == PRESET_FAST:
            self._set_voice_sort_combo(self.voice_gender_pref_combo, GENDER_MIX)
            self._set_voice_sort_combo(self.voice_region_pref_combo, REGION_ANY)
            self.voice_hide_unsuitable_check.setChecked(False)
            self.voice_show_recommended_badge_check.setChecked(False)
        self._on_voice_sort_pref_changed()

    def _on_voice_sort_pref_changed(self) -> None:
        self._update_voice_region_pref_visibility()
        self._refresh_voice_order_list()
        current_voice = self.voice_combo.currentData()
        self._refresh_voices(current_voice)
        if self.word_tts_profile_combo.currentData() == "same":
            self._refresh_word_voices(current_voice)
        else:
            self._refresh_word_voices(self.word_voice_combo.currentData())

    def _on_custom_voice_order_changed(self) -> None:
        self._set_voice_sort_combo(self.voice_sort_preset_combo, PRESET_CUSTOM)
        self._on_voice_sort_pref_changed()

    def _update_voice_region_pref_visibility(self) -> None:
        if not hasattr(self, "voice_region_pref_label"):
            return
        lang_code = self.language_combo.currentData() or "en"
        visible = lang_code == "en"
        self.voice_region_pref_label.setVisible(visible)
        self.voice_region_pref_combo.setVisible(visible)

    def _refresh_voice_order_list(self) -> None:
        if not hasattr(self, "voice_order_list"):
            return
        (
            lang_code,
            tts_mode,
            online_engine,
            offline_engine,
            piper_model_path,
            styletts2_model_path,
        ) = self._tts_context()
        engine = active_tts_engine(tts_mode, offline_engine, online_engine)
        prefs = self._voice_sort_prefs_from_ui()
        ordered = get_voices_for_tts_context(
            lang_code,
            tts_mode,
            offline_engine,
            online_engine=online_engine,
            app_dir=self.db.app_dir,
            piper_model_path=piper_model_path,
            styletts2_model_path=styletts2_model_path,
            elevenlabs_api_key=self._elevenlabs_api_key_for_voices(),
            cartesia_api_key=self._cartesia_api_key_for_voices(),
            murf_api_key=self._murf_api_key_for_voices(),
            voice_sort_prefs=prefs,
        )
        self.voice_order_list.blockSignals(True)
        self.voice_order_list.clear()
        for voice_id, label in ordered:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, voice_id)
            self.voice_order_list.addItem(item)
        self.voice_order_list.blockSignals(False)
        draft = dict(prefs.custom_order)
        draft[engine] = [voice_id for voice_id, _ in ordered]
        self._voice_sort_custom_order_draft = draft

    def _refresh_voices(self, select_voice: str | None = None) -> None:
        (
            lang_code,
            tts_mode,
            online_engine,
            offline_engine,
            piper_model_path,
            styletts2_model_path,
        ) = self._tts_context()
        if select_voice and ":" not in select_voice:
            select_voice = format_stored_voice("edge", select_voice)

        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        voice_sort_prefs = (
            self._voice_sort_prefs_from_ui()
            if hasattr(self, "voice_sort_preset_combo")
            else VoiceSortPrefs.from_settings(self.db.get_all_settings())
        )
        voices = get_voices_for_tts_context(
            lang_code,
            tts_mode,
            offline_engine,
            online_engine=online_engine,
            app_dir=self.db.app_dir,
            piper_model_path=piper_model_path,
            styletts2_model_path=styletts2_model_path,
            elevenlabs_api_key=self._elevenlabs_api_key_for_voices(),
            cartesia_api_key=self._cartesia_api_key_for_voices(),
            murf_api_key=self._murf_api_key_for_voices(),
            voice_sort_prefs=voice_sort_prefs,
        )
        for voice_id, label in voices:
            self.voice_combo.addItem(label, voice_id)

        target = select_voice
        if not target or not is_voice_valid_for_tts_context(
            target,
            lang_code,
            tts_mode,
            offline_engine,
            online_engine=online_engine,
            app_dir=self.db.app_dir,
            piper_model_path=piper_model_path,
            styletts2_model_path=styletts2_model_path,
            elevenlabs_api_key=self._elevenlabs_api_key_for_voices(),
            cartesia_api_key=self._cartesia_api_key_for_voices(),
            murf_api_key=self._murf_api_key_for_voices(),
            voice_sort_prefs=voice_sort_prefs,
        ):
            target = default_voice_for_tts_context(
                lang_code,
                tts_mode,
                offline_engine,
                online_engine=online_engine,
                app_dir=self.db.app_dir,
                piper_model_path=piper_model_path,
                styletts2_model_path=styletts2_model_path,
                elevenlabs_api_key=self._elevenlabs_api_key_for_voices(),
            cartesia_api_key=self._cartesia_api_key_for_voices(),
            murf_api_key=self._murf_api_key_for_voices(),
            voice_sort_prefs=voice_sort_prefs,
            )

        for i in range(self.voice_combo.count()):
            if self.voice_combo.itemData(i) == target:
                self.voice_combo.setCurrentIndex(i)
                break
        self.voice_combo.blockSignals(False)

    def _update_offline_engine_fields(self) -> None:
        tts_mode = self.tts_mode_combo.currentData() or "auto"
        offline_engine = self.offline_engine_combo.currentData() or "system"
        show_online = tts_mode in ("online", "auto")
        show_offline = tts_mode in ("offline", "auto")
        self.online_engine_label.setVisible(show_online)
        self.online_engine_combo.setVisible(show_online)
        self.offline_engine_label.setVisible(show_offline)
        self.offline_engine_combo.setVisible(show_offline)
        show_piper = show_offline and offline_engine == "piper"
        self.piper_hint_label.setVisible(show_piper)
        self.kokoro_hint_label.setVisible(show_offline and offline_engine == "kokoro")
        self.xtts_hint_label.setVisible(show_offline and offline_engine == "xtts")
        show_styletts2 = show_offline and offline_engine == "styletts2"
        self.styletts2_model_label.setVisible(show_styletts2)
        for i in range(self.styletts2_model_row.count()):
            item = self.styletts2_model_row.itemAt(i)
            if item and item.widget():
                item.widget().setVisible(show_styletts2)
        self.styletts2_hint_label.setVisible(show_styletts2)

    def _on_tts_engine_changed(self) -> None:
        current_voice = self.voice_combo.currentData()
        self._refresh_speed_combo()
        self._refresh_voices(current_voice)
        self._update_offline_engine_fields()
        self._update_offline_block_hint()
        if hasattr(self, "voice_order_list"):
            self._refresh_voice_order_list()
        if self.word_tts_profile_combo.currentData() == "same":
            self._refresh_word_voices(current_voice)

    def _update_offline_block_hint(self) -> None:
        tts_mode = self.tts_mode_combo.currentData() or "auto"
        offline_engine = self.offline_engine_combo.currentData() or "system"
        if tts_mode == "online" or not is_slow_offline_engine(offline_engine):
            self.offline_block_hint_label.hide()
            return
        current = int(self.block_size_combo.currentData() or 55)
        recommended = recommended_block_words(offline_engine)
        engine_label = tr(f"settings.offline_engine.{offline_engine}")
        self.offline_block_hint_label.setText(
            tr(
                "settings.offline_block_hint",
                engine=engine_label,
                recommended=recommended,
                current=current,
            )
        )
        self.offline_block_hint_label.setVisible(True)

    def _browse_sync_folder(self) -> None:
        start = self.sync_folder_edit.text().strip() or str(self.db.app_dir)
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("settings.sync_folder"),
            start,
        )
        if folder:
            self.sync_folder_edit.setText(folder)

    def _sync_now(self) -> None:
        folder_text = self.sync_folder_edit.text().strip()
        if not folder_text:
            QMessageBox.warning(
                self,
                tr("settings.sync_now"),
                tr("settings.sync_folder_hint"),
            )
            return
        try:
            path = self.backup.sync_to_folder(Path(folder_text))
            QMessageBox.information(
                self,
                tr("settings.sync_now"),
                tr("settings.sync_ok", path=path),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("settings.sync_now"),
                tr("settings.sync_failed", error=exc),
            )

    def _populate_voices(self, lang_code: str, select_voice: str | None = None) -> None:
        self._refresh_voices(select_voice)

    def _word_tts_context(self) -> tuple[str, str, str, str]:
        lang_code = self.language_combo.currentData() or "en"
        if (self.word_tts_profile_combo.currentData() or "same") == "same":
            _lang, tts_mode, online_engine, offline_engine, _piper, _style = (
                self._tts_context()
            )
            return lang_code, tts_mode, online_engine, offline_engine
        tts_mode = self.word_tts_mode_combo.currentData() or "auto"
        online_engine = self.word_online_engine_combo.currentData() or "edge"
        offline_engine = self.word_offline_engine_combo.currentData() or "system"
        return lang_code, tts_mode, online_engine, offline_engine

    def _refresh_word_voices(self, select_voice: str | None = None) -> None:
        lang_code, tts_mode, online_engine, offline_engine = self._word_tts_context()
        piper_model_path = self.piper_model_edit.text().strip()
        styletts2_model_path = self.styletts2_model_edit.text().strip()
        if select_voice and ":" not in select_voice:
            select_voice = format_stored_voice("edge", select_voice)

        self.word_voice_combo.blockSignals(True)
        self.word_voice_combo.clear()
        voice_sort_prefs = (
            self._voice_sort_prefs_from_ui()
            if hasattr(self, "voice_sort_preset_combo")
            else VoiceSortPrefs.from_settings(self.db.get_all_settings())
        )
        voices = get_voices_for_tts_context(
            lang_code,
            tts_mode,
            offline_engine,
            online_engine=online_engine,
            app_dir=self.db.app_dir,
            piper_model_path=piper_model_path,
            styletts2_model_path=styletts2_model_path,
            elevenlabs_api_key=self._elevenlabs_api_key_for_voices(),
            cartesia_api_key=self._cartesia_api_key_for_voices(),
            murf_api_key=self._murf_api_key_for_voices(),
            voice_sort_prefs=voice_sort_prefs,
        )
        for voice_id, label in voices:
            self.word_voice_combo.addItem(label, voice_id)

        target = select_voice
        if not target or not is_voice_valid_for_tts_context(
            target,
            lang_code,
            tts_mode,
            offline_engine,
            online_engine=online_engine,
            app_dir=self.db.app_dir,
            piper_model_path=piper_model_path,
            styletts2_model_path=styletts2_model_path,
            elevenlabs_api_key=self._elevenlabs_api_key_for_voices(),
            cartesia_api_key=self._cartesia_api_key_for_voices(),
            murf_api_key=self._murf_api_key_for_voices(),
            voice_sort_prefs=voice_sort_prefs,
        ):
            target = default_voice_for_tts_context(
                lang_code,
                tts_mode,
                offline_engine,
                online_engine=online_engine,
                app_dir=self.db.app_dir,
                piper_model_path=piper_model_path,
                styletts2_model_path=styletts2_model_path,
                elevenlabs_api_key=self._elevenlabs_api_key_for_voices(),
            cartesia_api_key=self._cartesia_api_key_for_voices(),
            murf_api_key=self._murf_api_key_for_voices(),
            voice_sort_prefs=voice_sort_prefs,
            )

        for i in range(self.word_voice_combo.count()):
            if self.word_voice_combo.itemData(i) == target:
                self.word_voice_combo.setCurrentIndex(i)
                break
        self.word_voice_combo.blockSignals(False)

    def _update_word_tts_fields(self) -> None:
        enabled = self.word_tts_combo.currentData() == "1"
        custom = (
            enabled and self.word_tts_profile_combo.currentData() == "custom"
        )
        word_mode = self.word_tts_mode_combo.currentData() or "auto"
        show_online = custom and word_mode in ("online", "auto")
        show_offline = custom and word_mode in ("offline", "auto")

        for widget in (
            self.word_tts_profile_label,
            self.word_tts_profile_combo,
        ):
            widget.setVisible(enabled)
        for widget in (
            self.word_tts_mode_label,
            self.word_tts_mode_combo,
            self.word_online_engine_label,
            self.word_online_engine_combo,
            self.word_offline_engine_label,
            self.word_offline_engine_combo,
            self.word_voice_label,
            self.word_voice_combo,
            self.word_voice_preview_btn,
        ):
            widget.setVisible(custom)
        self.word_online_engine_label.setVisible(show_online)
        self.word_online_engine_combo.setVisible(show_online)
        self.word_offline_engine_label.setVisible(show_offline)
        self.word_offline_engine_combo.setVisible(show_offline)

    def _on_word_tts_engine_changed(self) -> None:
        current_voice = self.word_voice_combo.currentData()
        self._refresh_word_voices(current_voice)
        self._update_word_tts_fields()

    def _on_language_changed(self) -> None:
        if hasattr(self, "voice_region_pref_label"):
            self._update_voice_region_pref_visibility()
        current_voice = self.voice_combo.currentData()
        self._refresh_voices(current_voice)
        current_word_voice = self.word_voice_combo.currentData()
        self._refresh_word_voices(current_word_voice)
        if hasattr(self, "voice_order_list"):
            self._refresh_voice_order_list()

    def _on_speech_speed_changed(self) -> None:
        speed = float(self.speed_combo.currentData() or 1.0)
        self.db.set_setting("tts_speed", str(speed))
        self.preview_tts.stop(emit_finished=False)
        self.preview_tts.reset_memory_cache()
        self.preview_tts.set_speed(speed)
        parent = self.parent()
        if parent is not None and hasattr(parent, "apply_speech_rate"):
            parent.apply_speech_rate(speed)

    def _apply_preview_engine_settings(self) -> None:
        self.preview_tts.stop(emit_finished=False)
        self.preview_tts.set_playback_intent(active=True, paused=False)
        voice = self.voice_combo.currentData()
        if voice:
            self.preview_tts.set_voice(voice)
        else:
            self.preview_tts.set_voice(format_stored_voice("edge", "en-US-AriaNeural"))
        self.preview_tts.set_speed(float(self.speed_combo.currentData() or 1.0))
        self.preview_tts.set_mode(self.tts_mode_combo.currentData() or "auto")
        self.preview_tts.set_online_engine(
            self.online_engine_combo.currentData() or "edge"
        )
        self.preview_tts.set_offline_language(self.language_combo.currentData() or "en")
        self.preview_tts.set_offline_engine(
            self.offline_engine_combo.currentData() or "system"
        )
        self.preview_tts.set_piper_model_path(self.piper_model_edit.text().strip())
        self.preview_tts.set_styletts2_model_path(
            self.styletts2_model_edit.text().strip()
        )
        self.preview_tts.set_azure_credentials(
            self.azure_speech_key_edit.text().strip(),
            self.azure_speech_region_edit.text().strip(),
        )
        self.preview_tts.set_google_tts_api_key(
            self.google_tts_api_key_edit.text().strip()
        )
        self.preview_tts.set_elevenlabs_api_key(
            self.elevenlabs_api_key_edit.text().strip()
        )
        self.preview_tts.set_cartesia_api_key(
            self.cartesia_api_key_edit.text().strip()
        )
        self.preview_tts.set_azure_tts_usage(self.azure_tts_usage)
        self.preview_tts.set_google_tts_usage(self.google_tts_usage)
        self.preview_tts.set_elevenlabs_tts_usage(self.elevenlabs_tts_usage)
        self.preview_tts.set_cartesia_tts_usage(self.cartesia_tts_usage)
        self.preview_tts.set_murf_api_key(self.murf_api_key_edit.text().strip())
        self.preview_tts.set_murf_tts_usage(self.murf_tts_usage)
        self.preview_tts.set_app_dir(self.db.app_dir)

    def _apply_word_preview_engine_settings(self) -> None:
        self.preview_tts.stop(emit_finished=False)
        self.preview_tts.set_playback_intent(active=True, paused=False)
        profile = self.word_tts_profile_combo.currentData() or "same"
        if profile == "custom":
            voice = self.word_voice_combo.currentData()
            self.preview_tts.set_word_tts_settings(
                "custom",
                voice or "",
                self.word_tts_mode_combo.currentData() or "auto",
                self.word_online_engine_combo.currentData() or "edge",
                self.word_offline_engine_combo.currentData() or "system",
            )
        else:
            self.preview_tts.set_word_tts_settings("same", "", "auto", "edge", "system")
            voice = self.voice_combo.currentData()
        if voice:
            self.preview_tts.set_voice(voice)
        self.preview_tts.set_speed(float(self.speed_combo.currentData() or 1.0))
        self.preview_tts.set_mode(self.tts_mode_combo.currentData() or "auto")
        self.preview_tts.set_online_engine(
            self.online_engine_combo.currentData() or "edge"
        )
        self.preview_tts.set_offline_language(self.language_combo.currentData() or "en")
        self.preview_tts.set_offline_engine(
            self.offline_engine_combo.currentData() or "system"
        )
        self.preview_tts.set_piper_model_path(self.piper_model_edit.text().strip())
        self.preview_tts.set_styletts2_model_path(
            self.styletts2_model_edit.text().strip()
        )
        self.preview_tts.set_azure_credentials(
            self.azure_speech_key_edit.text().strip(),
            self.azure_speech_region_edit.text().strip(),
        )
        self.preview_tts.set_google_tts_api_key(
            self.google_tts_api_key_edit.text().strip()
        )
        self.preview_tts.set_elevenlabs_api_key(
            self.elevenlabs_api_key_edit.text().strip()
        )
        self.preview_tts.set_cartesia_api_key(
            self.cartesia_api_key_edit.text().strip()
        )
        self.preview_tts.set_azure_tts_usage(self.azure_tts_usage)
        self.preview_tts.set_google_tts_usage(self.google_tts_usage)
        self.preview_tts.set_elevenlabs_tts_usage(self.elevenlabs_tts_usage)
        self.preview_tts.set_cartesia_tts_usage(self.cartesia_tts_usage)
        self.preview_tts.set_murf_api_key(self.murf_api_key_edit.text().strip())
        self.preview_tts.set_murf_tts_usage(self.murf_tts_usage)
        self.preview_tts.set_app_dir(self.db.app_dir)

    def _preview_word_voice(self) -> None:
        if self.word_tts_combo.currentData() != "1":
            return
        if self.word_tts_profile_combo.currentData() == "custom":
            if not self.word_voice_combo.currentData():
                return
        elif not self.voice_combo.currentData():
            return
        self._apply_word_preview_engine_settings()
        lang = self.language_combo.currentData() or "en"
        self.word_voice_preview_btn.setEnabled(False)
        sample = voice_preview_sample(lang).split()[0] or voice_preview_sample(lang)
        self.preview_tts.preview_word(sample)

    def _preview_voice(self) -> None:
        if not self.voice_combo.currentData():
            return
        self._apply_preview_engine_settings()
        lang = self.language_combo.currentData() or "en"
        self.voice_preview_btn.setEnabled(False)
        self.preview_tts.preview(voice_preview_sample(lang))

    def _on_preview_generating(self, active: bool) -> None:
        if active:
            self.voice_preview_btn.setEnabled(False)
            self.word_voice_preview_btn.setEnabled(False)
        elif not self.preview_tts.is_generating():
            self.voice_preview_btn.setEnabled(True)
            self.word_voice_preview_btn.setEnabled(True)

    def _on_preview_error(self, message: str) -> None:
        self.voice_preview_btn.setEnabled(True)
        self.word_voice_preview_btn.setEnabled(True)
        QMessageBox.warning(
            self,
            tr("errors.title.preview"),
            humanize_error(message, area="preview"),
        )

    def _on_preview_finished(self) -> None:
        self.voice_preview_btn.setEnabled(True)
        self.word_voice_preview_btn.setEnabled(True)

    def reject(self) -> None:
        self.preview_tts.stop(emit_finished=False)
        super().reject()

    def _goal_time_label(self, minutes: int) -> str:
        if minutes >= 60 and minutes % 60 == 0:
            return tr("settings.daily_goal_hours_fmt", n=minutes // 60)
        if minutes >= 60 and minutes % 30 == 0:
            hours = minutes // 60
            half = (minutes % 60) == 30
            if half and hours >= 1:
                return tr("settings.daily_goal_hours_half_fmt", n=hours)
        return tr("settings.daily_goal_minutes_fmt", n=minutes)

    @staticmethod
    def _closest_option(options: list[int], value: int) -> int:
        return min(options, key=lambda option: abs(option - value))

    def _populate_goal_combo(self, settings: dict | None = None) -> None:
        if settings is None:
            settings = self.db.get_all_settings()
        goal_type = self.goal_type_combo.currentData() or settings.get(
            "daily_goal_type", "blocks"
        )
        self.goal_combo.blockSignals(True)
        self.goal_combo.clear()
        if goal_type == "time":
            options = self.GOAL_TIME_OPTIONS
            current = int(settings.get("daily_goal_minutes", "15"))
            for minutes in options:
                self.goal_combo.addItem(self._goal_time_label(minutes), minutes)
        else:
            options = self.GOAL_BLOCK_OPTIONS
            current = int(settings.get("daily_goal_blocks", "10"))
            for blocks in options:
                self.goal_combo.addItem(str(blocks), blocks)
        pick = current if current in options else self._closest_option(options, current)
        self.goal_combo.setCurrentIndex(options.index(pick))
        self.goal_combo.blockSignals(False)

    def _on_goal_type_changed(self) -> None:
        self._populate_goal_combo()

    def _export_backup(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("settings.export"),
            BackupService.DEFAULT_FILENAME,
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            exported = self.backup.export_to_file(path)
            QMessageBox.information(
                self, tr("settings.export"), tr("settings.backup_ok", path=exported)
            )
        except Exception as exc:
            QMessageBox.critical(
                self, tr("settings.export"), tr("settings.backup_failed", error=exc)
            )

    def _import_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("settings.import"), "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            counts = self.backup.import_from_file(path, merge=True)
            QMessageBox.information(
                self,
                tr("settings.import"),
                tr(
                    "settings.import_ok",
                    books=counts["books"],
                    created=counts.get("books_created", 0),
                    stats=counts["stats"],
                ),
            )
        except Exception as exc:
            QMessageBox.critical(
                self, tr("settings.import"), tr("settings.import_failed", error=exc)
            )

    def _clear_user_data(self) -> None:
        reply = QMessageBox.warning(
            self,
            tr("settings.clear_data_confirm_title"),
            tr("settings.clear_data_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            counts = self.backup.clear_user_data()
            self.library_cleared = True
            self.preview_tts.reset_memory_cache()
            QMessageBox.information(
                self,
                tr("settings.clear_data"),
                tr(
                    "settings.clear_data_ok",
                    books=counts["books"],
                    stats=counts["stats_days"],
                    audio=counts["audio_files"],
                    covers=counts["cover_files"],
                ),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("settings.clear_data"),
                tr("settings.clear_data_failed", error=exc),
            )

    def _save(self) -> None:
        self.preview_tts.stop(emit_finished=False)
        self.db.set_setting("ui_language", self.ui_lang_combo.currentData())
        self.db.set_setting("theme", self.theme_combo.currentData())
        self.db.set_setting("tts_speed", str(self.speed_combo.currentData()))
        self.db.set_setting("book_language", self.language_combo.currentData())
        self.db.set_setting(
            "translation_language", self.translation_lang_combo.currentData()
        )
        block_provider = self.block_provider_combo.currentData()
        self.db.set_setting("translation_block_provider", block_provider)
        self.db.set_setting("translation_word_provider", self.word_provider_combo.currentData())
        self.db.set_setting(
            "translation_selection_provider",
            self.selection_provider_combo.currentData(),
        )
        self.db.set_setting("translation_provider", block_provider)
        self.db.set_setting("ollama_url", self.ollama_url_edit.text().strip())
        self.db.set_setting("ollama_model", self.ollama_model_edit.text().strip())
        self.db.set_setting("tts_voice", self.voice_combo.currentData())
        self.db.set_setting("tts_mode", self.tts_mode_combo.currentData())
        self.db.set_setting("online_engine", self.online_engine_combo.currentData())
        self.db.set_setting("word_tts", self.word_tts_combo.currentData())
        self.db.set_setting(
            "word_tts_profile", self.word_tts_profile_combo.currentData()
        )
        self.db.set_setting("word_tts_mode", self.word_tts_mode_combo.currentData())
        self.db.set_setting(
            "word_tts_online_engine", self.word_online_engine_combo.currentData()
        )
        self.db.set_setting(
            "word_tts_offline_engine", self.word_offline_engine_combo.currentData()
        )
        self.db.set_setting("word_tts_voice", self.word_voice_combo.currentData())
        self.db.set_setting("offline_engine", self.offline_engine_combo.currentData())
        self.db.set_setting("piper_model_path", "")
        self.db.set_setting(
            "styletts2_model_path", self.styletts2_model_edit.text().strip()
        )
        self.db.set_setting(
            "azure_speech_region", self.azure_speech_region_edit.text().strip()
        )
        self.db.set_setting("update_check", self.update_check.currentData())
        self.db.set_setting("github_repo", self.github_repo_edit.text().strip())
        self.db.set_setting("pdf_ocr_mode", self.pdf_ocr_combo.currentData())
        self.db.set_setting("pdf_ocr_max_pages", str(self.pdf_ocr_pages_spin.value()))
        self.db.set_setting("daily_goal_type", self.goal_type_combo.currentData())
        if self.goal_type_combo.currentData() == "time":
            self.db.set_setting("daily_goal_minutes", str(self.goal_combo.currentData()))
        else:
            self.db.set_setting("daily_goal_blocks", str(self.goal_combo.currentData()))
        self.db.set_setting("font_size", str(self.font_size_spin.value()))
        self.db.set_setting("font_family", self.font_combo.currentText())
        self.db.set_setting(
            "block_words_target", str(self.block_size_combo.currentData())
        )
        self.db.set_setting("line_width", str(self.line_width_spin.value()))
        self.db.set_setting("word_highlight", self.word_highlight_combo.currentData())
        self.db.set_setting(
            "word_highlight_style", self.word_highlight_style_combo.currentData()
        )
        self.db.set_setting("word_highlight_color", self._hl_color_primary.name())
        self.db.set_setting("word_highlight_color_2", self._hl_color_secondary.name())
        self.db.set_setting("word_highlight_color_3", self._hl_color_accent.name())
        self.db.set_setting("word_highlight_text_color", self._hl_color_text.name())
        self.db.set_setting(
            "word_highlight_palette", self.highlight_palette_combo.currentData()
        )
        self.db.set_setting(
            "whisper_word_align", self.whisper_align_combo.currentData()
        )
        self.db.set_setting("sync_folder", self.sync_folder_edit.text().strip())
        if hasattr(self, "voice_sort_preset_combo"):
            self._voice_sort_prefs_from_ui().save_to_db(self.db)
        self._pending_api_key = self.api_key_edit.text().strip()
        self._pending_apify_api_token = self.apify_api_token_edit.text().strip()
        self._pending_google_api_key = self.google_api_key_edit.text().strip()
        self._pending_deepl_api_key = self.deepl_api_key_edit.text().strip()
        self._pending_azure_speech_key = self.azure_speech_key_edit.text().strip()
        self._pending_google_tts_api_key = self.google_tts_api_key_edit.text().strip()
        self._pending_elevenlabs_api_key = self.elevenlabs_api_key_edit.text().strip()
        self._pending_cartesia_api_key = self.cartesia_api_key_edit.text().strip()
        self._pending_murf_api_key = self.murf_api_key_edit.text().strip()
        self.accept()

    def get_api_key(self) -> str:
        return getattr(self, "_pending_api_key", self.api_key_edit.text().strip())

    def get_apify_api_token(self) -> str:
        return getattr(
            self, "_pending_apify_api_token", self.apify_api_token_edit.text().strip()
        )

    def get_google_api_key(self) -> str:
        return getattr(
            self, "_pending_google_api_key", self.google_api_key_edit.text().strip()
        )

    def get_deepl_api_key(self) -> str:
        return getattr(
            self, "_pending_deepl_api_key", self.deepl_api_key_edit.text().strip()
        )

    def get_azure_speech_key(self) -> str:
        return getattr(
            self,
            "_pending_azure_speech_key",
            self.azure_speech_key_edit.text().strip(),
        )

    def get_google_tts_api_key(self) -> str:
        return getattr(
            self,
            "_pending_google_tts_api_key",
            self.google_tts_api_key_edit.text().strip(),
        )

    def get_elevenlabs_api_key(self) -> str:
        return getattr(
            self,
            "_pending_elevenlabs_api_key",
            self.elevenlabs_api_key_edit.text().strip(),
        )

    def get_cartesia_api_key(self) -> str:
        return getattr(
            self,
            "_pending_cartesia_api_key",
            self.cartesia_api_key_edit.text().strip(),
        )

    def get_murf_api_key(self) -> str:
        return getattr(
            self,
            "_pending_murf_api_key",
            self.murf_api_key_edit.text().strip(),
        )

    def get_settings(self) -> dict[str, str]:
        return self.db.get_all_settings()

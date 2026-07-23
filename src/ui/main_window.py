"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.book_import_worker import BookImportThread, MAX_IMPORT_BYTES
from ..core.book_parser import BookParser
from ..core.cover_service import CoverService
from ..core.database import Database
from ..core.i18n import set_language, tr
from ..core.parse_result import ParseResult
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
    set_api_key,
    set_apify_api_token,
    set_azure_speech_key,
    set_deepl_api_key,
    set_murf_api_key,
    set_cartesia_api_key,
    set_elevenlabs_api_key,
    set_google_api_key,
    set_google_tts_api_key,
)
from ..core.processing_status import ProcessingStatusTracker
from ..core.translation_service import TranslationService
from ..core.tts_engine import TTSEngine
from ..core.network_status import is_online
from ..core.update_service import check_github_release
from ..core.version import APP_NAME, APP_VERSION
from .continue_dialog import ContinueDialog
from .processing_status_panel import ProcessingStatusPanel
from .reading_view import ReadingView
from .settings_dialog import SettingsDialog
from .stats_view import StatsView
from .styles import DARK_THEME, LIGHT_THEME
from .tags_dialog import TagsDialog


class MainWindow(QMainWindow):
    PAGE_READING = 0
    PAGE_LIBRARY = 1
    PAGE_STATS = 2

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(900, 700)
        self.resize(1100, 800)

        self.db = Database()
        self.covers = CoverService(self.db.app_dir)
        self.apify_usage = ApifyTranslateUsage(self.db)
        self.google_cloud_usage = GoogleTranslateUsage(self.db)
        self.deepl_usage = DeepLTranslateUsage(self.db)
        self.azure_tts_usage = AzureTTSUsage(self.db)
        self.google_tts_usage = GoogleTTSUsage(self.db)
        self.elevenlabs_tts_usage = ElevenLabsTTSUsage(self.db)
        self.cartesia_tts_usage = CartesiaTTSUsage(self.db)
        self.murf_tts_usage = MurfTTSUsage(self.db)
        set_language(self.db.get_setting("ui_language", "uk"))
        self.tts = TTSEngine(self.db.get_setting("tts_voice", "en-US-AriaNeural"))
        settings = self.db.get_all_settings()
        api_key = get_api_key(settings.get("openai_api_key", ""))
        apify_api_token = get_apify_api_token(settings.get("apify_api_token", ""))
        google_api_key = get_google_api_key(settings.get("google_api_key", ""))
        deepl_api_key = get_deepl_api_key(settings.get("deepl_api_key", ""))
        self.translator = TranslationService(
            api_key,
            settings.get("book_language", "en"),
            settings.get(
                "translation_language", settings.get("ui_language", "uk")
            ),
            provider=settings.get("translation_provider", "auto"),
            ollama_url=settings.get("ollama_url", "http://127.0.0.1:11434"),
            ollama_model=settings.get("ollama_model", ""),
            apify_api_token=apify_api_token,
            google_api_key=google_api_key,
            deepl_api_key=deepl_api_key,
            block_provider=settings.get(
                "translation_block_provider",
                settings.get("translation_provider", "auto"),
            ),
            word_provider=settings.get("translation_word_provider", "free"),
            selection_provider=settings.get(
                "translation_selection_provider", "apify"
            ),
            apify_usage=self.apify_usage,
            google_usage=self.google_cloud_usage,
            deepl_usage=self.deepl_usage,
        )
        self._nav_buttons: list[QPushButton] = []
        self._current_page = self.PAGE_READING
        self._import_thread: BookImportThread | None = None
        self._import_dialog: QProgressDialog | None = None
        self._import_worker = None
        self._library_filter = ""
        self._library_sort = "recent"
        self._library_tag = ""
        self._reimport_book_id = 0
        self._status_debounce = QTimer(self)
        self._status_debounce.setSingleShot(True)
        self._status_debounce.setInterval(300)
        self._status_debounce.timeout.connect(self._update_status_bar_impl)
        self._library_refresh_timer = QTimer(self)
        self._library_refresh_timer.setSingleShot(True)
        self._library_refresh_timer.setInterval(800)
        self._library_refresh_timer.timeout.connect(self._refresh_book_list)

        self._build_ui()
        self._retranslate_ui()
        self._apply_theme()
        self._apply_reading_settings()
        self._switch_page(self.PAGE_READING)
        QTimer.singleShot(0, self._check_continue_reading)
        QTimer.singleShot(3000, self._check_for_updates)

    def _check_for_updates(self) -> None:
        if self.db.get_setting("update_check", "1") != "1":
            return
        repo = self.db.get_setting("github_repo", "").strip()
        if not repo:
            return

        class _UpdateWorker(QThread):
            result = None

            def __init__(self, repository: str) -> None:
                super().__init__()
                self.repository = repository

            def run(self) -> None:
                self.result = check_github_release(self.repository, APP_VERSION)

        worker = _UpdateWorker(repo)
        worker.finished.connect(lambda: self._show_update_dialog(worker.result))
        worker.start()
        self._update_worker = worker

    def _show_update_dialog(self, info) -> None:
        if not info:
            return
        reply = QMessageBox.question(
            self,
            tr("update.title"),
            tr("update.message", version=info.version),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            import webbrowser

            webbrowser.open(info.url)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 24, 12, 24)
        sidebar_layout.setSpacing(4)

        logo = QLabel("AI Reading\nStudio")
        logo.setStyleSheet("font-size: 18px; font-weight: 700; padding: 8px 0 20px 4px;")
        sidebar_layout.addWidget(logo)

        self.nav_reading = self._make_nav_button("", self.PAGE_READING)
        self.nav_books = self._make_nav_button("", self.PAGE_LIBRARY)
        self.nav_stats = self._make_nav_button("", self.PAGE_STATS)

        for btn in self._nav_buttons:
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        self.add_btn = QPushButton()
        self.add_btn.setToolTip("")
        self.add_btn.clicked.connect(self._add_book)
        sidebar_layout.addWidget(self.add_btn)

        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("secondaryBtn")
        self.settings_btn.setToolTip("")
        self.settings_btn.clicked.connect(self._open_settings)
        sidebar_layout.addWidget(self.settings_btn)

        main_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        self.reading_view = ReadingView(
            self.db, self.tts, self.translator
        )
        self.reading_view.progress_updated.connect(self._on_progress_updated)
        self.reading_view.focus_mode_changed.connect(self._on_focus_mode)
        self.stack.addWidget(self.reading_view)

        self.status_tracker = ProcessingStatusTracker(
            self.tts, self.translator, self.reading_view, self
        )
        self.status_panel = ProcessingStatusPanel(self.status_tracker, self)

        library_page = QWidget()
        lib_layout = QVBoxLayout(library_page)
        lib_layout.setContentsMargins(30, 30, 30, 30)
        lib_layout.setSpacing(12)

        self.lib_title = QLabel()
        self.lib_title.setObjectName("titleLabel")
        lib_layout.addWidget(self.lib_title)

        self.lib_hint = QLabel()
        self.lib_hint.setStyleSheet("color: #888; font-size: 13px;")
        lib_layout.addWidget(self.lib_hint)

        filter_row = QHBoxLayout()
        self.sort_combo = QComboBox()
        for key in ("recent", "title", "author", "progress", "added"):
            self.sort_combo.addItem(tr(f"library.sort.{key}"), key)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        filter_row.addWidget(self.sort_combo)

        self.tag_combo = QComboBox()
        self.tag_combo.currentIndexChanged.connect(self._on_tag_filter_changed)
        filter_row.addWidget(self.tag_combo, stretch=1)
        lib_layout.addLayout(filter_row)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("")
        self.search_edit.textChanged.connect(self._on_library_search)
        lib_layout.addWidget(self.search_edit)

        self.book_list = QListWidget()
        self.book_list.setIconSize(QSize(42, 56))
        self.book_list.setSpacing(4)
        self.book_list.itemDoubleClicked.connect(self._on_book_selected)
        self.book_list.itemClicked.connect(self._on_book_clicked)
        lib_layout.addWidget(self.book_list)

        lib_btns = QHBoxLayout()
        self.open_btn = QPushButton()
        self.open_btn.clicked.connect(self._open_selected_book)
        lib_btns.addWidget(self.open_btn)

        self.delete_btn = QPushButton()
        self.delete_btn.setObjectName("secondaryBtn")
        self.delete_btn.clicked.connect(self._remove_selected_book)
        lib_btns.addWidget(self.delete_btn)

        self.reimport_btn = QPushButton()
        self.reimport_btn.setObjectName("secondaryBtn")
        self.reimport_btn.clicked.connect(self._reimport_selected_book)
        lib_btns.addWidget(self.reimport_btn)

        self.tags_btn = QPushButton()
        self.tags_btn.setObjectName("secondaryBtn")
        self.tags_btn.clicked.connect(self._edit_book_tags)
        lib_btns.addWidget(self.tags_btn)
        lib_layout.addLayout(lib_btns)

        self.stack.addWidget(library_page)

        self.stats_view = StatsView(self.db)
        self.stack.addWidget(self.stats_view)

        self._refresh_book_list()
        self._init_status_bar()

    def _init_status_bar(self) -> None:
        status_wrap = QWidget()
        status_layout = QHBoxLayout(status_wrap)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)

        self._status_activity = QLabel("●")
        self._status_activity.setStyleSheet("color: #c4a035; font-size: 10px;")
        self._status_activity.hide()
        status_layout.addWidget(self._status_activity)

        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: #888; padding: 0 4px;")
        status_layout.addWidget(self._status_label)

        self._status_btn = QPushButton(tr("status.panel.open"))
        self._status_btn.setObjectName("secondaryBtn")
        self._status_btn.setFixedHeight(24)
        self._status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._status_btn.setToolTip(tr("status.panel.hint"))
        self._status_btn.clicked.connect(self._toggle_status_panel)
        status_layout.addWidget(self._status_btn)

        self.statusBar().addPermanentWidget(status_wrap)
        self.status_tracker.changed.connect(self._schedule_status_bar_update)
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start(15000)
        self._update_status_bar()

    def _toggle_status_panel(self) -> None:
        if self.status_panel.isVisible():
            self.status_panel.hide()
        else:
            self.status_panel.show()
            self.status_panel.raise_()
            self.status_panel.activateWindow()

    def _schedule_status_bar_update(self) -> None:
        self._status_debounce.start()

    def _update_status_bar(self) -> None:
        from ..core.network_status import invalidate_cache

        invalidate_cache()
        self.translator.invalidate_network_cache()
        self._update_status_bar_impl()

    def _update_status_bar_impl(self) -> None:
        parts = [tr("status.online") if is_online() else tr("status.offline")]
        if self.translator.can_use_ollama():
            parts.append(tr("status.ollama"))
        if self.status_tracker.is_busy():
            snap = self.status_tracker.snapshot()
            parts.append(tr("status.bar.busy", summary=snap.summary_text))
            color = "#b54545" if snap.summary_level == "error" else "#c4a035"
            self._status_activity.setStyleSheet(
                f"color: {color}; font-size: 10px;"
            )
            self._status_activity.show()
        else:
            self._status_activity.hide()
        self._status_label.setText(" · ".join(parts))

    def _make_nav_button(self, text: str, page_index: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("navBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, idx=page_index: self._switch_page(idx))
        self._nav_buttons.append(btn)
        return btn

    def _switch_page(self, index: int) -> None:
        if index != self.PAGE_READING and self._current_page == self.PAGE_READING:
            self.reading_view.pause_reading()

        self._current_page = index
        self.stack.setCurrentIndex(index)

        for i, btn in enumerate(self._nav_buttons):
            btn.setObjectName("navBtnActive" if i == index else "navBtn")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if index == self.PAGE_STATS:
            self.stats_view.refresh()

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(f"{tr('app.title')} {APP_VERSION}")
        self.nav_reading.setText(tr("nav.reading"))
        self.nav_books.setText(tr("nav.library"))
        self.nav_stats.setText(tr("nav.stats"))
        self.add_btn.setText(tr("btn.add_book"))
        self.add_btn.setToolTip(tr("tip.add_book"))
        self.settings_btn.setText(tr("btn.settings"))
        self.settings_btn.setToolTip(tr("tip.settings"))
        self.lib_title.setText(tr("library.title"))
        self.lib_hint.setText(tr("library.hint"))
        self.search_edit.setPlaceholderText(tr("library.search"))
        self.open_btn.setText(tr("library.open"))
        self.delete_btn.setText(tr("library.remove"))
        self.reimport_btn.setText(tr("library.reimport"))
        self.tags_btn.setText(tr("library.tags"))
        self._refresh_tag_combo()
        self._update_sort_combo_labels()
        self._update_status_bar()
        self.reading_view.retranslate()
        self.stats_view.retranslate()

    def _apply_theme(self) -> None:
        theme = self.db.get_setting("theme", "light")
        self.setStyleSheet(DARK_THEME if theme == "dark" else LIGHT_THEME)
        self._switch_page(self._current_page)

    def _apply_reading_settings(self) -> None:
        settings = self.db.get_all_settings()
        self.reading_view.apply_settings(settings)
        speed = float(settings.get("tts_speed", "1.0"))
        self.tts.set_speed(speed)
        self.tts.set_mode(settings.get("tts_mode", "auto"))
        self.tts.set_online_engine(settings.get("online_engine", "edge"))
        self.tts.set_offline_language(settings.get("book_language", "en"))
        self.tts.set_offline_engine(settings.get("offline_engine", "system"))
        self.tts.set_whisper_word_align(settings.get("whisper_word_align", "auto"))
        self.tts.set_piper_model_path(settings.get("piper_model_path", ""))
        self.tts.set_styletts2_model_path(settings.get("styletts2_model_path", ""))
        self.tts.set_azure_credentials(
            get_azure_speech_key(settings.get("azure_speech_key", "")),
            settings.get("azure_speech_region", ""),
        )
        self.tts.set_google_tts_api_key(
            get_google_tts_api_key(settings.get("google_tts_api_key", ""))
        )
        self.tts.set_elevenlabs_api_key(
            get_elevenlabs_api_key(settings.get("elevenlabs_api_key", ""))
        )
        self.tts.set_cartesia_api_key(
            get_cartesia_api_key(settings.get("cartesia_api_key", ""))
        )
        self.tts.set_azure_tts_usage(self.azure_tts_usage)
        self.tts.set_google_tts_usage(self.google_tts_usage)
        self.tts.set_elevenlabs_tts_usage(self.elevenlabs_tts_usage)
        self.tts.set_cartesia_tts_usage(self.cartesia_tts_usage)
        self.tts.set_murf_api_key(
            get_murf_api_key(settings.get("murf_api_key", ""))
        )
        self.tts.set_murf_tts_usage(self.murf_tts_usage)
        self.tts.set_word_tts_settings(
            settings.get("word_tts_profile", "same"),
            settings.get("word_tts_voice", ""),
            settings.get("word_tts_mode", "auto"),
            settings.get("word_tts_online_engine", "edge"),
            settings.get("word_tts_offline_engine", "system"),
        )
        self.tts.set_app_dir(self.db.app_dir)
        playback_rate = float(settings.get("playback_rate", "1.0") or 1.0)
        self.tts.set_playback_rate(playback_rate)
        api_key = get_api_key(settings.get("openai_api_key", ""))
        self.translator.set_api_key(api_key)
        apify_api_token = get_apify_api_token(settings.get("apify_api_token", ""))
        google_api_key = get_google_api_key(settings.get("google_api_key", ""))
        deepl_api_key = get_deepl_api_key(settings.get("deepl_api_key", ""))
        self.translator.set_apify_api_token(apify_api_token)
        self.translator.set_google_api_key(google_api_key)
        self.translator.set_deepl_api_key(deepl_api_key)
        self.translator.set_apify_usage_tracker(self.apify_usage)
        self.translator.set_google_usage_tracker(self.google_cloud_usage)
        self.translator.set_deepl_usage_tracker(self.deepl_usage)
        self.translator.set_languages(
            settings.get("book_language", "en"),
            settings.get(
                "translation_language", settings.get("ui_language", "uk")
            ),
        )
        self.translator.set_providers(
            settings.get(
                "translation_block_provider",
                settings.get("translation_provider", "auto"),
            ),
            settings.get("translation_word_provider", "free"),
            settings.get("translation_selection_provider", "apify"),
        )
        self.translator.set_ollama(
            settings.get("ollama_url", "http://127.0.0.1:11434"),
            settings.get("ollama_model", ""),
        )
        self.reading_view.translator = self.translator

    def _check_continue_reading(self) -> None:
        last_book = self.db.get_last_read_book()
        if last_book and last_book.current_block > 0:
            dialog = ContinueDialog(last_book, self)
            if dialog.exec():
                if dialog.result_action == "continue":
                    self._open_book(last_book)
                elif dialog.result_action == "choose":
                    self._switch_page(self.PAGE_LIBRARY)
                # skip: do nothing

    def _resolve_book_file(self, book) -> bool:
        if Path(book.file_path).exists():
            return True
        reply = QMessageBox.question(
            self,
            tr("msg.file_missing_title"),
            tr("msg.file_missing", title=book.title, path=book.file_path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False
        extensions = " ".join(f"*{ext}" for ext in BookParser.supported_extensions())
        new_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("library.find_file"),
            str(Path.home()),
            f"Books ({extensions});;All Files (*)",
        )
        if not new_path:
            return False
        self.db.update_book_file_path(book.id, new_path)
        book.file_path = new_path
        return True

    def _open_book(self, book) -> None:
        if not self._resolve_book_file(book):
            return
        fresh = self.db.get_book(book.id)
        if fresh:
            self.reading_view.load_book(fresh)
            self._switch_page(self.PAGE_READING)
            self._refresh_book_list()

    def _add_book(self) -> None:
        extensions = " ".join(f"*{ext}" for ext in BookParser.supported_extensions())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("import.title"),
            str(Path.home()),
            f"Books ({extensions});;All Files (*)",
        )
        if not file_path:
            return

        if self.db.book_exists(file_path):
            QMessageBox.information(self, "", tr("msg.already_added"))
            return

        try:
            size = Path(file_path).stat().st_size
            if size > MAX_IMPORT_BYTES:
                mb = size / (1024 * 1024)
                max_mb = MAX_IMPORT_BYTES // (1024 * 1024)
                QMessageBox.warning(
                    self, "", tr("msg.file_too_large", mb=f"{mb:.0f}", max_mb=max_mb)
                )
                return
        except OSError:
            pass

        if self._import_thread and self._import_thread.isRunning():
            QMessageBox.information(self, "", tr("msg.wait_import"))
            return

        self._import_dialog = QProgressDialog(tr("import.reading"), tr("dialog.cancel"), 0, 0, self)
        self._import_dialog.setWindowTitle(tr("import.title"))
        self._import_dialog.setMinimumDuration(0)
        self._import_dialog.canceled.connect(self._cancel_import)
        self._import_dialog.show()

        self._start_import_thread(file_path)

    def _import_options(self) -> dict:
        s = self.db.get_all_settings()
        return {
            "block_words_target": int(s.get("block_words_target", "55")),
            "pdf_ocr_mode": s.get("pdf_ocr_mode", "auto"),
            "ocr_language": s.get("book_language", "en"),
            "ocr_max_pages": int(s.get("pdf_ocr_max_pages", "40")),
        }

    def _start_import_thread(self, file_path: str) -> None:
        opts = self._import_options()
        self._import_thread = BookImportThread(file_path, parent=self, **opts)
        self._import_worker = self._import_thread.worker
        worker = self._import_thread.start_import()
        worker.status.connect(self._on_import_status)
        worker.finished.connect(self._on_import_finished)
        worker.failed.connect(self._on_import_failed)
        self._import_thread.finished.connect(self._on_import_thread_done)

    def _cancel_import(self) -> None:
        if self._import_worker:
            self._import_worker.cancel()

    def _on_import_status(self, message: str) -> None:
        self.status_tracker.set_import_status(message)
        if not self._import_dialog:
            return
        if message == "reading":
            self._import_dialog.setLabelText(tr("import.reading"))
        elif message.startswith("blocks:"):
            count = message.split(":", 1)[1]
            self._import_dialog.setLabelText(tr("import.blocks", n=count))
        elif message.startswith("ocr:"):
            _, current, total = message.split(":", 2)
            self._import_dialog.setLabelText(
                tr("import.ocr", current=current, total=total)
            )
        else:
            self._import_dialog.setLabelText(message)

    def _finalize_import(self, result: ParseResult, file_path: str, reimport_id: int = 0) -> None:
        if reimport_id:
            self.db.replace_book_blocks(reimport_id, result.blocks)
            book_id = reimport_id
            if result.cover_bytes:
                cp = self.covers.save_cover(book_id, result.cover_bytes)
                self.db.update_cover_path(book_id, cp)
        else:
            book_id = self.db.add_book(
                result.title,
                result.author,
                file_path,
                result.file_suffix,
                result.blocks,
            )
            if result.cover_bytes:
                cp = self.covers.save_cover(book_id, result.cover_bytes)
                self.db.update_cover_path(book_id, cp)

        book = self.db.get_book(book_id)
        self._refresh_book_list()
        if book and not reimport_id:
            self.reading_view.load_book(book, start_block=0)
            self._switch_page(self.PAGE_READING)
        elif book and reimport_id and self.reading_view.current_book and self.reading_view.current_book.id == book.id:
            self.reading_view.load_book(book)

        msg_key = "msg.reimport_done" if reimport_id else "msg.book_added"
        msg = tr(msg_key, title=result.title, blocks=len(result.blocks))
        if result.warnings:
            warn_text = "\n".join(
                BookParser.warning_message(w) for w in result.warnings
            )
            msg += "\n\n" + tr("msg.import_warnings") + "\n" + warn_text
        QMessageBox.information(self, "", msg)

    def _on_import_finished(self, result: ParseResult, file_path: str) -> None:
        if self._import_dialog:
            self._import_dialog.setLabelText(tr("import.saving"))
        try:
            self._finalize_import(result, file_path)
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), tr("msg.save_failed", error=e))

    def _on_focus_mode(self, enabled: bool) -> None:
        self.sidebar.setVisible(not enabled)
        self.reading_view._update_reading_layout()

    def _on_import_failed(self, message: str) -> None:
        if message == "empty":
            text = tr("msg.import_empty")
        else:
            text = tr("msg.import_failed", error=message)
        QMessageBox.critical(self, tr("import.failed"), text)

    def _on_import_thread_done(self) -> None:
        self.status_tracker.clear_import_status()
        if self._import_dialog:
            self._import_dialog.close()
            self._import_dialog = None
        self._import_thread = None
        self._import_worker = None

    def _on_library_search(self, text: str) -> None:
        self._library_filter = text.strip().lower()
        self._refresh_book_list()

    def _on_sort_changed(self) -> None:
        self._library_sort = self.sort_combo.currentData()
        self._refresh_book_list()

    def _on_tag_filter_changed(self) -> None:
        self._library_tag = self.tag_combo.currentData() or ""
        self._refresh_book_list()

    def _refresh_tag_combo(self) -> None:
        current = self._library_tag
        self.tag_combo.blockSignals(True)
        self.tag_combo.clear()
        self.tag_combo.addItem(tr("library.all_tags"), "")
        for tag in self.db.get_all_tags():
            self.tag_combo.addItem(f"#{tag}", tag)
        if current:
            idx = self.tag_combo.findData(current)
            if idx >= 0:
                self.tag_combo.setCurrentIndex(idx)
        self.tag_combo.blockSignals(False)

    def _update_sort_combo_labels(self) -> None:
        keys = ("recent", "title", "author", "progress", "added")
        for i, key in enumerate(keys):
            self.sort_combo.setItemText(i, tr(f"library.sort.{key}"))

    def _refresh_book_list(self) -> None:
        self._refresh_tag_combo()
        self.book_list.clear()
        for book in self.db.get_all_books(self._library_sort):
            if self._library_filter:
                tags = " ".join(self.db.get_book_tags(book.id))
                haystack = f"{book.title} {book.author} {tags}".lower()
                if self._library_filter not in haystack:
                    continue
            if self._library_tag:
                if self._library_tag not in self.db.get_book_tags(book.id):
                    continue

            missing = "" if Path(book.file_path).exists() else " ⚠"
            tags = self.db.get_book_tags(book.id)
            tag_suffix = f"  [{' · '.join(tags)}]" if tags else ""
            item = QListWidgetItem(
                f"{book.title}{missing}{tag_suffix}  ({book.progress_percent:.0f}%)"
            )
            item.setData(Qt.ItemDataRole.UserRole, book.id)

            cover_path = self.covers.get_cover_path(book.id, book.cover_path)
            if cover_path:
                pix = QPixmap(str(cover_path))
                if not pix.isNull():
                    item.setIcon(QIcon(pix.scaled(42, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))

            self.book_list.addItem(item)

    def _on_book_clicked(self, item: QListWidgetItem) -> None:
        book_id = item.data(Qt.ItemDataRole.UserRole)
        book = self.db.get_book(book_id)
        if book:
            exists = Path(book.file_path).exists()
            item.setToolTip(
                tr(
                    "library.tooltip",
                    title=book.title,
                    percent=f"{book.progress_percent:.0f}",
                    block=book.current_block + 1,
                    path=book.file_path,
                    status=tr("library.file_ok" if exists else "library.file_missing"),
                )
            )

    def _on_book_selected(self, item: QListWidgetItem) -> None:
        book_id = item.data(Qt.ItemDataRole.UserRole)
        book = self.db.get_book(book_id)
        if book:
            self._open_book(book)

    def _open_selected_book(self) -> None:
        item = self.book_list.currentItem()
        if item:
            self._on_book_selected(item)
        else:
            QMessageBox.information(self, "", tr("msg.no_selection"))

    def _remove_selected_book(self) -> None:
        item = self.book_list.currentItem()
        if not item:
            QMessageBox.information(self, "", tr("msg.no_selection"))
            return

        book_id = item.data(Qt.ItemDataRole.UserRole)
        book = self.db.get_book(book_id)
        if not book:
            return

        reply = QMessageBox.question(
            self,
            "",
            tr("msg.remove_book", title=book.title),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.covers.delete_cover(book_id)
            self.db.delete_book(book_id)
            if self.reading_view.current_book and self.reading_view.current_book.id == book_id:
                self.reading_view.current_book = None
                self.reading_view.text_edit.clear()
                self.reading_view.chapter_label.hide()
                self.reading_view._update_controls_state()
            self._refresh_book_list()

    def _reimport_selected_book(self) -> None:
        item = self.book_list.currentItem()
        if not item:
            QMessageBox.information(self, "", tr("msg.no_selection"))
            return

        book_id = item.data(Qt.ItemDataRole.UserRole)
        book = self.db.get_book(book_id)
        if not book:
            return

        if not self._resolve_book_file(book):
            return

        reply = QMessageBox.question(
            self,
            "",
            tr("msg.reimport_confirm", title=book.title),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._import_thread and self._import_thread.isRunning():
            QMessageBox.information(self, "", tr("msg.wait_import"))
            return

        self._reimport_book_id = book_id
        self._import_dialog = QProgressDialog(tr("import.reading"), tr("dialog.cancel"), 0, 0, self)
        self._import_dialog.setWindowTitle(tr("library.reimport"))
        self._import_dialog.setMinimumDuration(0)
        self._import_dialog.canceled.connect(self._cancel_import)
        self._import_dialog.show()

        opts = self._import_options()
        self._import_thread = BookImportThread(book.file_path, parent=self, **opts)
        self._import_worker = self._import_thread.worker
        worker = self._import_thread.start_import()
        worker.status.connect(self._on_import_status)
        worker.finished.connect(self._on_reimport_finished)
        worker.failed.connect(self._on_import_failed)
        self._import_thread.finished.connect(self._on_import_thread_done)

    def _on_reimport_finished(self, result: ParseResult, file_path: str) -> None:
        if self._import_dialog:
            self._import_dialog.setLabelText(tr("import.saving"))
        try:
            self._finalize_import(result, file_path, reimport_id=self._reimport_book_id)
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), tr("msg.save_failed", error=e))

    def _edit_book_tags(self) -> None:
        item = self.book_list.currentItem()
        if not item:
            QMessageBox.information(self, "", tr("msg.no_selection"))
            return
        book_id = item.data(Qt.ItemDataRole.UserRole)
        book = self.db.get_book(book_id)
        if not book:
            return
        dialog = TagsDialog(book.title, self.db.get_book_tags(book_id), self)
        if dialog.exec():
            self.db.set_book_tags(book_id, dialog.tags())
            self._refresh_book_list()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.db, self)
        accepted = dialog.exec()
        if dialog.library_cleared:
            self._on_library_data_cleared()
        if accepted:
            set_language(self.db.get_setting("ui_language", "uk"))
            set_api_key(
                dialog.get_api_key(),
                self.db,
            )
            set_apify_api_token(
                dialog.get_apify_api_token(),
                self.db,
            )
            set_google_api_key(
                dialog.get_google_api_key(),
                self.db,
            )
            set_deepl_api_key(
                dialog.get_deepl_api_key(),
                self.db,
            )
            set_azure_speech_key(
                dialog.get_azure_speech_key(),
                self.db,
            )
            set_google_tts_api_key(
                dialog.get_google_tts_api_key(),
                self.db,
            )
            set_elevenlabs_api_key(
                dialog.get_elevenlabs_api_key(),
                self.db,
            )
            set_cartesia_api_key(
                dialog.get_cartesia_api_key(),
                self.db,
            )
            set_murf_api_key(
                dialog.get_murf_api_key(),
                self.db,
            )
            self._retranslate_ui()
            self._apply_theme()
            self._apply_reading_settings()

    def _on_library_data_cleared(self) -> None:
        self.reading_view.stop_reading()
        self.reading_view.current_book = None
        self.reading_view.text_edit.clear()
        self.reading_view.chapter_label.hide()
        self.reading_view._update_controls_state()
        self.tts.reset_memory_cache()
        self.translator.clear_cache()
        self._refresh_book_list()
        if self._current_page == self.PAGE_STATS:
            self.stats_view.refresh()

    def _on_progress_updated(self) -> None:
        if self._current_page == self.PAGE_STATS:
            self.stats_view.refresh()
        if self._current_page == self.PAGE_LIBRARY:
            self._library_refresh_timer.start()

    def closeEvent(self, event) -> None:
        self.reading_view.stop_reading()
        super().closeEvent(event)

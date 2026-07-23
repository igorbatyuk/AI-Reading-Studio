"""Application themes and styles."""

LIGHT_THEME = """
QMainWindow, QDialog {
    background-color: #f8f6f2;
}
QWidget {
    color: #2c2c2c;
    font-family: "Segoe UI", sans-serif;
}
QPushButton {
    background-color: #4a7c59;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 14px;
    font-weight: 600;
    min-height: 36px;
}
QPushButton:hover {
    background-color: #3d6a4a;
}
QPushButton:pressed {
    background-color: #2f5539;
}
QPushButton:disabled {
    background-color: #c5c5c5;
    color: #888;
}
QPushButton#secondaryBtn {
    background-color: #e8e4dc;
    color: #2c2c2c;
}
QPushButton#secondaryBtn:hover {
    background-color: #d9d4ca;
}
QPushButton#secondaryBtn:disabled {
    background-color: #eceae4;
    color: #aaa;
}
QPushButton#navBtn {
    background-color: transparent;
    color: #2c2c2c;
    text-align: left;
    padding: 12px 14px;
    border-radius: 8px;
    font-weight: 500;
}
QPushButton#navBtn:hover {
    background-color: #ddd9d0;
}
QPushButton#navBtnActive {
    background-color: #4a7c59;
    color: white;
    text-align: left;
    padding: 12px 14px;
    border-radius: 8px;
    font-weight: 600;
}
QWidget#sidebar {
    background-color: #eceae4;
}
QLabel#titleLabel {
    font-size: 24px;
    font-weight: 700;
    color: #2c2c2c;
}
QLabel#statValue {
    font-size: 28px;
    font-weight: 700;
    color: #4a7c59;
}
QLabel#statLabel {
    font-size: 13px;
    color: #666;
}
QLabel#goalComplete {
    color: #4a7c59;
    font-weight: 600;
    font-size: 14px;
}
QLabel#hintLabel {
    color: #888;
    font-size: 12px;
}
QLabel#cardTitle {
    font-weight: 600;
    font-size: 13px;
    color: #2c2c2c;
}
QLabel#statusRowLabel {
    color: #666;
    font-size: 12px;
}
QLabel#statusRowValue, QLabel#statusRowValueActive {
    font-size: 12px;
    font-weight: 600;
    color: #2c2c2c;
}
QLabel#statusRowValueActive {
    color: #9a7b1a;
}
QLabel#statusValueOk {
    font-size: 12px;
    font-weight: 600;
    color: #4a7c59;
}
QLabel#statusValueWorking {
    font-size: 12px;
    font-weight: 600;
    color: #9a7b1a;
}
QLabel#statusValueError {
    font-size: 12px;
    font-weight: 600;
    color: #b54545;
}
QProgressBar#apiUsageBarOk, QProgressBar#apiUsageBarWarn, QProgressBar#apiUsageBarCritical,
QProgressBar#statusMeterOk, QProgressBar#statusMeterWorking, QProgressBar#statusMeterWaiting,
QProgressBar#statusMeterError {
    background: #e8e4dc;
    border: none;
    border-radius: 5px;
}
QProgressBar#apiUsageBarOk::chunk, QProgressBar#statusMeterOk::chunk {
    background: #4a7c59;
    border-radius: 5px;
}
QProgressBar#apiUsageBarWarn::chunk, QProgressBar#statusMeterWorking::chunk,
QProgressBar#statusMeterWaiting::chunk {
    background: #c4a035;
    border-radius: 5px;
}
QProgressBar#apiUsageBarCritical::chunk, QProgressBar#statusMeterError::chunk {
    background: #b54545;
    border-radius: 5px;
}
QLabel#statusBannerOk {
    background: #e8f0ea;
    color: #2d6a3e;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
}
QLabel#statusBannerWorking {
    background: #fff8e6;
    color: #9a7b1a;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
}
QLabel#statusBannerError {
    background: #fdecea;
    color: #b54545;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
}
QLabel#errorLabel {
    color: #b54545;
    font-size: 12px;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QComboBox QAbstractItemView {
    background: white;
    color: #2c2c2c;
    selection-background-color: #4a7c59;
    selection-color: white;
}
QTabBar::tab {
    background: #e8e4dc;
    color: #2c2c2c;
    padding: 8px 16px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
}
QFrame#card {
    background-color: white;
    border-radius: 12px;
    border: 1px solid #e0dcd4;
}
QFrame#readingCard {
    background-color: white;
    border-radius: 16px;
    border: 1px solid #e0dcd4;
}
QTextEdit {
    background: transparent;
    border: none;
}
QListWidget {
    background: white;
    border: 1px solid #e0dcd4;
    border-radius: 8px;
    padding: 4px;
}
QListWidget::item {
    padding: 10px 8px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #4a7c59;
    color: white;
}
QListWidget::item:hover {
    background-color: #e8f0ea;
}
QTabWidget::pane {
    border: 1px solid #e0dcd4;
    border-radius: 8px;
    background: white;
}
QTabBar::tab:selected {
    background: #4a7c59;
    color: white;
    border-radius: 6px 6px 0 0;
}
QComboBox, QSpinBox, QLineEdit {
    padding: 8px 12px;
    border: 1px solid #d0ccc4;
    border-radius: 8px;
    background: white;
    min-height: 20px;
}
QProgressBar {
    border: none;
    border-radius: 6px;
    background-color: #e8e4dc;
    height: 8px;
}
QProgressBar::chunk {
    background-color: #4a7c59;
    border-radius: 6px;
}
QPushButton#calDayDone {
    background-color: #d4edda;
    color: #1e4d2b;
    border: 2px solid #4a7c59;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    padding: 0px;
    margin: 0px;
    min-height: 38px;
    max-height: 38px;
}
QPushButton#calDayDone[today="true"],
QPushButton#calDayPartial[today="true"],
QPushButton#calDayEmpty[today="true"],
QPushButton#calDayFuture[today="true"] {
    border: 2px solid #2d6a3e;
}
QPushButton#calDayDone:hover {
    background-color: #c3e6cb;
}
QPushButton#calDayPartial {
    background-color: #fff3cd;
    color: #856404;
    border: 2px solid #e0c060;
    border-radius: 6px;
    font-size: 11px;
    padding: 0px;
    margin: 0px;
    min-height: 38px;
    max-height: 38px;
}
QPushButton#calDayPartial:hover {
    background-color: #ffe69c;
}
QPushButton#calDayEmpty {
    background-color: #f0ede6;
    color: #999;
    border: 2px solid #ddd9d0;
    border-radius: 6px;
    font-size: 11px;
    padding: 0px;
    margin: 0px;
    min-height: 38px;
    max-height: 38px;
}
QPushButton#calDayEmpty:hover {
    background-color: #e8e4dc;
}
QPushButton#calDayFuture {
    background-color: #eceae4;
    color: #bbb;
    border: 2px solid #ddd9d0;
    border-radius: 6px;
    font-size: 11px;
    padding: 0px;
    margin: 0px;
    min-height: 38px;
    max-height: 38px;
}
QPushButton#calNavBtn {
    background-color: #e8e4dc;
    color: #2c2c2c;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    padding: 0px;
    font-size: 14px;
    font-weight: 700;
}
QPushButton#calNavBtn:hover {
    background-color: #d9d4ca;
}
QPushButton#calNavBtn:disabled {
    background-color: #eceae4;
    color: #ccc;
}
QPushButton#calTodayBtn {
    background-color: #e8e4dc;
    color: #2c2c2c;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 12px;
    min-height: 28px;
    max-height: 28px;
}
QPushButton#calTodayBtn:hover {
    background-color: #d9d4ca;
}
"""

DARK_THEME = """
QMainWindow, QDialog {
    background-color: #1a1a1e;
}
QWidget {
    color: #e8e6e3;
    font-family: "Segoe UI", sans-serif;
}
QPushButton {
    background-color: #5a9e6f;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 14px;
    font-weight: 600;
    min-height: 36px;
}
QPushButton:hover {
    background-color: #4a8a5e;
}
QPushButton:disabled {
    background-color: #3a3a42;
    color: #666;
}
QPushButton#secondaryBtn {
    background-color: #2a2a30;
    color: #e8e6e3;
}
QPushButton#secondaryBtn:hover {
    background-color: #3a3a42;
}
QPushButton#secondaryBtn:disabled {
    background-color: #242428;
    color: #555;
}
QPushButton#navBtn {
    background-color: transparent;
    color: #e8e6e3;
    text-align: left;
    padding: 12px 14px;
    border-radius: 8px;
    font-weight: 500;
}
QPushButton#navBtn:hover {
    background-color: #2a2a30;
}
QPushButton#navBtnActive {
    background-color: #5a9e6f;
    color: white;
    text-align: left;
    padding: 12px 14px;
    border-radius: 8px;
    font-weight: 600;
}
QWidget#sidebar {
    background-color: #242428;
}
QLabel#titleLabel {
    font-size: 24px;
    font-weight: 700;
    color: #e8e6e3;
}
QLabel#statValue {
    font-size: 28px;
    font-weight: 700;
    color: #5a9e6f;
}
QLabel#statLabel {
    font-size: 13px;
    color: #999;
}
QLabel#goalComplete {
    color: #5a9e6f;
    font-weight: 600;
}
QLabel#hintLabel {
    color: #999;
    font-size: 12px;
}
QLabel#cardTitle {
    font-weight: 600;
    font-size: 13px;
    color: #e8e6e3;
}
QLabel#statusRowLabel {
    color: #999;
    font-size: 12px;
}
QLabel#statusRowValue, QLabel#statusRowValueActive {
    font-size: 12px;
    font-weight: 600;
    color: #e8e6e3;
}
QLabel#statusRowValueActive {
    color: #d4b84a;
}
QLabel#statusValueOk {
    font-size: 12px;
    font-weight: 600;
    color: #5a9e6f;
}
QLabel#statusValueWorking {
    font-size: 12px;
    font-weight: 600;
    color: #d4b84a;
}
QLabel#statusValueError {
    font-size: 12px;
    font-weight: 600;
    color: #e07070;
}
QProgressBar#apiUsageBarOk, QProgressBar#apiUsageBarWarn, QProgressBar#apiUsageBarCritical,
QProgressBar#statusMeterOk, QProgressBar#statusMeterWorking, QProgressBar#statusMeterWaiting,
QProgressBar#statusMeterError {
    background: #3a3835;
    border: none;
    border-radius: 5px;
}
QProgressBar#apiUsageBarOk::chunk, QProgressBar#statusMeterOk::chunk {
    background: #5a9e6f;
    border-radius: 5px;
}
QProgressBar#apiUsageBarWarn::chunk, QProgressBar#statusMeterWorking::chunk,
QProgressBar#statusMeterWaiting::chunk {
    background: #d4b84a;
    border-radius: 5px;
}
QProgressBar#apiUsageBarCritical::chunk, QProgressBar#statusMeterError::chunk {
    background: #e07070;
    border-radius: 5px;
}
QLabel#statusBannerOk {
    background: #243028;
    color: #5a9e6f;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
}
QLabel#statusBannerWorking {
    background: #3a3420;
    color: #d4b84a;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
}
QLabel#statusBannerError {
    background: #3a2424;
    color: #e07070;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
}
QLabel#errorLabel {
    color: #e07070;
    font-size: 12px;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QComboBox QAbstractItemView {
    background: #2a2a30;
    color: #e8e6e3;
    selection-background-color: #5a9e6f;
    selection-color: white;
}
QTabBar::tab {
    background: #2a2a30;
    color: #e8e6e3;
    padding: 8px 16px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
}
QTabBar::tab:hover {
    background: #323238;
}
QFrame#card, QFrame#readingCard {
    background-color: #242428;
    border-radius: 12px;
    border: 1px solid #3a3a42;
}
QTextEdit {
    background: transparent;
    border: none;
    color: #e8e6e3;
}
QListWidget {
    background: #242428;
    border: 1px solid #3a3a42;
    border-radius: 8px;
    padding: 4px;
}
QListWidget::item {
    padding: 10px 8px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #5a9e6f;
    color: white;
}
QListWidget::item:hover {
    background-color: #2f3f34;
}
QTabWidget::pane {
    border: 1px solid #3a3a42;
    border-radius: 8px;
    background: #242428;
}
QTabBar::tab:selected {
    background: #5a9e6f;
    color: white;
    border-radius: 6px 6px 0 0;
}
QComboBox, QSpinBox, QLineEdit {
    padding: 8px 12px;
    border: 1px solid #3a3a42;
    border-radius: 8px;
    background: #2a2a30;
    color: #e8e6e3;
    min-height: 20px;
}
QProgressBar {
    border: none;
    border-radius: 6px;
    background-color: #3a3a42;
    height: 8px;
}
QProgressBar::chunk {
    background-color: #5a9e6f;
    border-radius: 6px;
}
QPushButton#calDayDone {
    background-color: #1e3d28;
    color: #a8e6b8;
    border: 2px solid #5a9e6f;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    padding: 0px;
    margin: 0px;
    min-height: 38px;
    max-height: 38px;
}
QPushButton#calDayDone[today="true"],
QPushButton#calDayPartial[today="true"],
QPushButton#calDayEmpty[today="true"],
QPushButton#calDayFuture[today="true"] {
    border: 2px solid #7bc492;
}
QPushButton#calDayDone:hover {
    background-color: #2a4d34;
}
QPushButton#calDayPartial {
    background-color: #3d3520;
    color: #f0d878;
    border: 2px solid #a08030;
    border-radius: 6px;
    font-size: 11px;
    padding: 0px;
    margin: 0px;
    min-height: 38px;
    max-height: 38px;
}
QPushButton#calDayPartial:hover {
    background-color: #4a4028;
}
QPushButton#calDayEmpty {
    background-color: #2a2a30;
    color: #666;
    border: 2px solid #3a3a42;
    border-radius: 6px;
    font-size: 11px;
    padding: 0px;
    margin: 0px;
    min-height: 38px;
    max-height: 38px;
}
QPushButton#calDayEmpty:hover {
    background-color: #323238;
}
QPushButton#calDayFuture {
    background-color: #242428;
    color: #555;
    border: 2px solid #3a3a42;
    border-radius: 6px;
    font-size: 11px;
    padding: 0px;
    margin: 0px;
    min-height: 38px;
    max-height: 38px;
}
QPushButton#calNavBtn {
    background-color: #2a2a30;
    color: #e8e6e3;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    padding: 0px;
    font-size: 14px;
    font-weight: 700;
}
QPushButton#calNavBtn:hover {
    background-color: #3a3a42;
}
QPushButton#calNavBtn:disabled {
    background-color: #242428;
    color: #555;
}
QPushButton#calTodayBtn {
    background-color: #2a2a30;
    color: #e8e6e3;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 12px;
    min-height: 28px;
    max-height: 28px;
}
QPushButton#calTodayBtn:hover {
    background-color: #3a3a42;
}
"""

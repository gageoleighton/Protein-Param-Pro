"""Application-wide Qt stylesheet."""

STYLE = """
QMainWindow, QDialog { background: #f6f6f4; color: #303234; }
QLabel { color: #303234; }
QToolBar { background: #ffffff; border: none; border-bottom: 1px solid #dfdfdc; spacing: 8px; padding: 8px; }
QToolButton { color: #45484a; font-weight: 600; padding: 7px 10px; border-radius: 5px; } QToolButton:hover { background: #f0f0ee; }
#sidebar { background: #343638; color: #e8e8e5; } #brand { color: #ffffff; font-size: 15px; font-weight: 800; letter-spacing: 1px; padding: 6px 0; } #brandImage { background: #ffffff; border-radius: 7px; } #brandImage:hover { background: #f2f2f0; }
#sidebar QLabel { color: #e8e8e5; }
#sidebar QPushButton { background: #55585a; color: #ffffff; text-align: left; border: none; padding: 10px; border-radius: 5px; font-weight: 700; } #sidebar QPushButton:hover { background: #66696a; }
#navlabel { color: #aaacab; font-size: 10px; font-weight: 700; padding: 18px 5px 5px; } #sidebar QTreeWidget { background: transparent; border: none; color: #eeeeeb; outline: none; } #sidebar QTreeWidget::item { padding: 6px 3px; border-radius: 4px; } #sidebar QTreeWidget::item:selected { background: #4b4e50; }
#heading { color: #252729; font-size: 27px; font-weight: 750; } #subheading { color: #686b6d; font-size: 13px; }
QTableWidget { background: #ffffff; color: #303234; alternate-background-color: #fbfbfa; border: 1px solid #dfdfdc; border-radius: 7px; gridline-color: #eeeeeb; } QTableWidget::item { color: #303234; padding: 10px 8px; } QTableWidget::item:selected { background: #e9e9e6; color: #303234; } QHeaderView::section { background: #f3f3f1; color: #5c5f61; border: none; border-bottom: 1px solid #dfdfdc; padding: 11px 8px; font-weight: 700; }
#detail, #analysis { background: #ffffff; border: 1px solid #dfdfdc; border-radius: 7px; } #analysis:hover { border-color: #bfc1bc; } #concentration { color: #3c4140; font-size: 16px; font-weight: 750; padding-left: 10px; } #analysisHeading, #dialogTitle { color: #303234; font-size: 14px; font-weight: 750; } #dialogTitle { font-size: 20px; } #dialogSubtitle, #analysisMetricLabel, #composition { color: #686b6d; font-size: 11px; } #analysisValue, #dialogMetricValue { color: #303234; font-size: 17px; font-weight: 750; } #dialogMetricValue { font-size: 14px; } #dialogSectionTitle { color: #303234; font-size: 14px; font-weight: 750; padding-top: 8px; } #composition { padding-top: 3px; } QLineEdit, QTextEdit, QComboBox { background: #ffffff; color: #303234; border: 1px solid #cfcfcb; border-radius: 5px; padding: 6px; } QLineEdit::placeholder, QTextEdit::placeholder { color: #858785; } QDialogButtonBox QPushButton { color: #303234; background: #ffffff; border: 1px solid #cfcfcb; border-radius: 5px; padding: 7px 12px; } QStatusBar { color: #747674; }
QLineEdit#proteinAbsorbanceInput { font-size: 18px; font-weight: 500; padding: 3px 6px; min-height: 26px; }
"""

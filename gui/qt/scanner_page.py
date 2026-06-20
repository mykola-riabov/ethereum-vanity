"""Balance scanner page for the Qt GUI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chains import DEFAULT_CHAIN, EVM_CHAINS, chain_keys, chain_label
from gui.qt.found_wallets_table import FoundWalletsPanel
from gui.qt.scan_runner import ScanThread
from gui.qt.widgets import Card, form_row
from scanner import ScanConfig, resolve_input_files
from workspace import WorkspaceLayout, default_workspace, ensure_workspace


class ScannerPage(QWidget):
    def __init__(self, *, theme_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme_name = theme_name
        self._scan_thread: ScanThread | None = None
        self._last_progress_log = 0
        self._workspace = ensure_workspace(default_workspace())
        self._build_ui()
        self._refresh_workspace_labels()

    def set_theme_name(self, name: str) -> None:
        self._theme_name = name

    def set_workspace(self, layout: WorkspaceLayout) -> None:
        self._workspace = layout
        self._refresh_workspace_labels()

    def _refresh_workspace_labels(self) -> None:
        if not hasattr(self, "_scan_from"):
            return
        self._scan_from.setText(f"{self._workspace.generated_dir}/")
        self._scan_from.setToolTip(str(self._workspace.generated_dir))
        self._results_dir.setText(f"{self._workspace.found_dir}/")
        self._results_dir.setToolTip(str(self._workspace.found_dir))
        self._cache_path.setText(str(self._workspace.cache_file))
        self._cache_path.setToolTip(str(self._workspace.cache_file))

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 8, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)

        prog = Card("Progress")
        self._progress_label = QLabel("Ready — scans all *.jsonl in workspace generated/")
        prog.body_layout.addWidget(self._progress_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(False)
        prog.body_layout.addWidget(self._progress_bar)
        grid.addWidget(prog, 0, 0, 1, 2)

        paths = Card("Workspace paths")
        self._scan_from = QLabel()
        self._scan_from.setObjectName("cardDim")
        self._scan_from.setWordWrap(True)
        self._results_dir = QLabel()
        self._results_dir.setObjectName("cardDim")
        self._results_dir.setWordWrap(True)
        self._cache_path = QLabel()
        self._cache_path.setObjectName("cardDim")
        self._cache_path.setWordWrap(True)
        paths.body_layout.addLayout(form_row("Scan from", self._scan_from))
        paths.body_layout.addLayout(form_row("Found wallets", self._results_dir))
        paths.body_layout.addLayout(form_row("Cache", self._cache_path))
        hint = QLabel(
            "Scanner reads every wallet file in generated/. "
            "Cache skips already-checked addresses — safe to stop and resume."
        )
        hint.setObjectName("cardHint")
        paths.body_layout.addWidget(hint)
        grid.addWidget(paths, 1, 0)

        endpoint = Card("Network")
        self._chain = QComboBox()
        for key in chain_keys():
            self._chain.addItem(chain_label(key), key)
        self._chain.setCurrentIndex(chain_keys().index(DEFAULT_CHAIN))
        self._chain.currentIndexChanged.connect(self._on_chain_changed)
        self._rpc = QLineEdit(EVM_CHAINS[DEFAULT_CHAIN]["rpc"])
        self._workers = QSpinBox()
        self._workers.setRange(1, 64)
        self._workers.setValue(10)
        endpoint.body_layout.addLayout(form_row("Chain", self._chain))
        endpoint.body_layout.addLayout(form_row("RPC URL", self._rpc))
        endpoint.body_layout.addLayout(form_row("Workers", self._workers))
        rpc_hint = QLabel(
            "Uses JSON-RPC eth_getBalance. Same 0x address is checked on the selected chain only."
        )
        rpc_hint.setObjectName("cardHint")
        endpoint.body_layout.addWidget(rpc_hint)
        grid.addWidget(endpoint, 1, 1)

        found_card = Card("Found wallets")
        self._found_panel = FoundWalletsPanel()
        self._found_panel._open_dir_btn.clicked.connect(self._open_results_dir)
        found_card.body_layout.addWidget(self._found_panel)
        grid.addWidget(found_card, 2, 0, 1, 2)

        log_card = Card("Scan log")
        self._log = QTextEdit()
        self._log.setObjectName("logView")
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(140)
        log_card.body_layout.addWidget(self._log)
        grid.addWidget(log_card, 3, 0, 1, 2)
        grid.setRowStretch(2, 2)
        grid.setRowStretch(3, 1)

        actions = QHBoxLayout()
        self._start_btn = QPushButton("START SCAN")
        self._start_btn.setObjectName("accentBtn")
        self._start_btn.clicked.connect(self._start)
        self._stop_btn = QPushButton("STOP")
        self._stop_btn.setObjectName("dangerBtn")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        actions.addWidget(self._start_btn)
        actions.addWidget(self._stop_btn)
        actions.addStretch()
        outer.addLayout(actions)

        self._append_log("Scans wallets from the workspace generated/ folder via JSON-RPC.")

    def _selected_chain_key(self) -> str:
        return str(self._chain.currentData() or DEFAULT_CHAIN)

    def _on_chain_changed(self) -> None:
        key = self._selected_chain_key()
        info = EVM_CHAINS.get(key, EVM_CHAINS[DEFAULT_CHAIN])
        if key != "custom" and info["rpc"]:
            self._rpc.setText(info["rpc"])

    def _open_results_dir(self) -> None:
        self._found_panel.open_results_dir(str(self._workspace.found_dir))

    def _append_log(self, line: str) -> None:
        self._log.append(line)

    def _set_running(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._progress_bar.setVisible(running)

    def _config_from_ui(self) -> ScanConfig:
        chain_key = self._selected_chain_key()
        chain_info = EVM_CHAINS.get(chain_key, EVM_CHAINS[DEFAULT_CHAIN])
        return ScanConfig(
            input_files=[str(self._workspace.generated_dir)],
            rpc_url=self._rpc.text().strip(),
            chain=chain_key,
            chain_symbol=chain_info["symbol"],
            num_workers=int(self._workers.value()),
            result_dir=str(self._workspace.found_dir),
            cache_file=str(self._workspace.cache_file),
        )

    def _start(self) -> None:
        if self._scan_thread and self._scan_thread.isRunning():
            return
        try:
            config = self._config_from_ui()
            files = resolve_input_files(config)
            if not files:
                raise ValueError(
                    f"No wallet files in {self._workspace.generated_dir}/. "
                    "Generate addresses first on the Generator page."
                )
            if not config.rpc_url:
                raise ValueError("RPC URL is required.")
        except ValueError as e:
            QMessageBox.critical(self, "Invalid input", str(e))
            return

        chain_name = EVM_CHAINS.get(config.chain, {}).get("name", config.chain)
        self._append_log("——— Starting balance scan ———")
        self._append_log(f"Workspace: {self._workspace.root}")
        self._append_log(f"Chain: {chain_name}")
        self._found_panel.clear()
        self._last_progress_log = 0
        self._set_running(True)
        self._progress_label.setText("Connecting…")

        self._scan_thread = ScanThread(config, self)
        self._scan_thread.message.connect(self._handle_message)
        self._scan_thread.finished_scan.connect(self._on_thread_finished)
        self._scan_thread.start()

    def _stop(self) -> None:
        if self._scan_thread and self._scan_thread.isRunning():
            self._progress_label.setText("Stopping…")
            self._append_log("Stop requested…")
            self._scan_thread.stop()

    def _on_thread_finished(self) -> None:
        self._set_running(False)
        if self._progress_label.text() in ("Stopping…", "Connecting…"):
            self._progress_label.setText("Stopped")
        self._scan_thread = None

    def _handle_message(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "info":
            self._append_log(
                f"RPC: {msg.get('rpc')} | chain: {msg.get('chain')} | unit: {msg.get('unit')}"
            )
            cache_size = msg.get("cache_size", 0)
            if cache_size:
                self._append_log(
                    f"Resume cache: {cache_size:,} address(es) in {msg.get('cache_file')} (will skip)"
                )
            for f in msg.get("files", []):
                self._append_log(f"  • {f}")
        elif kind == "file_start":
            self._append_log(f"Scanning {msg.get('file')}…")
            self._progress_label.setText(f"Scanning {Path(msg.get('file', '')).name}…")
        elif kind == "progress":
            checked = msg.get("checked", 0)
            self._progress_label.setText(
                f"Checked: {checked:,}  ·  skipped {msg.get('skipped', 0):,}  ·  "
                f"found {msg.get('found', 0)}  ·  errors {msg.get('errors', 0)}"
            )
            if checked - self._last_progress_log >= 50_000:
                self._last_progress_log = checked
                self._append_log(
                    f"… checked {checked:,}, found {msg.get('found', 0)} so far"
                )
        elif kind == "found":
            address = msg.get("address", "")
            amount = int(msg.get("amount", 0))
            unit = msg.get("denom", "wei")
            symbol = msg.get("chain_symbol", "")
            if address:
                self._found_panel.add_found(address, amount, unit, symbol=symbol)
        elif kind == "cache_flush":
            self._append_log(f"Cache saved ({msg.get('cache_size', 0):,} addresses)")
        elif kind == "file_done":
            out_jsonl = msg.get("out_jsonl")
            if out_jsonl:
                loaded = self._found_panel.load_jsonl(out_jsonl, replace=True)
                if loaded:
                    self._append_log(f"Loaded {loaded:,} found wallet(s) from {out_jsonl}")
            self._append_log(
                f"File done: found {msg.get('found', 0)}, checked {msg.get('checked', 0):,}, "
                f"skipped {msg.get('skipped', 0):,}"
            )
        elif kind == "done":
            self._progress_label.setText("Done")
            n = self._found_panel.count
            self._append_log(
                f"Done. {n:,} wallet(s) with balance · "
                f"checked {msg.get('checked', 0):,} · skipped {msg.get('skipped', 0):,} · "
                f"errors {msg.get('errors', 0)}"
            )
            self._append_log(f"Results: {msg.get('result_dir')} | cache: {msg.get('cache_file')}")
        elif kind == "stopped":
            self._progress_label.setText("Stopped")
            self._append_log(
                f"Stopped. Found {msg.get('found', 0)}, checked {msg.get('checked', 0):,}"
            )
        elif kind == "error":
            self._progress_label.setText("Error")
            QMessageBox.critical(self, "Error", msg.get("message", "Unknown error"))
            self._append_log(f"ERROR: {msg.get('message')}")

    def is_running(self) -> bool:
        return self._scan_thread is not None and self._scan_thread.isRunning()

    def request_stop(self) -> None:
        if self.is_running():
            self._stop()

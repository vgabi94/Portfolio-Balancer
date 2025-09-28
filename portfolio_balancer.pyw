import sys
import json
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QPushButton, QHBoxLayout, QLineEdit, QLabel, QMessageBox, QStatusBar,
    QFileDialog, QComboBox, QDialog, QFormLayout, QDoubleSpinBox, QHeaderView,
    QSplitter, QToolBar, QScrollArea, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QAction
import yfinance as yf

class Holding:
    def __init__(self, name, ticker, quantity, allocation, market_price=0.0):
        self.name = name
        self.ticker = ticker
        self.quantity = quantity
        self.allocation = allocation  # Target allocation in %
        self.market_price = market_price
        self.total_value = self.market_price * self.quantity
        self.real_allocation = 0.0
        self.deviation = 0.0

    def update_price(self):
        try:
            stock = yf.Ticker(self.ticker)
            self.market_price = stock.history(period="1d")['Close'].iloc[-1]
            self.total_value = self.market_price * self.quantity
        except Exception as e:
            raise ValueError(f"Error fetching price for {self.ticker}: {e}")

    def to_dict(self):
        return {
            'name': self.name,
            'ticker': self.ticker,
            'quantity': self.quantity,
            'allocation': self.allocation,
            'market_price': self.market_price
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data['name'], data['ticker'], data['quantity'], data['allocation'], data.get('market_price', 0.0))

class Portfolio:
    def __init__(self, name="My Portfolio", currency="USD"):
        self.name = name
        self.holdings = []
        self.currency = currency
        self.saved = True
        self.file_path = None
        self.history = []  # For undo/redo
        self.history_index = -1

    def add_holding(self, holding):
        self.holdings.append(holding)
        self._update_real_allocations()
        self.saved = False
        self._save_state()

    def remove_holding(self, index):
        del self.holdings[index]
        self._update_real_allocations()
        self.saved = False
        self._save_state()

    def edit_holding(self, index, name, ticker, quantity, allocation):
        holding = self.holdings[index]
        holding.name = name
        holding.ticker = ticker
        holding.quantity = quantity
        holding.allocation = allocation
        self._update_real_allocations()
        self.saved = False
        self._save_state()

    def update_prices(self):
        for holding in self.holdings:
            holding.update_price()
        self._update_real_allocations()

    def _update_real_allocations(self):
        total_value = self.total_value()
        if total_value == 0:
            return
        for holding in self.holdings:
            holding.total_value = holding.market_price * holding.quantity
            holding.real_allocation = (holding.total_value / total_value) * 100 if total_value > 0 else 0
            holding.deviation = holding.real_allocation - holding.allocation

    def total_value(self):
        return sum(h.total_value for h in self.holdings)

    def total_allocation(self):
        return sum(h.allocation for h in self.holdings)

    def save(self, file_path=None):
        if file_path:
            self.file_path = file_path
        if not self.file_path:
            return False
        data = {
            'name': self.name,
            'currency': self.currency,
            'holdings': [h.to_dict() for h in self.holdings]
        }
        with open(self.file_path, 'w') as f:
            json.dump(data, f)
        self.saved = True
        return True

    def load(self, file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
        self.name = data['name']
        self.currency = data['currency']
        self.holdings = [Holding.from_dict(h) for h in data['holdings']]
        self.file_path = file_path
        self.saved = True
        self.history = []
        self.history_index = -1
        self._update_real_allocations()
        self._save_state()

    def _save_state(self):
        state = {
            'holdings': [h.to_dict() for h in self.holdings],
            'name': self.name,
            'currency': self.currency
        }
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index + 1]
        self.history.append(state)
        self.history_index = len(self.history) - 1

    def undo(self):
        if self.history_index > 0:
            self.history_index -= 1
            self._restore_state(self.history[self.history_index])
            self.saved = False

    def redo(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self._restore_state(self.history[self.history_index])
            self.saved = False

    def _restore_state(self, state):
        self.name = state['name']
        self.currency = state['currency']
        self.holdings = [Holding.from_dict(h) for h in state['holdings']]
        self._update_real_allocations()

    def suggest_invest(self, amount, buy_only=False):
        total_allocation = self.total_allocation()
        if total_allocation == 0:
            return []
        suggestions = []
        current_total = self.total_value()
        if not buy_only:
            for h in self.holdings:
                target_value = (h.allocation / 100) * (current_total + amount)
                delta_value = target_value - h.total_value
                qty_change = delta_value / h.market_price if h.market_price > 0 else 0
                suggestions.append((h.ticker, qty_change, delta_value))
        else:
            # Distribute amount only among underallocated holdings proportionally
            under_holdings = [h for h in self.holdings if h.real_allocation < h.allocation]
            if not under_holdings:
                return []
            S = sum(h.allocation for h in under_holdings)
            if S == 0:
                return []
            for h in under_holdings:
                allocated = (h.allocation / S) * amount
                qty_change = allocated / h.market_price if h.market_price > 0 else 0
                suggestions.append((h.ticker, qty_change, allocated))
        return suggestions

    def rebalance(self):
        suggestions = []
        total_value = self.total_value()
        for h in self.holdings:
            target_value = (h.allocation / 100) * total_value
            delta_value = target_value - h.total_value
            qty_change = delta_value / h.market_price if h.market_price > 0 else 0
            suggestions.append((h.ticker, qty_change, delta_value))
        return suggestions

    def reallocate(self, new_allocations):
        # new_allocations: dict of ticker to new allocation %
        suggestions = []
        total_value = self.total_value()
        for h in self.holdings:
            new_alloc = new_allocations.get(h.ticker, h.allocation)
            h.allocation = new_alloc  # Update the target allocation
            target_value = (new_alloc / 100) * total_value
            delta_value = target_value - h.total_value
            qty_change = delta_value / h.market_price if h.market_price > 0 else 0
            suggestions.append((h.ticker, qty_change, delta_value))
        self._update_real_allocations()
        self.saved = False
        self._save_state()
        return suggestions

class EditHoldingDialog(QDialog):
    def __init__(self, holding=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Holding" if holding else "Add Holding")
        layout = QFormLayout(self)
        
        self.name_edit = QLineEdit(holding.name if holding else "")
        layout.addRow("Name:", self.name_edit)
        
        self.ticker_edit = QLineEdit(holding.ticker if holding else "")
        layout.addRow("Ticker:", self.ticker_edit)
        
        self.quantity_spin = QDoubleSpinBox()
        self.quantity_spin.setRange(0, 1e6)
        self.quantity_spin.setDecimals(4)  # 4 decimal precision
        self.quantity_spin.setValue(holding.quantity if holding else 0)
        layout.addRow("Quantity:", self.quantity_spin)
        
        self.allocation_spin = QDoubleSpinBox()
        self.allocation_spin.setRange(0, 100)
        self.allocation_spin.setValue(holding.allocation if holding else 0)
        layout.addRow("Allocation (%):", self.allocation_spin)
        
        # Dynamic name fetch for add mode and edit mode if name is empty
        if not holding or holding.name == "":
            self.ticker_edit.editingFinished.connect(self.fetch_name_from_yfinance)
        
        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addRow(buttons)
    
    def fetch_name_from_yfinance(self):
        text = self.ticker_edit.text()
        if not text:
            self.name_edit.setText("")
            return
        try:
            stock = yf.Ticker(text.upper())
            info = stock.info
            name = info.get('longName', '') or info.get('shortName', '')
            self.name_edit.setText(name)
        except Exception:
            self.name_edit.setText("")  # Clear if fetch fails

class ReallocateDialog(QDialog):
    def __init__(self, holdings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reallocate")
        layout = QVBoxLayout(self)
        self.alloc_edits = {}
        form_layout = QFormLayout()
        for h in holdings:
            spin = QDoubleSpinBox()
            spin.setRange(0, 100)
            spin.setValue(h.allocation)
            form_layout.addRow(f"{h.ticker} Allocation (%):", spin)
            self.alloc_edits[h.ticker] = spin
        layout.addLayout(form_layout)
        
        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def get_allocations(self):
        return {ticker: spin.value() for ticker, spin in self.alloc_edits.items()}

class InvestDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Invest Amount")
        layout = QFormLayout(self)
        
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 1e9)
        layout.addRow("Amount to Invest:", self.amount_spin)
        
        self.buy_only_check = QComboBox()  # Using ComboBox for simplicity
        self.buy_only_check.addItems(["No", "Yes"])
        layout.addRow("Buy Only:", self.buy_only_check)
        
        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addRow(buttons)

class PortfolioBalancer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Portfolio Balancer")
        self.setGeometry(100, 100, 1200, 800)
        self.portfolio = Portfolio()
        self.currency_symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Toolbar
        self.toolbar = QToolBar("Tools")
        self.addToolBar(self.toolbar)
        
        add_action = QAction("Add Holding", self)
        add_action.triggered.connect(self.add_holding)
        self.toolbar.addAction(add_action)
        
        edit_action = QAction("Edit Holding", self)
        edit_action.triggered.connect(self.edit_holding)
        self.toolbar.addAction(edit_action)
        
        remove_action = QAction("Remove Holding", self)
        remove_action.triggered.connect(self.remove_holding)
        self.toolbar.addAction(remove_action)
        
        update_prices_action = QAction("Update Prices", self)
        update_prices_action.triggered.connect(self.update_prices)
        self.toolbar.addAction(update_prices_action)
        
        invest_action = QAction("Invest", self)
        invest_action.triggered.connect(self.invest)
        self.toolbar.addAction(invest_action)
        
        rebalance_action = QAction("Rebalance", self)
        rebalance_action.triggered.connect(self.rebalance)
        self.toolbar.addAction(rebalance_action)
        
        reallocate_action = QAction("Reallocate", self)
        reallocate_action.triggered.connect(self.reallocate)
        self.toolbar.addAction(reallocate_action)
        
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_portfolio)
        self.toolbar.addAction(save_action)
        
        save_as_action = QAction("Save As", self)
        save_as_action.triggered.connect(self.save_as_portfolio)
        self.toolbar.addAction(save_as_action)
        
        load_action = QAction("Load", self)
        load_action.triggered.connect(self.load_portfolio)
        self.toolbar.addAction(load_action)
        
        undo_action = QAction("Undo", self)
        undo_action.triggered.connect(self.undo)
        self.toolbar.addAction(undo_action)
        
        redo_action = QAction("Redo", self)
        redo_action.triggered.connect(self.redo)
        self.toolbar.addAction(redo_action)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Portfolio name (editable)
        name_layout = QHBoxLayout()
        name_label = QLabel("Portfolio Name:")
        name_layout.addWidget(name_label)
        self.name_edit = QLineEdit(self.portfolio.name)
        self.name_edit.editingFinished.connect(self.update_portfolio_name)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Currency selector
        currency_layout = QHBoxLayout()
        currency_label = QLabel("Currency:")
        currency_layout.addWidget(currency_label)
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(self.currency_symbols.keys())
        self.currency_combo.setCurrentText(self.portfolio.currency)
        self.currency_combo.currentTextChanged.connect(self.change_currency)
        currency_layout.addWidget(self.currency_combo)
        layout.addLayout(currency_layout)
        
        # Total value display
        self.total_value_label = QLabel("Total Value: 0.0000")
        layout.addWidget(self.total_value_label)
        
        # Table for holdings
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Name", "Ticker", "Quantity", "Allocation %", "Market Price", "Total Value",
            "Real Allocation %", "Deviation %", "Index"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().sortIndicatorChanged.connect(self.sort_table)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)  # Make table non-editable
        self.table.setColumnHidden(8, True)  # Hide the index column
        self.table.itemDoubleClicked.connect(self.handle_double_click)

        # Suggestions display area (scrollable list of checkable items)
        self.suggestions_container = QWidget()
        self.suggestions_layout = QVBoxLayout(self.suggestions_container)
        self.suggestions_layout.setContentsMargins(0, 0, 0, 0)
        self.suggestions_layout.setSpacing(5)
        self.suggestions_scroll = QScrollArea()
        self.suggestions_scroll.setWidget(self.suggestions_container)
        self.suggestions_scroll.setWidgetResizable(True)

        # Splitter to make suggestions collapsible
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.suggestions_scroll)
        splitter.setCollapsible(0, False)  # Table cannot be collapsed
        splitter.setCollapsible(1, True)   # Suggestions can be collapsed
        splitter.setSizes([400, 100])      # Initial sizes (adjust as needed)
        layout.addWidget(splitter)

        # Initial update
        self.update_table()
        self.update_total_value()
        
        # Prompt save on close
        self.setAttribute(Qt.WA_DeleteOnClose)

    def closeEvent(self, event):
        if not self.portfolio.saved:
            reply = QMessageBox.question(self, "Save Portfolio", "Do you want to save changes before closing?",
                                         QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                if not self.save_portfolio():
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()

    def show_message(self, msg, error=False):
        self.status_bar.showMessage(msg, 5000)
        if error:
            palette = self.status_bar.palette()
            palette.setColor(QPalette.WindowText, QColor("red"))
            self.status_bar.setPalette(palette)
        else:
            palette = self.status_bar.palette()
            palette.setColor(QPalette.WindowText, QColor("#e0e0e0"))
            self.status_bar.setPalette(palette)

    def update_portfolio_name(self):
        new_name = self.name_edit.text()
        if new_name != self.portfolio.name:
            self.portfolio.name = new_name
            self.portfolio.saved = False
            self.portfolio._save_state()

    def change_currency(self, currency):
        self.portfolio.currency = currency
        self.portfolio.saved = False
        self.portfolio._save_state()
        self.update_table()
        self.update_total_value()

    def add_holding(self):
        dialog = EditHoldingDialog()
        if dialog.exec() == QDialog.Accepted:
            name = dialog.name_edit.text()
            ticker = dialog.ticker_edit.text().upper()
            quantity = dialog.quantity_spin.value()
            allocation = dialog.allocation_spin.value()
            try:
                holding = Holding(name, ticker, quantity, allocation)
                holding.update_price()
                self.portfolio.add_holding(holding)
                self.update_table()
                self.check_allocations()
            except ValueError as e:
                self.show_message(str(e), error=True)

    def _edit_holding_dialog(self, row):
        if row < 0:
            self.show_message("Select a holding to edit.", error=True)
            return
        original_index = int(self.table.item(row, 8).text())
        holding = self.portfolio.holdings[original_index]
        dialog = EditHoldingDialog(holding)
        if dialog.exec() == QDialog.Accepted:
            name = dialog.name_edit.text()
            ticker = dialog.ticker_edit.text().upper()
            quantity = dialog.quantity_spin.value()
            allocation = dialog.allocation_spin.value()
            try:
                self.portfolio.edit_holding(original_index, name, ticker, quantity, allocation)
                self.portfolio.holdings[original_index].update_price()  # Update price if ticker changed
                self.update_table()
                self.check_allocations()
            except ValueError as e:
                self.show_message(str(e), error=True)
    
    def edit_holding(self):
        row = self.table.currentRow()
        self._edit_holding_dialog(row)

    def handle_double_click(self, item):
        row = item.row()
        self._edit_holding_dialog(row)

    def remove_holding(self):
        row = self.table.currentRow()
        if row < 0:
            self.show_message("Select a holding to remove.", error=True)
            return
        original_index = int(self.table.item(row, 8).text())
        reply = QMessageBox.question(self, "Remove Holding", "Are you sure you want to remove this holding?")
        if reply == QMessageBox.Yes:
            self.portfolio.remove_holding(original_index)
            self.update_table()
            self.check_allocations()


    def update_prices(self):
        try:
            self.portfolio.update_prices()
            self.update_table()
            self.show_message("Prices updated successfully.")
        except ValueError as e:
            self.show_message(str(e), error=True)

    def invest(self):
        dialog = InvestDialog()
        if dialog.exec() == QDialog.Accepted:
            amount = dialog.amount_spin.value()
            buy_only = dialog.buy_only_check.currentText() == "Yes"
            suggestions = self.portfolio.suggest_invest(amount, buy_only)
            self.show_suggestions(suggestions, "Investment Suggestions")

    def rebalance(self):
        suggestions = self.portfolio.rebalance()
        self.show_suggestions(suggestions, "Rebalance Suggestions")

    def reallocate(self):
        dialog = ReallocateDialog(self.portfolio.holdings)
        if dialog.exec() == QDialog.Accepted:
            new_allocs = dialog.get_allocations()
            if sum(new_allocs.values()) > 100:
                self.show_message("New allocations exceed 100%.", error=True)
                return
            suggestions = self.portfolio.reallocate(new_allocs)
            self.show_suggestions(suggestions, "Reallocation Suggestions")
            self.update_table()  # Refresh table to show updated allocations
            self.check_allocations()

    def show_suggestions(self, suggestions, title):
        # Clear existing suggestions
        while self.suggestions_layout.count():
            item = self.suggestions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not suggestions:
            label = QLabel(f"{title}\nNo suggestions available.")
            label.setStyleSheet("color: #e0e0e0;")
            self.suggestions_layout.addWidget(label)
            return
        
        # Add title
        title_label = QLabel(title)
        self.suggestions_layout.addWidget(title_label)
        
        symbol = self.currency_symbols.get(self.portfolio.currency, "")
        for ticker, qty, value in suggestions:
            action = "Buy" if qty > 0 else "Sell"
            original_text = f"{action} {abs(qty):.4f} of {ticker} ({symbol}{value:.4f})"
            
            # Create horizontal layout for checkbox + label
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.setSpacing(5)
            
            checkbox = QCheckBox()
            label = QLabel(original_text)
            label.setStyleSheet("color: #e0e0e0; font-weight: normal; font-size: 16px;")
            
            def toggle_strikethrough(checked, lbl=label, orig=original_text):
                if checked:
                    lbl.setText(f"<s>{orig}</s>")
                    lbl.setStyleSheet("color: #a0a0a0; font-weight: normal; font-size: 16px;")
                else:
                    lbl.setText(orig)
                    lbl.setStyleSheet("color: #e0e0e0; font-weight: normal; font-size: 16px;")
            
            checkbox.toggled.connect(toggle_strikethrough)
            h_layout.addWidget(checkbox)
            h_layout.addWidget(label)
            h_layout.addStretch()  # Align to left
            
            container = QWidget()
            container.setLayout(h_layout)
            self.suggestions_layout.addWidget(container)
        
        self.suggestions_layout.addStretch()  # Push items to top


    def save_portfolio(self):
        if not self.portfolio.file_path:
            return self.save_as_portfolio()
        if self.portfolio.save():
            self.show_message("Portfolio saved.")
            return True
        return False

    def save_as_portfolio(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Portfolio", "", "JSON (*.json)")
        if file_path:
            self.portfolio.save(file_path)
            self.show_message("Portfolio saved as.")
            return True
        return False

    def load_portfolio(self):
        if not self.portfolio.saved:
            reply = QMessageBox.question(self, "Save Changes", "Save current portfolio before loading?")
            if reply == QMessageBox.Yes:
                self.save_portfolio()
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Portfolio", "", "JSON (*.json)")
        if file_path:
            try:
                self.portfolio.load(file_path)
                self.name_edit.setText(self.portfolio.name)
                self.currency_combo.setCurrentText(self.portfolio.currency)
                self.update_table()
                self.show_message("Portfolio loaded.")
            except Exception as e:
                self.show_message(f"Error loading: {e}", error=True)

    def undo(self):
        self.portfolio.undo()
        self.name_edit.setText(self.portfolio.name)
        self.currency_combo.setCurrentText(self.portfolio.currency)
        self.update_table()

    def redo(self):
        self.portfolio.redo()
        self.name_edit.setText(self.portfolio.name)
        self.currency_combo.setCurrentText(self.portfolio.currency)
        self.update_table()

    def update_table(self):
        self.table.setRowCount(0)
        symbol = self.currency_symbols.get(self.portfolio.currency, "")
        for i, holding in enumerate(self.portfolio.holdings):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(holding.name))
            self.table.setItem(row, 1, QTableWidgetItem(holding.ticker))
            self.table.setItem(row, 2, QTableWidgetItem(f"{holding.quantity:.4f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{holding.allocation:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{symbol}{holding.market_price:.4f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{symbol}{holding.total_value:.4f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"{holding.real_allocation:.2f}"))
            self.table.setItem(row, 7, QTableWidgetItem(f"{holding.deviation:.2f}"))
            self.table.setItem(row, 8, QTableWidgetItem(str(i)))  # Original index
        self.table.resizeColumnsToContents()
        self.update_total_value()

    def sort_table(self, column, order):
        self.table.sortItems(column, order)

    def update_total_value(self):
        symbol = self.currency_symbols.get(self.portfolio.currency, "")
        self.total_value_label.setText(f"Total Value: {symbol}{self.portfolio.total_value():.4f}")

    def check_allocations(self):
        total_alloc = self.portfolio.total_allocation()
        if total_alloc > 100:
            self.show_message(f"Warning: Total allocation is {total_alloc:.2f}% > 100%", error=True)
        else:
            self.show_message("")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    style_file = "styles.qss"
    if os.path.exists(style_file):
        with open(style_file, "r") as f:
            stylesheet = f.read()
        app.setStyleSheet(stylesheet)
    window = PortfolioBalancer()
    window.show()
    sys.exit(app.exec())

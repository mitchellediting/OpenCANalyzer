import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QFileDialog, QTreeWidget, 
                             QTreeWidgetItem, QLabel, QSlider, QSplitter, QHeaderView,
                             QComboBox)
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtCore import Qt, QTimer
import pyqtgraph as pg
from can_loader import CANLoader

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("OpenCANalyzer")
        self.resize(1200, 800)

        self.loader = CANLoader()
        self.current_index = 0
        self.is_playing = False
        self.playback_speed = 1.0
        
        # Trace Window State
        self.message_items = {} # {can_id: QTreeWidgetItem}
        self.signal_items = {}  # {(can_id, signal_name): QTreeWidgetItem}
        self.last_data = {}     # {can_id: hex_string}
        self.last_signals = {}  # {(can_id, signal_name): value}
        self.byte_states = {}   # {can_id: [state_byte_0, state_byte_1, ...]} 0=Gray, 1=Red, 2=Yellow
        self.signal_states = {} # {(can_id, signal_name): state} 0=Gray, 1=Red, 2=Yellow

        # Main Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Toolbar / Controls
        controls_layout = QHBoxLayout()
        
        self.btn_load_log = QPushButton("Load Log")
        self.btn_load_log.clicked.connect(self.load_log_dialog)
        controls_layout.addWidget(self.btn_load_log)

        self.btn_load_dbc = QPushButton("Load DBC")
        self.btn_load_dbc.clicked.connect(self.load_dbc_dialog)
        controls_layout.addWidget(self.btn_load_dbc)

        self.btn_gen_mock = QPushButton("Gen Mock Data")
        self.btn_gen_mock.clicked.connect(self.generate_mock)
        controls_layout.addWidget(self.btn_gen_mock)

        controls_layout.addSpacing(20)

        self.btn_step_back = QPushButton("Step Back")
        self.btn_step_back.clicked.connect(self.step_back)
        controls_layout.addWidget(self.btn_step_back)

        self.btn_play = QPushButton("Play")
        self.btn_play.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.btn_play)

        self.btn_step = QPushButton("Step")
        self.btn_step.clicked.connect(self.step_forward)
        controls_layout.addWidget(self.btn_step)

        self.lbl_time = QLabel("Time: 0.000 s")
        controls_layout.addWidget(self.lbl_time)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.sliderPressed.connect(self.slider_pressed)
        self.slider.sliderReleased.connect(self.slider_released)
        self.slider.valueChanged.connect(self.slider_moved)
        controls_layout.addWidget(self.slider)

        layout.addLayout(controls_layout)

        # Splitter for Table and Graph
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # Graph Container
        graph_widget = QWidget()
        graph_layout = QVBoxLayout(graph_widget)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        
        # Signal Selection Dropdown
        self.signal_combo = QComboBox()
        self.signal_combo.addItem("Select Signal to Trace...")
        self.signal_combo.currentTextChanged.connect(self.on_signal_select)
        graph_layout.addWidget(self.signal_combo)

        # Graph Area
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setTitle("Signal Trace")
        graph_layout.addWidget(self.plot_widget)
        
        splitter.addWidget(graph_widget)

        # Trace Tree
        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["Time", "Ch", "ID", "Name", "DLC", "Data / Decoded"])
        self.tree.header().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.tree.itemClicked.connect(self.on_tree_click)
        self.tree.setUniformRowHeights(True)
        # Dark Theme for Tree
        self.tree.setStyleSheet("QTreeWidget { background-color: black; color: #E0E0E0; } QHeaderView::section { background-color: #333; color: white; }")
        splitter.addWidget(self.tree)
        
        # Set initial splitter sizes (Graph smaller, Table larger)
        splitter.setSizes([300, 500])

        # Timer for playback
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_playback)
        self.timer_interval = 50 # ms

    def load_log_dialog(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open Log File", "", "Supported Files (*.csv *.asc *.log *.blf);;CSV Files (*.csv);;Vector ASC (*.asc);;Log Files (*.log);;BLF Files (*.blf);;All Files (*)")
        if fname:
            if self.loader.load_log(fname):
                self.refresh_table()

    def load_dbc_dialog(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open DBC File", "", "DBC Files (*.dbc);;All Files (*)")
        if fname:
            if self.loader.load_dbc(fname):
                self.refresh_table() # Refresh to show decoded names

    def generate_mock(self):
        self.loader.generate_mock_data()
        self.refresh_table()

    def refresh_table(self):
        """
        Resets the trace view and processes frames up to current_index.
        For a fresh log load, current_index is 0.
        """
        self.tree.clear()
        self.message_items = {}
        self.signal_items = {}
        self.last_data = {}
        self.last_signals = {}
        self.byte_states = {}
        self.signal_states = {}
        
        if self.loader.df.empty:
            return

        self.slider.setRange(0, len(self.loader.df) - 1)
        
        # If just loaded, start at 0
        if self.current_index >= len(self.loader.df):
            self.current_index = 0
            
        # For initial display, if index is 0, process just the first frame or nothing?
        # Usually user wants to see something. Let's process 0.
        self.process_frame(self.current_index)
        self.update_ui_common()

    def step_forward(self):
        if self.loader.df.empty: return
        if self.current_index < len(self.loader.df) - 1:
            self.current_index += 1
            self.process_frame(self.current_index)
            self.update_ui_common()

    def step_back(self):
        if self.loader.df.empty: return
        if self.current_index > 0:
            # decrementing slider triggers slider_moved -> rebuilds view
            self.slider.setValue(self.current_index - 1)

    def process_frame(self, index):
        """
        Updates the Tree Widget with data from the frame at 'index'.
        Highlights changes compared to previous state.
        """
        row = self.loader.df.iloc[index]
        can_id = row['ID']
        timestamp = row['Timestamp']
        dlc = row['DLC']
        data_str = str(row['Data']) # Hex string
        
        # Pad data if needed
        if len(data_str) % 2 != 0:
            data_str = "0" + data_str
            
        # Split into byte strings
        current_bytes = [data_str[i:i+2] for i in range(0, len(data_str), 2)]
        
        # Initialize States if New
        if can_id not in self.byte_states:
             # Default state 0 (Gray)
             self.byte_states[can_id] = [0] * len(current_bytes)
        
        # Resize state if DLC changed (rare but possible)
        if len(self.byte_states[can_id]) != len(current_bytes):
            self.byte_states[can_id] = [0] * len(current_bytes)

        # 1. Update or Create Message Row
        if can_id not in self.message_items:
            # Create new
            id_str = f"0x{can_id:X}"
            name = "Unknown"
            msg_def = None
            if self.loader.db:
                try:
                    msg_def = self.loader.db.get_message_by_frame_id(can_id)
                    name = msg_def.name
                except:
                    pass
            
            # Initial create
            item = QTreeWidgetItem([f"{timestamp:.4f}", str(row.get('Channel', 1)), id_str, name, str(dlc), ""])
            
            # Create Label for HTML Data
            lbl = QLabel()
            lbl.setStyleSheet("background-color: transparent;")
            
            self.tree.addTopLevelItem(item)
            self.tree.setItemWidget(item, 5, lbl)
            self.message_items[can_id] = item
            
            # Create child items for signals if DBC exists
            if msg_def:
                for sig in msg_def.signals:
                    sig_item = QTreeWidgetItem(["", "", "", sig.name, "", ""])
                    item.addChild(sig_item)
                    self.signal_items[(can_id, sig.name)] = sig_item
                    
                    # Also use Label for signal value
                    s_lbl = QLabel()
                    s_lbl.setStyleSheet("background-color: transparent;")
                    self.tree.setItemWidget(sig_item, 5, s_lbl)

        item = self.message_items[can_id]
        item.setText(0, f"{timestamp:.4f}")
        item.setText(4, str(dlc))
        
        # Determine Byte Colors
        # Logic: 
        # Diff vs Prev:
        #   Changed -> Red (State 1)
        #   Unchanged -> 
        #       If State was Red (1) -> Yellow (State 2)
        #       If State was Yellow (2) -> Yellow (State 2)
        #       If State was Gray (0) -> Gray (0)
        
        prev_data_str = self.last_data.get(can_id, "")
        if len(prev_data_str) % 2 != 0: prev_data_str = "0" + prev_data_str
        prev_bytes = [prev_data_str[i:i+2] for i in range(0, len(prev_data_str), 2)]
        
        # If prev is empty or length mismatch, treat all as new (Gray or Red? Let's say Gray for initial, Red if change detected from nothing? No, keep Gray for init)
        # But if we are stepping, and this is the first time we see it, it is "new". 
        # Standard: Gray.
        
        html_parts = []
        states = self.byte_states[can_id]
        
        for i, byte_val in enumerate(current_bytes):
            color = "#E0E0E0" # Light Gray (Default)
            
            # Check Change
            changed = False
            if i < len(prev_bytes):
                if byte_val != prev_bytes[i]:
                    changed = True
            
            if changed:
                states[i] = 1 # Red
                color = "#FF3333" # Red
            else:
                if states[i] == 1: # Was Red
                    states[i] = 2 # Become Yellow
                    color = "#FFFF33" # Yellow
                elif states[i] == 2: # Was Yellow
                    color = "#FFFF33" # Stay Yellow
                else:
                    color = "#E0E0E0" # Stay Gray

            html_parts.append(f'<span style="color:{color}; font-family: monospace;">{byte_val}</span>')

        # Update Message Label
        lbl = self.tree.itemWidget(item, 5)
        if lbl:
            lbl.setText(" ".join(html_parts))
        
        self.last_data[can_id] = data_str

        # 2. Decode and Update Signals
        if self.loader.db:
            try:
                data_bytes = bytes.fromhex(data_str)
                msg_def = self.loader.db.get_message_by_frame_id(can_id)
                decoded = msg_def.decode(data_bytes) # {name: value}
                
                for sig_name, val in decoded.items():
                    key = (can_id, sig_name)
                    if key in self.signal_items:
                        s_item = self.signal_items[key]
                        s_lbl = self.tree.itemWidget(s_item, 5)
                        
                        # Get unit
                        unit = ""
                        try:
                            s_def = msg_def.get_signal_by_name(sig_name)
                            if s_def.unit: unit = " " + s_def.unit
                        except: pass
                        
                        new_text_val = f"{val}{unit}"
                        old_val = self.last_signals.get(key)
                        
                        # Color Logic for Signal
                        # 0=Gray, 1=Red, 2=Yellow
                        s_state = self.signal_states.get(key, 0)
                        s_color = "#E0E0E0"
                        
                        if old_val is not None and val != old_val:
                            s_state = 1 # Red
                            s_color = "#FF3333"
                        else:
                            if s_state == 1:
                                s_state = 2 # Yellow
                                s_color = "#FFFF33"
                            elif s_state == 2:
                                s_color = "#FFFF33"
                            else:
                                s_color = "#E0E0E0"
                        
                        self.signal_states[key] = s_state
                        self.last_signals[key] = val
                        
                        if s_lbl:
                            s_lbl.setText(f'<span style="color:{s_color}; font-family: monospace;">{new_text_val}</span>')

            except Exception:
                pass
    
    def update_ui_common(self):
        """Updates common UI elements like slider, label, plot line."""
        # Update Slider
        self.slider.blockSignals(True)
        self.slider.setValue(self.current_index)
        self.slider.blockSignals(False)

        # Update Time Label
        timestamp = self.loader.df.iloc[self.current_index]['Timestamp']
        self.lbl_time.setText(f"Time: {timestamp:.4f} s")
        
        # Update Plot Line
        for item in self.plot_widget.items():
            if isinstance(item, pg.InfiniteLine):
                self.plot_widget.removeItem(item)
        self.plot_widget.addLine(x=timestamp, pen='r')

    def toggle_playback(self):
        if self.is_playing:
            self.timer.stop()
            self.is_playing = False
            self.btn_play.setText("Play")
        else:
            self.timer.start(self.timer_interval)
            self.is_playing = True
            self.btn_play.setText("Pause")

    def update_playback(self):
        if self.loader.df.empty:
            return
        
        if self.current_index < len(self.loader.df) - 1:
            self.current_index += 1
            self.process_frame(self.current_index)
            self.update_ui_common()
        else:
            self.toggle_playback() # Stop at end

    def slider_pressed(self):
        self.was_playing = self.is_playing
        if self.is_playing:
            self.toggle_playback()

    def slider_released(self):
        if hasattr(self, 'was_playing') and self.was_playing:
            self.toggle_playback()

    def slider_moved(self, val):
        # Optimization: If val is just +1, use step.
        if val == self.current_index + 1:
            self.step_forward()
            return
            
        self.current_index = val
        
        # When jumping arbitrarily, we strictly should re-process everything from 0 to val
        # to get the correct "Last Known State".
        # For performance on large logs, we might just update the ONE frame at 'val' 
        # but that leaves other messages stale or missing.
        # Let's try to be correct first.
        
        # Disable updates during bulk process
        self.tree.setUpdatesEnabled(False)
        self.tree.clear()
        self.message_items = {}
        self.signal_items = {}
        self.last_data = {}
        self.last_signals = {}
        self.byte_states = {}
        self.signal_states = {}
        
        # We need to find the latest occurrence of EACH unique ID up to index 'val'
        # Scanning 0..val is O(val).
        # Optimization: Pandas allows us to get the latest indices per group efficiently!
        
        # Filter df up to current index
        subset = self.loader.df.iloc[:val+1]
        
        # Group by ID and take the last occurrence
        # This gives us the set of messages that should be visible and their last state.
        latest_frames = subset.groupby('ID').tail(1)
        
        # Sort by timestamp to maintain relative order if desired, or just ID.
        # Trace windows usually sort by Timestamp of last event.
        latest_frames = latest_frames.sort_values('Timestamp')
        
        for idx, row in latest_frames.iterrows():
            # We treat this as a "fresh" render for these rows (no highlight? or highlight vs nothing?)
            # Let's just render them. 
            # We call process_frame but that method assumes it's updating global state and highlighting.
            # We want to populate the tree without "changed" red highlights initially, 
            # OR we just want to set the state.
            
            # To re-use process_frame, we just loop. 
            # But process_frame does a lot of UI lookups.
            # Faster to loop locally.
            
            # Actually, to properly populate self.last_data and items, we can just call process_frame 
            # on these indices.
            # But we must ensure self.message_items is populated.
            self.process_frame(self.loader.df.index.get_loc(idx))
            
            # Reset highlights after seek?
            # Usually when you seek, everything is "static". 
            # Let's clear highlights (set everything to Gray 0 or Yellow 2 if we want to show it's 'state')
            # Standard: Reset to Gray if we consider this the "starting point".
            # If we want to show diff from PREVIOUS known state, we don't have that.
            # So reset to Gray.
            cid = row['ID']
            if cid in self.byte_states:
                self.byte_states[cid] = [0] * len(self.byte_states[cid])
                # We need to re-render to apply Gray
                # This is getting expensive. 
                # Ideally process_frame handles it if we reset byte_states BEFORE calling it? 
                # No, process_frame logic is "diff vs last_data". 
                # Here last_data is empty initially.
                # So process_frame sees "New" -> Default Gray.
                # So we are good! Because we cleared self.last_data and self.byte_states.
                pass

        self.tree.setUpdatesEnabled(True)
        self.update_ui_common()

    def on_tree_click(self, item, col):
        # Determine ID from the item
        # Parent item (Message) or Child item (Signal)
        
        can_id_str = ""
        signal_name = None
        
        if item.parent():
            # Signal row
            signal_name = item.text(3)
            parent = item.parent()
            can_id_str = parent.text(2)
        else:
            # Message row
            can_id_str = item.text(2)
            
        try:
            can_id = int(can_id_str, 16)
        except:
            return

        # Populate Combobox with signals for this ID
        signals = self.loader.get_signals_for_id(can_id)
        
        self.signal_combo.blockSignals(True)
        self.signal_combo.clear()
        
        if signals:
            self.signal_combo.addItems(signals)
            if signal_name and signal_name in signals:
                self.signal_combo.setCurrentText(signal_name)
        else:
            self.signal_combo.addItem(f"Raw ID: 0x{can_id:X}")
            
        self.signal_combo.blockSignals(False)
        
        # Update Plot
        if signal_name:
            self.update_plot(can_id, signal_name)
        elif signals:
             self.update_plot(can_id, signals[0])
        else:
             self.update_plot(can_id, None)

    def on_signal_select(self, text):
        if not text: return
        if self.current_index < 0 or self.current_index >= len(self.loader.df): return
        
        can_id = self.loader.df.iloc[self.current_index]['ID']
        self.update_plot(can_id, text)

    def update_plot(self, can_id, signal_name):
        self.plot_widget.clear()
        
        if signal_name and "Raw ID" not in signal_name:
            times, values = self.loader.get_signal_trace(can_id, signal_name)
            self.plot_widget.plot(times, values, pen='b', name=signal_name)
            self.plot_widget.setTitle(f"Signal: {signal_name}")
        else:
            # Fallback: Plot existence of ID (toggle) or just dots
            # Or similar to before, just plot ID value over time (constant line usually)
            # Better: Plot DLC or just tick marks
            times = self.loader.df[self.loader.df['ID'] == can_id]['Timestamp']
            y = [1] * len(times) # Just presence
            self.plot_widget.plot(times, y, pen=None, symbol='o', symbolSize=5)
            self.plot_widget.setTitle(f"Message Occurrences: 0x{can_id:X}")

        # Add current time line
        if not self.loader.df.empty:
            current_time = self.loader.df.iloc[self.current_index]['Timestamp']
            self.plot_widget.addLine(x=current_time, pen='r')



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

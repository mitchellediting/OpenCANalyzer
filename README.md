# 🚗 OpenCANalyzer

**A modern, lightweight CAN bus analysis tool built with Python.**

OpenCANalyzer helps you visualize, decode, and playback CAN bus data with ease. Whether you are debugging a vehicle network or analyzing log files, this tool provides a clean and intuitive interface.

---

## ✨ Features

- **📊 Load & Analyze**: Import CSV formatted CAN logs effortlessly.
- **📂 DBC Support**: Decode raw CAN frames into human-readable signals using `.dbc` files.
- **⏯️ Playback Control**: Play, pause, and scrub through your data with a real-time slider.
- **🔍 Trace View**: Inspect messages frame-by-frame for precise debugging.
- **🧪 Mock Data**: Generate test data instantly to explore features without a log file.
- **📈 Visualization**: Plot Message IDs and signals over time.

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/OpenCANalyzer.git
   cd OpenCANalyzer
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 🎮 Usage

Launch the application with a single command:

```bash
python main.py
```

### How to use:
1. **Quick Test**: Click **"Gen Mock Data"** to see the tool in action immediately.
2. **Analyze Real Data**: Click **"Load Log"** to open your CSV log file.
3. **Decode**: Click **"Load DBC"** to apply decoding rules and see physical values.
4. **Navigate**: Use the **Play/Pause** buttons or drag the **Time Slider** to move through the log.

## 📂 Project Structure

- `main.py`: Entry point for the application.
- `ui_main.py`: Handles the User Interface logic.
- `can_loader.py`: Utilities for loading and processing CAN data.
- `requirements.txt`: Python dependencies.

## 🤝 Contributing

Contributions are welcome! Feel free to submit a Pull Request or open an Issue if you have ideas for improvements.

---
*Built with ❤️ for the Open Source Community*
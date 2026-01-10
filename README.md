# OpenCANalyzer

A lightweight CAN bus analysis tool written in Python.

## Features
- **Load Log Files:** Supports CSV formatted CAN logs.
- **DBC Support:** Decode raw CAN data into physical values using `.dbc` files.
- **Trace View:** Step through messages frame-by-frame.
- **Playback:** Play, pause, and scrub through the log with a time slider.
- **Mock Data Generation:** Quickly test the UI without needing real log files.
- **Visualization:** Basic plotting of Message IDs over time (extensible to signals).

## Installation

1. Install Python 3.8+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the application:
```bash
python main.py
```

1. Click **"Gen Mock Data"** to populate the view with test data.
2. Or, **"Load Log"** to open your own CSV file.
3. **"Load DBC"** to apply decoding rules.
4. Use the **Play** button or **Slider** to navigate the log.

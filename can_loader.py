import pandas as pd
import cantools
import numpy as np
import random
import can
import os

class CANLoader:
    def __init__(self):
        self.db = None
        self.df = pd.DataFrame(columns=['Timestamp', 'ID', 'Data', 'Channel', 'DLC'])
        self.decoded_cache = {} # Cache for decoded messages to speed up playback/display

    def load_dbc(self, filepath):
        """Loads a DBC file using cantools."""
        try:
            self.db = cantools.database.load_file(filepath)
            print(f"Loaded DBC: {filepath}")
            return True
        except Exception as e:
            print(f"Error loading DBC: {e}")
            return False

    def load_log(self, filepath):
        """
        Loads a log file. 
        Supports CSV, ASC, and LOG formats.
        """
        ext = os.path.splitext(filepath)[1].lower()
        
        try:
            # Check for BusMaster specifically
            if ext == '.log':
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    header = f.readline()
                    if header.startswith('***BUSMASTER'):
                        return self._load_busmaster(filepath)

            if ext == '.csv':
                return self._load_csv(filepath)
            elif ext in ['.asc', '.log', '.blf']:
                return self._load_can_log(filepath)
            else:
                print(f"Unsupported file extension: {ext}")
                return False
        except Exception as e:
            print(f"Error loading Log: {e}")
            return False

    def _load_busmaster(self, filepath):
        """Custom parser for BusMaster .log files."""
        data_list = []
        base_time_seconds = None
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('***'):
                    continue
                
                parts = line.split()
                if len(parts) < 6:
                    continue
                
                # Format: Time Tx/Rx Channel ID Type DLC Data...
                # Ex: 17:48:32:9099 Rx 1 0x004 s 8 04 08 ...
                
                try:
                    time_str = parts[0]
                    # Parse Time HH:MM:SS:mmmm
                    # Split by ':'
                    t_parts = time_str.split(':')
                    if len(t_parts) == 4:
                        h = int(t_parts[0])
                        m = int(t_parts[1])
                        s = int(t_parts[2])
                        ms = int(t_parts[3]) # This might be 0.1ms units (0-9999)
                        
                        # Convert to seconds
                        # If ms has 4 digits, it is 0.1ms resolution.
                        # If 3 digits, 1ms.
                        # Usually Busmaster is 0.1ms (100us). 
                        # 9099 -> 909.9ms
                        
                        seconds = h * 3600 + m * 60 + s + (ms / 10000.0)
                        
                        if base_time_seconds is None:
                            base_time_seconds = seconds
                        
                        rel_time = seconds - base_time_seconds
                        # Handle day rollover? (If log crosses midnight)
                        if rel_time < 0:
                            rel_time += 24 * 3600

                        can_id_str = parts[3]
                        can_id = int(can_id_str, 16)
                        
                        dlc = int(parts[5])
                        
                        data_hex_parts = parts[6:6+dlc]
                        data_hex = "".join(data_hex_parts)
                        
                        data_list.append({
                            'Timestamp': rel_time,
                            'ID': can_id,
                            'DLC': dlc,
                            'Data': data_hex,
                            'Channel': int(parts[2])
                        })
                except Exception as e:
                    # Skip malformed lines
                    continue

        if not data_list:
            print("No CAN frames found in BusMaster log.")
            return False

        self.df = pd.DataFrame(data_list)
        self.decoded_cache = {}
        print(f"Loaded BusMaster Log: {len(self.df)} frames")
        return True

    def _load_csv(self, filepath):
        # Try parsing as CSV first
        self.df = pd.read_csv(filepath)
        
        # Normalize column names
        self.df.columns = [c.strip().lower() for c in self.df.columns]
        
        # Ensure required columns exist, map common variations
        col_map = {
            'time': 'Timestamp', 'timestamp': 'Timestamp',
            'id': 'ID', 'can_id': 'ID', 'identifier': 'ID',
            'dlc': 'DLC', 'len': 'DLC', 'length': 'DLC',
            'data': 'Data', 'payload': 'Data'
        }
        
        self.df = self.df.rename(columns=col_map)
        
        # Clean up ID (handle 0x prefix)
        if self.df['ID'].dtype == object:
            self.df['ID'] = self.df['ID'].astype(str).apply(lambda x: int(x, 16) if 'x' in x else int(x))
        
        # Sort by timestamp
        self.df = self.df.sort_values('Timestamp').reset_index(drop=True)
        
        # Clear cache on new log load
        self.decoded_cache = {}
        
        print(f"Loaded Log: {len(self.df)} frames")
        return True

    def _load_can_log(self, filepath):
        """Uses python-can to read standard log formats (ASC, BLF, etc)."""
        data_list = []
        
        # can.LogReader automatically detects format for many types
        # For .asc, it works well. For .log, it depends on the content.
        with can.LogReader(filepath) as reader:
            for msg in reader:
                # Convert data bytes to hex string
                data_hex = msg.data.hex()
                
                data_list.append({
                    'Timestamp': msg.timestamp,
                    'ID': msg.arbitration_id,
                    'DLC': msg.dlc,
                    'Data': data_hex,
                    'Channel': msg.channel
                })
        
        if not data_list:
            print("No CAN frames found in log.")
            return False
            
        self.df = pd.DataFrame(data_list)
        
        # Adjust timestamps to start at 0 if desired? 
        # Usually ASC has absolute or relative timestamps. 
        # For now, we keep as is, but maybe useful to normalize to start from 0 if huge.
        if not self.df.empty:
             first_ts = self.df['Timestamp'].iloc[0]
             # Optional: normalize to 0
             self.df['Timestamp'] = self.df['Timestamp'] - first_ts

        self.decoded_cache = {}
        print(f"Loaded Log ({filepath}): {len(self.df)} frames")
        return True

    def decode_message(self, can_id, data_bytes):
        """Decodes a single message based on ID and raw bytes."""
        if not self.db:
            return "No DBC Loaded"
        
        try:
            message = self.db.get_message_by_frame_id(can_id)
            decoded = message.decode(data_bytes)
            return decoded # Returns a dictionary of signal_name: value
        except KeyError:
            return "Unknown ID"
        except Exception:
            return "Decode Error"

    def generate_mock_data(self, count=1000):
        """Generates mock CAN traffic for testing."""
        timestamps = np.cumsum(np.random.uniform(0.001, 0.05, count))
        ids = [0x100, 0x101, 0x200]
        data_list = []
        
        for t in timestamps:
            cid = random.choice(ids)
            # Generate random 8 bytes
            data_int = random.getrandbits(64)
            data_hex = f"{data_int:016x}"
            data_list.append({
                'Timestamp': t,
                'ID': cid,
                'DLC': 8,
                'Data': data_hex,
                'Channel': 1
            })
            
        self.df = pd.DataFrame(data_list)
        print("Generated mock data.")

    def get_frame_by_index(self, index):
        if 0 <= index < len(self.df):
            return self.df.iloc[index]
        return None

    def get_decoded_string(self, index):
        """Returns a string representation of decoded signals for the UI."""
        if index in self.decoded_cache:
            return self.decoded_cache[index]

        row = self.df.iloc[index]
        can_id = row['ID']
        data_str = str(row['Data']).strip()
        
        # Convert hex string to bytes
        try:
            # Pad if odd length or short
            if len(data_str) % 2 != 0:
                data_str = "0" + data_str
            data_bytes = bytes.fromhex(data_str)
        except:
            return "Invalid Data"

        decoded = self.decode_message(can_id, data_bytes)
        
        if isinstance(decoded, dict):
            # Format as "Sig1: 12.5, Sig2: 100"
            res = ", ".join([f"{k}: {v}" for k, v in decoded.items()])
        else:
            res = str(decoded)
            
        self.decoded_cache[index] = res
        return res

    def get_signals_for_id(self, can_id):
        """Returns a list of signal names for a given CAN ID."""
        if not self.db:
            return []
        try:
            msg = self.db.get_message_by_frame_id(can_id)
            return [s.name for s in msg.signals]
        except:
            return []

    def get_signal_trace(self, can_id, signal_name):
        """
        Extracts timestamps and values for a specific signal.
        This iterates over the dataframe, which can be slow for large logs.
        """
        if self.df.empty:
            return [], []

        # Filter DF for this ID
        subset = self.df[self.df['ID'] == can_id]
        
        timestamps = []
        values = []
        
        for _, row in subset.iterrows():
            try:
                data_bytes = bytes.fromhex(row['Data'])
                decoded = self.decode_message(can_id, data_bytes)
                if isinstance(decoded, dict) and signal_name in decoded:
                    timestamps.append(row['Timestamp'])
                    values.append(decoded[signal_name])
            except:
                continue
                
        return timestamps, values

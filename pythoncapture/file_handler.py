import os
from datetime import datetime

class FileHandler:
    def __init__(self, output_dir=None):
        self.output_dir = output_dir
        self.counter = 0
        if output_dir:
            self.top_panel_dir = os.path.join(output_dir, 'Top_Panel')
            self.bottom_panel_dir = os.path.join(output_dir, 'Bottom_Panel')
            self._create_directories()
            top_max = self._get_highest_counter(self.top_panel_dir)
            bottom_max = self._get_highest_counter(self.bottom_panel_dir)
            self.counter = max(top_max, bottom_max)

    def set_output_directory(self, output_dir):
        self.output_dir = output_dir
        self.top_panel_dir = os.path.join(output_dir, 'Top_Panel')
        self.bottom_panel_dir = os.path.join(output_dir, 'Bottom_Panel')
        self._create_directories()
        top_max = self._get_highest_counter(self.top_panel_dir)
        bottom_max = self._get_highest_counter(self.bottom_panel_dir)
        self.counter = max(top_max, bottom_max)

    def _create_directories(self):
        os.makedirs(self.top_panel_dir, exist_ok=True)
        os.makedirs(self.bottom_panel_dir, exist_ok=True)

    def _get_highest_counter(self, directory):
        if not os.path.exists(directory):
            return 0
        files = os.listdir(directory)
        counters = []
        for file in files:
            if file.endswith('.jpg'):
                parts = file.split('_')
                if len(parts) >= 4:
                    try:
                        counter = int(parts[3].split('.')[0])
                        counters.append(counter)
                    except ValueError:
                        pass
        return max(counters) + 1 if counters else 0

    def generate_filename(self, category):
        now = datetime.now()
        date_str = now.strftime('%Y%m%d')
        time_str = now.strftime('%H%M%S')
        counter = self.counter
        self.counter += 1
        return f"{category}_{date_str}_{time_str}_{counter:03d}.jpg"

    def get_both_save_paths(self):
        if not self.output_dir:
            raise RuntimeError("Output directory not set")
        now = datetime.now()
        date_str = now.strftime('%Y%m%d')
        time_str = now.strftime('%H%M%S')
        counter = self.counter
        self.counter += 1
        top_filename = f"Top_Panel_{date_str}_{time_str}_{counter:03d}.jpg"
        bottom_filename = f"Bottom_Panel_{date_str}_{time_str}_{counter:03d}.jpg"
        return os.path.join(self.top_panel_dir, top_filename), os.path.join(self.bottom_panel_dir, bottom_filename)

    def get_top_save_path(self):
        """Get save path for top camera only"""
        if not self.output_dir:
            raise RuntimeError("Output directory not set")
        now = datetime.now()
        date_str = now.strftime('%Y%m%d')
        time_str = now.strftime('%H%M%S')
        counter = self.counter
        self.counter += 1
        top_filename = f"Top_Panel_{date_str}_{time_str}_{counter:03d}.jpg"
        return os.path.join(self.top_panel_dir, top_filename)

    def get_bottom_save_path(self):
        """Get save path for bottom camera only"""
        if not self.output_dir:
            raise RuntimeError("Output directory not set")
        now = datetime.now()
        date_str = now.strftime('%Y%m%d')
        time_str = now.strftime('%H%M%S')
        counter = self.counter
        self.counter += 1
        bottom_filename = f"Bottom_Panel_{date_str}_{time_str}_{counter:03d}.jpg"
        return os.path.join(self.bottom_panel_dir, bottom_filename)

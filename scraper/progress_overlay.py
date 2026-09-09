import tkinter as tk
from tkinter import ttk
import threading
import time

class ProgressOverlay:
    def __init__(self):
        self.root = None
        self.status_var = None
        self.metrics_var = None
        self.progress_canvas = None
        self.progress_rect = None
        self.thread = None
        self.running = False
        self.percent = 0
        self.status_text = "Initializing pipeline..."
        self.metrics_text = "Jobs Scraped: 0 | Best Fit: 0"
        self._lock = threading.Lock()

    def _build_gui(self):
        self.root = tk.Tk()
        self.root.title("LinkedIn Scraper Progress")
        
        # Borderless, always-on-top floating card
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Dimensions & positioning (bottom-right corner)
        win_w, win_h = 380, 125
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - win_w - 24
        y = screen_h - win_h - 60
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        # Dark theme colors
        bg_color = "#181825"
        card_color = "#1e1e2e"
        accent_color = "#89b4fa"
        text_primary = "#cdd6f4"
        text_sub = "#a6adc8"
        border_color = "#313244"
        
        self.root.configure(bg=border_color)
        
        container = tk.Frame(self.root, bg=card_color, bd=0)
        container.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Header layout
        header_frame = tk.Frame(container, bg=card_color)
        header_frame.pack(fill="x", padx=14, pady=(12, 4))
        
        title_label = tk.Label(
            header_frame,
            text="LinkedIn Scraper & NetWeave AI",
            font=("Segoe UI", 10, "bold"),
            fg=accent_color,
            bg=card_color
        )
        title_label.pack(side="left")
        
        # Status Label
        self.status_var = tk.StringVar(value=self.status_text)
        status_label = tk.Label(
            container,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            fg=text_primary,
            bg=card_color,
            anchor="w"
        )
        status_label.pack(fill="x", padx=14, pady=(2, 6))
        
        # Custom Canvas Progress Bar
        bar_frame = tk.Frame(container, bg=card_color)
        bar_frame.pack(fill="x", padx=14, pady=2)
        
        self.progress_canvas = tk.Canvas(
            bar_frame,
            height=8,
            bg="#313244",
            highlightthickness=0,
            bd=0
        )
        self.progress_canvas.pack(fill="x", expand=True)
        self.progress_rect = self.progress_canvas.create_rectangle(0, 0, 0, 8, fill=accent_color, width=0)
        
        # Metrics / Counter Label
        self.metrics_var = tk.StringVar(value=self.metrics_text)
        metrics_label = tk.Label(
            container,
            textvariable=self.metrics_var,
            font=("Segoe UI", 8),
            fg=text_sub,
            bg=card_color,
            anchor="w"
        )
        metrics_label.pack(fill="x", padx=14, pady=(6, 10))
        
        self._update_loop()
        self.root.mainloop()

    def _update_loop(self):
        if not self.running or not self.root:
            return
        
        with self._lock:
            percent = self.percent
            status = self.status_text
            metrics = self.metrics_text
            
        if self.status_var:
            self.status_var.set(status)
        if self.metrics_var:
            self.metrics_var.set(metrics)
            
        if self.progress_canvas:
            w = self.progress_canvas.winfo_width()
            if w > 1:
                fill_w = max(0, min(w, int(w * (percent / 100.0))))
                self.progress_canvas.coords(self.progress_rect, 0, 0, fill_w, 8)
                
        self.root.after(100, self._update_loop)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._build_gui, daemon=True)
        self.thread.start()
        # Wait for GUI to initialize
        time.sleep(0.5)

    def update(self, percent: float, status: str, metrics: str = None):
        with self._lock:
            self.percent = max(0.0, min(100.0, percent))
            self.status_text = status
            if metrics:
                self.metrics_text = metrics

    def close(self):
        self.running = False
        if self.root:
            try:
                def _safe_destroy():
                    try:
                        self.status_var = None
                        self.metrics_var = None
                        self.root.quit()
                        self.root.destroy()
                    except Exception:
                        pass
                self.root.after(0, _safe_destroy)
            except Exception:
                pass

# Global Singleton Overlay Instance
_overlay_instance = ProgressOverlay()

def start_overlay():
    _overlay_instance.start()

def update_overlay(percent: float, status: str, metrics: str = None):
    _overlay_instance.update(percent, status, metrics)

def close_overlay():
    _overlay_instance.close()

if __name__ == "__main__":
    print("Testing Progress Overlay GUI...")
    start_overlay()
    
    steps = [
        (10, "Navigating to LinkedIn search URL...", "Scraped: 0 | Best Fit: 0"),
        (30, "Scraping Data Scientist (Page 1/2)...", "Scraped: 7 | Best Fit: 0"),
        (50, "Scraping Machine Learning Engineer (Page 2/2)...", "Scraped: 14 | Best Fit: 0"),
        (75, "Evaluating Stage 2 Gemini LLM Batch 1/2...", "Scraped: 14 | Evaluated: 7"),
        (90, "Ingesting NetWeave company database...", "Best Fit: 4 | Excluded: 10"),
        (100, "Pipeline execution complete! Opening report...", "Opening Chrome Dashboard...")
    ]
    
    for pct, msg, met in steps:
        time.sleep(1.2)
        update_overlay(pct, msg, met)
        
    time.sleep(1.0)
    close_overlay()
    print("Overlay test finished.")

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd

# --- CONFIGURATION ---
PARTS_FILE = "parts.txt"
HISTORY_FILE = "inventory_history.json"

class InventoryMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Everest Inventory Monitor")
        self.root.geometry("700x450")
        
        self.monitored_parts = self.load_monitored_parts()
        self.history = self.load_history()
        
        self.setup_ui()
        
    def load_monitored_parts(self):
        """Loads the list of target part numbers from parts.txt"""
        if not os.path.exists(PARTS_FILE):
            with open(PARTS_FILE, "w") as f:
                f.write("# Enter part numbers line by line\n")
            return []
        
        with open(PARTS_FILE, "r") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]

    def load_history(self):
        """Loads previous inventory counts to detect drops"""
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_history(self, current_inventory):
        """Saves current counts for the next run"""
        with open(HISTORY_FILE, "w") as f:
            json.dump(current_inventory, f, indent=4)

    def setup_ui(self):
        """Builds the Tkinter interface"""
        # Top Frame for controls
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="Everest Export File:").pack(side=tk.LEFT, padx=5)
        self.file_label = ttk.Label(top_frame, text="No file selected", font=("Arial", 9, "italic"), foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        import_btn = ttk.Button(top_frame, text="Browse & Scan", command=self.process_spreadsheet)
        import_btn.pack(side=tk.RIGHT, padx=5)

        # Treeview (Table) for displaying parts
        columns = ("part_num", "prev_qty", "curr_qty", "status")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings")
        
        self.tree.heading("part_num", text="Part Number")
        self.tree.heading("prev_qty", text="Previous Qty")
        self.tree.heading("curr_qty", text="Current Qty")
        self.tree.heading("status", text="Status")
        
        self.tree.column("part_num", width=150)
        self.tree.column("prev_qty", width=100, anchor=tk.CENTER)
        self.tree.column("curr_qty", width=100, anchor=tk.CENTER)
        self.tree.column("status", width=250)
        
        # Color coding tags for alerts
        self.tree.tag_configure("alert_zero", background="#ffcccc", foreground="#990000") # Soft red
        self.tree.tag_configure("alert_drop", background="#fff2cc", foreground="#996600") # Soft yellow
        self.tree.tag_configure("normal", background="#ffffff")
        
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def process_spreadsheet(self):
        """Opens file dialog, parses spreadsheet, and checks inventory rules with strict data cleaning"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Excel/CSV Files", "*.xlsx *.xls *.csv")]
        )
        
        if not file_path:
            return
            
        self.file_label.config(text=os.path.basename(file_path), foreground="black")
        
        try:
            # 1. Read spreadsheet - keep EVERYTHING as text initially to preserve leading zeros
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, dtype=str)
            else:
                df = pd.read_excel(file_path, dtype=str)
            
            # Clean column names (forces lowercase and removes accidental spaces)
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            # Mapping columns to match your exact Everest Export
            part_col = 'code'
            qty_col = 'available stock'
            
            if part_col not in df.columns or qty_col not in df.columns:
                missing = [c for c in [part_col, qty_col] if c not in df.columns]
                raise ValueError(f"Could not find required column(s): {missing}")
            
            # Clean the spreadsheet part codes to ignore hidden spaces or case issues
            df[part_col] = df[part_col].astype(str).str.strip().str.lower()
            
            # Clear old rows in UI
            for row in self.tree.get_children():
                self.tree.delete(row)
                
            new_history = {}
            alerts_triggered = []
            zeros_triggered = []
            
            # 2. Scan for our parts
            for original_part in self.monitored_parts:
                # Clean the target part number from parts.txt the exact same way
                cleaned_part = original_part.strip().lower()
                
                # Match against the cleaned spreadsheet column
                match = df[df[part_col] == cleaned_part]
                
                if not match.empty:
                    # Safely extract and convert quantity
                    raw_val = match.iloc[0][qty_col]
                    safe_val = pd.to_numeric(raw_val, errors='coerce')
                    current_qty = int(0 if pd.isna(safe_val) else safe_val)
                else:
                    current_qty = 0
                
                previous_qty = self.history.get(original_part, None)
                new_history[original_part] = current_qty
                
                # 3. Determine status and pick visual tags
                if match.empty:
                    status = "❌ Not Found in Spreadsheet"
                    tag = "alert_zero"  
                elif current_qty == 0:
                    status = "⚠️ OUT OF STOCK (0)"
                    tag = "alert_zero"
                    zeros_triggered.append(original_part)
                elif previous_qty is not None and current_qty < previous_qty:
                    dropped_by = previous_qty - current_qty
                    status = f"📉 Dropped by {dropped_by} (Was {previous_qty})"
                    tag = "alert_drop"
                    alerts_triggered.append(f"{original_part}: {previous_qty} -> {current_qty}")
                elif previous_qty is not None and current_qty > previous_qty:
                    status = f"📈 Stock Increased (Was {previous_qty})"
                    tag = "normal"
                else:
                    status = "No Change"
                    tag = "normal"
                
                prev_display = previous_qty if previous_qty is not None else "N/A"
                self.tree.insert("", tk.END, values=(original_part, prev_display, current_qty, status), tags=(tag,))
            
            # 4. Save history for next run
            self.save_history(new_history)
            self.history = new_history 
            
            # 5. Show popup alerts if triggered
            if zeros_triggered:
                messagebox.showerror("CRITICAL ALERT", f"The following parts hit ZERO stock:\n\n" + "\n".join(zeros_triggered))
            if alerts_triggered:
                messagebox.showwarning("Inventory Drop Detected", f"The following parts have sold/dropped:\n\n" + "\n".join(alerts_triggered))
                
            if not zeros_triggered and not alerts_triggered:
                messagebox.showinfo("Scan Complete", "All parts scanned. No drops or stockouts detected.")
                
        except Exception as e:
            messagebox.showerror("Error Reading File", f"An error occurred while reading the file:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = InventoryMonitorApp(root)
    root.mainloop()

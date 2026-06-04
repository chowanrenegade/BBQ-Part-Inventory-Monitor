## Everest Inventory Monitor — README

Overview
- Simple Tkinter app to scan an Everest export spreadsheet (Excel/CSV) for a list of part numbers and flag stock drops or zeros.
- Reads part numbers from parts.txt and stores previous-run counts in inventory_history.json.

Quick start
1. Save the provided Python script (e.g., inventory_monitor.py) in a folder.
2. Create a parts.txt file in the same folder. Put one part number per line; lines starting with # are ignored. Example:
   PART12345
   PART67890
3. Install dependencies:
   - Python 3.8+
   - pandas
   Install with:
   ```
   pip install pandas
   ```
4. Run:
   ```
   python inventory_monitor.py
   ```

How it works
- On startup the app loads parts.txt and inventory_history.json (if present).
- Click "Browse & Scan" and select an Everest export (.xlsx, .xls or .csv).
- The app reads the spreadsheet treating all fields as text, lowercases and strips column names, and expects two columns:
  - code  (part number)
  - available stock  (quantity)
- Part numbers from parts.txt are cleaned (strip + lowercase) and matched against the spreadsheet.
- For each monitored part the app shows:
  - Previous Qty (from inventory_history.json)
  - Current Qty (from spreadsheet)
  - Status (Not Found, Out of Stock, Dropped, Increased, No Change)
- Visual row tags:
  - alert_zero (soft red) — not found or zero stock
  - alert_drop (soft yellow) — count decreased since last run
  - normal — no notable change
- After scanning the app saves the new counts to inventory_history.json for the next run.
- Popup alerts:
  - Error dialog if required columns are missing or on read errors.
  - Critical alert if any monitored part is at zero.
  - Warning if any monitored part dropped in quantity.
  - Info if nothing changed.

Required file/column names (case-insensitive after cleaning)
- parts.txt — list of monitored part numbers (one per line)
- Spreadsheet columns (must appear after lowercasing and stripping): "code", "available stock"

Behavior notes and assumptions
- Part matching is exact after lowercasing and stripping whitespace; leading zeros are preserved in the spreadsheet read by treating columns as text.
- If a part is not present in the spreadsheet it is treated as current quantity = 0.
- Previous quantities are looked up by the exact original line text from parts.txt (not the cleaned version) to preserve user identifiers.
- Non-numeric quantities in the "available stock" column are coerced to 0.

Customizing
- Change PARTS_FILE or HISTORY_FILE constants at top of the script to use different filenames.
- To use different spreadsheet column names, change:
  part_col = 'code'
  qty_col = 'available stock'
  to your desired column names (in lowercase, since the script normalizes column names).

Troubleshooting
- Missing required columns error: open the spreadsheet and ensure headers exist and match the expected names (after stripping and lowercasing).
- If quantities look wrong, confirm the "available stock" column contains numeric values or empty cells; non-numeric cells convert to 0.
- If parts aren't matched, verify parts.txt entries match the spreadsheet codes when both are stripped and lowercased.

License
- No license specified. Use and modify freely.

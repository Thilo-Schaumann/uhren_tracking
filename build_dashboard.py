"""Combines dashboard_template.html + dashboard_data.json into dashboard.html for publishing."""
from pathlib import Path

template = Path("dashboard_template.html").read_text()
data = Path("dashboard_data.json").read_text()
Path("dashboard.html").write_text(template.replace("__DASHBOARD_DATA__", data))
print("wrote dashboard.html")

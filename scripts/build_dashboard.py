"""Combines dashboard_template.html + dashboard_data.json into dashboard.html for publishing."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
template = (HERE / "dashboard_template.html").read_text()
data = (HERE / "dashboard_data.json").read_text()
(HERE / "dashboard.html").write_text(template.replace("__DASHBOARD_DATA__", data))
print(f"wrote {HERE / 'dashboard.html'}")

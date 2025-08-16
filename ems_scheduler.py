import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, date
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import tempfile

# --------------------
# Configuration
# --------------------
SHIFTS = ["AM", "Midday", "PM"]
SHIFT_COLORS = {
    "AM": colors.lightyellow,
    "Midday": colors.lightblue,
    "PM": colors.lightgrey,
}
ROLES_NEEDED = ["Full EMT", "Probationary EMT", "Observer"]
SHIFT_HOURS = 12

# --------------------
# Scheduler
# --------------------
class Scheduler:
    def __init__(self, staff_df, max_week_paid_hours=240, max_hours_per_person=None):
        self.staff_df = staff_df
        self.max_week_paid_hours = max_week_paid_hours
        self.max_hours_per_person = max_hours_per_person
        self.assignments = {}
        self.violations = []

    def generate_schedule(self, year, month):
        # Simplified assignment: randomly assign available staff to shifts
        self.assignments.clear()
        self.violations.clear()

        num_days = calendar.monthrange(year, month)[1]
        for d in range(1, num_days + 1):
            day_key = date(year, month, d).strftime("%Y-%m-%d")
            for shift in SHIFTS:
                available = self.staff_df[self.staff_df['Availability'].str.contains(shift, na=False)]
                picks = []
                if not available.empty:
                    sampled = available.sample(min(3, len(available)))
                    for _, row in sampled.iterrows():
                        picks.append((row['Name'], row['Role'], row['Paid']))
                self.assignments[(day_key, shift)] = picks

                roles_present = {r for _, r, _ in picks}
                for needed in ROLES_NEEDED:
                    if needed not in roles_present:
                        self.violations.append(f"{day_key} {shift}: missing role {needed}")

    def export_pdf(self, filename, year, month):
        doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
        elements = []
        styles = getSampleStyleSheet()
        title = Paragraph(f"<b>{calendar.month_name[month]} {year}</b>", styles['Title'])
        elements.append(title)

        cal = calendar.Calendar(firstweekday=6)
        weeks = cal.monthdatescalendar(year, month)
        grid_data = []
        grid_data.append([Paragraph(d, styles['Heading5']) for d in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]])
        small = ParagraphStyle('small', parent=styles['Normal'], fontSize=7, leading=8)
        daynum = ParagraphStyle('daynum', parent=styles['Normal'], fontSize=8, alignment=2)

        for week in weeks:
            row = []
            for d in week:
                if d.month != month:
                    row.append("")
                    continue
                day_key = d.strftime("%Y-%m-%d")
                nested_rows = [[Paragraph(f"{d.day}", daynum)]]
                for shift in SHIFTS:
                    picks = self.assignments.get((day_key, shift), [])
                    if picks:
                        lines = [f"{shift}:"] + [f"• {n} ({r}){' $' if paid else ''}" for n, r, paid in picks]
                    else:
                        lines = [f"{shift}: (unfilled)"]
                    nested_rows.append([Paragraph("<br/>".join(lines), small)])
                day_table = Table(nested_rows, colWidths=[100])
                ts = [('BOX', (0,0), (-1,-1), 0.25, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black)]
                for idx, shift in enumerate(SHIFTS, start=1):
                    ts.append(('BACKGROUND', (0, idx), (-1, idx), SHIFT_COLORS[shift]))
                day_table.setStyle(TableStyle(ts))
                row.append(day_table)
            grid_data.append(row)

        col_width = 105
        main_table = Table(grid_data, colWidths=[col_width]*7)
        main_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.6, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(main_table)

        if self.violations:
            viol_text = "<br/>".join([f"• {v}" for v in self.violations])
            elements.append(Paragraph(f"<b>Violations</b><br/>{viol_text}", styles['Normal']))

        doc.build(elements)

# --------------------
# Streamlit UI
# --------------------

def main():
    st.title("🚑 EMS Scheduler")
    st.write("Upload an Excel staff file and generate a monthly wall calendar PDF.")

    uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type="xlsx")
    month = st.number_input("Month", min_value=1, max_value=12, value=datetime.today().month)
    year = st.number_input("Year", min_value=2020, max_value=2100, value=datetime.today().year)
    max_hours = st.number_input("Max Weekly Paid Hours", min_value=0, value=240)

    if uploaded_file:
        staff_df = pd.read_excel(uploaded_file)
        if st.button("Generate Schedule"):
            sched = Scheduler(staff_df, max_week_paid_hours=max_hours)
            sched.generate_schedule(int(year), int(month))

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                sched.export_pdf(tmp.name, int(year), int(month))
                with open(tmp.name, "rb") as f:
                    st.download_button("Download PDF Calendar", f, file_name=f"schedule_{month}_{year}.pdf", mime="application/pdf")

            if sched.violations:
                st.warning("Some violations were detected:")
                for v in sched.violations:
                    st.text(v)

if __name__ == "__main__":
    main()

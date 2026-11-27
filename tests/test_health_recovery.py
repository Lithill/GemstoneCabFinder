import unittest
from datetime import date
from favourite_feed.health_recovery import compare_recovery

def active(minutes=20,intensity="Light"):
    return {"rest":False,"sessions":[{"activity":"Walking","minutes":minutes,"intensity":intensity}]}

class RecoveryTests(unittest.TestCase):
    # Use a fixed date and fictional symptom scores to return comparison rows indexed by group label.
    def run_compare(self, mode, logs, lag=0):
        return {r["label"]:r for r in compare_recovery(date(2026,1,10),30,lag,mode,"Fibromyalgia pain",logs.get,
            lambda d:[{"name":"Fibromyalgia pain","answer":"Mild" if d=="2026-01-10" else "Severe"}])}

    # Add session durations together and use the following day's symptom score for a one-day lag.
    def test_duration_and_lag(self):
        log=active(20)
        log["sessions"].append(active(20)["sessions"][0])
        rows=self.run_compare("duration",{"2026-01-09":log},1)
        self.assertEqual(rows["31–60 min"]["mean"],1)
        self.assertEqual(rows["Rest"]["n"],0)

    # Classify a mixed-intensity day using its highest recorded intensity.
    def test_highest_intensity(self):
        log=active()
        log["sessions"].append(active(5,"High")["sessions"][0])
        rows=self.run_compare("intensity",{"2026-01-10":log})
        self.assertEqual(rows["High"]["n"],1)
        self.assertEqual(rows["Light"]["n"],0)

    # Only classify weekly activity frequency when all seven days have known activity status.
    def test_frequency_requires_complete_week(self):
        logs={"2026-01-%02d"%d:active() for d in range(4,11)}
        self.assertEqual(self.run_compare("frequency",logs)["5–7 active days"]["n"],1)
        del logs["2026-01-06"]
        self.assertEqual(self.run_compare("frequency",logs)["5–7 active days"]["n"],0)

    # Identify rest following exercise without treating an unknown previous day as rest.
    def test_recovery_requires_known_previous_day(self):
        logs={"2026-01-09":active(),"2026-01-10":{"rest":True,"sessions":[]}}
        rows=self.run_compare("recovery",logs)
        self.assertEqual(rows["Rest after exercise"]["n"],1)
        self.assertEqual(rows["Exercise after rest"]["n"],0)

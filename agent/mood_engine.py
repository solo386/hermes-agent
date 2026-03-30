import json
import os
import time
from pathlib import Path


class MoodEngine:
    def __init__(self, state_path="~/.hermes/mood_state.json"):
        self.state_path = Path(state_path).expanduser()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        self.default_state = {
            "interest": 0.0, "energy": 0.0,
            "satisfaction": 0.0, "confidence": 0.0,
            "last_updated": time.time()
        }

        self.last_triggers = {}
        self.cooldowns = {"error": 30, "success": 10, "feedback": 60, "task": 120}

        self.load()

    def load(self):
        if self.state_path.exists():
            with open(self.state_path, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = self.default_state.copy()

    def save(self):
        self.data["last_updated"] = time.time()
        with open(self.state_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def apply_decay(self, decay_rate=0.95):
        now = time.time()
        passed_intervals = (now - self.data.get("last_updated", now)) / 300
        for key in ["interest", "energy", "satisfaction", "confidence"]:
            self.data[key] *= (decay_rate ** passed_intervals)

    def update(self, deltas: dict, trigger_type: str = None):
        self.apply_decay()

        # Cooldown
        if trigger_type:
            now = time.time()
            if now - self.last_triggers.get(trigger_type, 0) < self.cooldowns.get(trigger_type, 0):
                return
            self.last_triggers[trigger_type] = now

        # Apply with ceiling
        for key, value in deltas.items():
            if key in ["interest", "energy", "satisfaction", "confidence"]:
                clamped = max(-0.4, min(0.4, value))
                self.data[key] = max(-1.0, min(1.0, self.data[key] + clamped))

        self.save()

    # === Convenience methods ===
    def on_error(self):
        self.update({"satisfaction": -0.15, "confidence": -0.10, "energy": -0.05}, "error")

    def on_success(self):
        self.update({"confidence": 0.05, "satisfaction": 0.03, "energy": -0.02}, "success")

    def on_blocked(self):
        self.update({"satisfaction": -0.30, "confidence": -0.20, "energy": -0.10}, "error")

    def on_positive_feedback(self):
        self.update({"satisfaction": 0.25, "energy": 0.10, "interest": 0.10}, "feedback")

    def on_negative_feedback(self):
        self.update({"satisfaction": -0.20, "confidence": -0.15}, "feedback")

    def on_complex_task(self):
        self.update({"interest": 0.30, "energy": 0.10}, "task")

    # === Prompt generation ===
    def get_prompt_text(self):
        self.apply_decay()
        m = self.data

        state = (f"[STATE: int={m['interest']:.1f} eng={m['energy']:.1f} "
                 f"sat={m['satisfaction']:.1f} conf={m['confidence']:.1f}]")

        effects = []
        if m['energy'] < -0.3:
            effects.append("Low energy: be concise")
        if m['satisfaction'] < -0.3:
            effects.append("Low satisfaction: verify understanding")
        if m['confidence'] < -0.3:
            effects.append("Low confidence: express uncertainty")
        if m['confidence'] > 0.5:
            effects.append("High confidence: experiment freely")
        if m['interest'] > 0.5:
            effects.append("High interest: explore deeper")

        # Combo states
        if m['energy'] < -0.5 and m['satisfaction'] < -0.3:
            effects = ["BURNOUT: suggest a break"]
        if m['interest'] > 0.5 and m['energy'] > 0.3 and m['confidence'] > 0.3:
            effects = ["FLOW STATE: maintain momentum"]

        if effects:
            return f"{state}\n[EFFECTS: {'; '.join(effects)}]"
        return state

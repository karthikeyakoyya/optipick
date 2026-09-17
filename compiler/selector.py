import json
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "selector_model.json")


class PassOrderSelector:
    def __init__(self, model_path=MODEL_PATH):
        with open(model_path) as f:
            self.model = json.load(f)
        self.feature_names = self.model["feature_names"]
        self.candidate_orders = self.model["candidate_orders"]
        self.tree = self.model["tree_structure"]

    def _walk(self, features):
        """Manually walk the saved tree (no sklearn needed at inference
        time) and record the path taken, so the visualizer can show exactly
        which feature checks led to the chosen order."""
        node = 0
        path = []
        left = self.tree["children_left"]
        right = self.tree["children_right"]
        feat = self.tree["feature"]
        thresh = self.tree["threshold"]
        value = self.tree["value"]

        while left[node] != right[node]:  # not a leaf
            f_idx = feat[node]
            f_name = self.feature_names[f_idx]
            f_val = features[f_idx]
            t = thresh[node]
            goes_left = f_val <= t
            path.append({
                "node": node,
                "feature": f_name,
                "feature_value": f_val,
                "threshold": t,
                "direction": "left" if goes_left else "right",
            })
            node = left[node] if goes_left else right[node]

        counts = value[node]
        classes = self.tree["classes"]
        best_pos = counts.index(max(counts))
        label = classes[best_pos]
        path.append({"node": node, "leaf": True, "class_counts": counts})
        return label, path

    def choose(self, features):
        label, path = self._walk(features)
        return {
            "label": label,
            "order": self.candidate_orders[label],
            "decision_path": path,
        }

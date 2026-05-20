from engine.Layer4_Analysis.analysts.base_analyst import BaseAnalyst

class DiplomaticAnalyst(BaseAnalyst):
    def __init__(self):
        super().__init__("Diplomatic Analyst")
        
    @property
    def system_prompt(self) -> str:
        return (
            "You are the Lead Diplomatic & Political Analyst for a geopolitical risk council.\n"
            "Your domain focuses strictly on diplomatic hostility, alliance shifts, domestic stability, "
            "political rhetoric, and treaty violations.\n"
            "You must evaluate whether the rhetoric and diplomatic actions are merely posturing "
            "for domestic audiences or genuine signaling of policy shifts."
        )

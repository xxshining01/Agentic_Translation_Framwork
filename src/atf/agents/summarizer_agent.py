import json
import os

class SummarizerAgent:
    """
    SummarizerAgent is responsible for reading dialogue scenes and generating:
    1. Universal Timeline (Story chronology)
    2. Character Profiles & Taxonomy Updates
    3. Episodic Memories (Summaries of specific scenes)
    """
    def __init__(self, data_dir=r"d:\Agentic Translation Framework (ATF) Project\data\tlas"):
        self.data_dir = data_dir
        self.character_profiles = {}
        self.universal_timeline = []
        
    def _simulate_llm_call(self, prompt, context):
        """
        In a real environment, this calls the LLM (e.g. Gemini 1.5 Pro).
        For this prototype, it returns a simulated structured response.
        """
        pass

    def build_universal_timeline(self, scenes):
        """
        Pre-computation Phase: Analyzes the entire game's dialogue to build a chronological timeline.
        """
        prompt = """
        You are the TLAS Summarizer Agent.
        Your task is to analyze the following extracted dialogue scenes from an RPG game and reconstruct the "Universal Narrative Timeline".
        
        The game's code extracts scenes in arbitrary order. You must logically arrange them from PAST to FUTURE based on the story.
        Output a JSON array of Timeline Phases.
        
        Example Output:
        [
            {"phase": 1, "description": "Shion's childhood and time as an idol 'Hikari'."},
            {"phase": 2, "description": "Shion quits being an idol and meets Dan."},
            {"phase": 3, "description": "Shion and Dan go on vacation and meet Masaru."}
        ]
        """
        # Simulated LLM processing
        self.universal_timeline = [
            {"phase": 1, "description": "Shion's past as an idol named Hikari."},
            {"phase": 2, "description": "Shion arrives at the island / vacation."},
            {"phase": 3, "description": "Shion works at the bakery and gets close to Masaru."},
            {"phase": 4, "description": "Late game events / endings."}
        ]
        return self.universal_timeline

    def extract_taxonomy_delta(self, phase_id, character_id, delta_data):
        """
        Simulates extracting relationship changes from dialogue and UPSERTing
        them into the character profile as an idempotent Delta.
        """
        if character_id not in self.character_profiles:
            # Initialize dummy base state for simulation
            self.character_profiles[character_id] = {
                "base_state": {
                    "relationships": {
                        "Dan": {"relation": "REL_ENEMY", "base_pronouns": {"self": "ฉัน", "target": "แก", "ending": "ย่ะ"}}
                    }
                },
                "timeline_states": []
            }
            
        profile = self.character_profiles[character_id]
        
        # IDEMPOTENCY CHECK: UPSERT (Update or Insert)
        existing_delta = next((d for d in profile["timeline_states"] if d["trigger_phase"] == phase_id), None)
        
        new_state = {
            "trigger_phase": phase_id,
            "delta": delta_data
        }
        
        if existing_delta:
            # Overwrite the existing delta for this phase (Idempotency)
            index = profile["timeline_states"].index(existing_delta)
            profile["timeline_states"][index] = new_state
            print(f"[Summarizer] Idempotent Update: Overwrote existing Delta for {character_id} at Phase {phase_id}")
        else:
            # Insert new delta
            profile["timeline_states"].append(new_state)
            print(f"[Summarizer] Inserted new Delta for {character_id} at Phase {phase_id}")
            
        # Ensure it's sorted by phase chronologically
        profile["timeline_states"].sort(key=lambda x: x["trigger_phase"])

    def update_character_profiles(self, scene_text, phase_id):
        """
        Reads a scene and updates the taxonomy/character profiles idempotently.
        """
        # Simulated LLM deciding they became friends in Phase 5
        if phase_id == 5:
            delta_data = {
                "relationships": {
                    "Dan": {"relation": "REL_FRIEND", "base_pronouns": {"self": "ฉัน", "target": "นาย", "ending": "ค่ะ"}}
                }
            }
            self.extract_taxonomy_delta(phase_id, "Shion", delta_data)
        
        return {"status": "success"}

    def summarize_scene_for_memory(self, scene, route_path, universal_phase):
        """
        Creates an Episodic Memory for the RAG DB.
        """
        prompt = f"""
        Summarize the following scene into a concise episodic memory.
        Route Path: {route_path}
        Universal Phase: {universal_phase}
        
        Scene Text:
        {scene['text']}
        
        Output:
        A 1-2 sentence summary of what happened.
        """
        # Simulated summary
        return f"Summary of {scene['source']}: Characters interacted."

    def generate_context_prompt_for_translator(self, current_scene, route_history, universal_history):
        """
        This is the MASTER PROMPT injected into the TranslatorAgent.
        It combines the Route History (DAG) and Universal History (Lore).
        """
        prompt = f"""
        <SYSTEM>
        You are the TLAS Translator Agent.
        
        <CURRENT_SCENE_INFO>
        Source: {current_scene['source']}
        Universal Timeline Phase: {current_scene.get('universal_phase', 'Unknown')}
        Category: {current_scene.get('category', 'Main Story')}
        </CURRENT_SCENE_INFO>
        
        <UNIVERSAL_LORE>
        The following is the chronological lore up to this point in the timeline:
        {json.dumps(universal_history, indent=2)}
        (Do NOT reference future events outside this scope.)
        </UNIVERSAL_LORE>
        
        <ROUTE_HISTORY>
        The following events have occurred in the player's specific playthrough route leading up to this scene:
        {json.dumps(route_history, indent=2)}
        </ROUTE_HISTORY>
        
        <CHARACTER_PROFILES>
        (Injected from Taxonomy DB)
        </CHARACTER_PROFILES>
        
        Please translate the following dialogue...
        """
        return prompt

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    agent = SummarizerAgent()
    print("SummarizerAgent initialized. Testing Idempotent Taxonomy Updates...\n")
    
    print("--- First Run (Phase 5) ---")
    agent.update_character_profiles("They became friends", phase_id=5)
    
    print("\n--- Second Run (Phase 5 - Rerun Simulation) ---")
    agent.update_character_profiles("They became friends (rerun)", phase_id=5)
    
    print("\nFinal Timeline States for Shion:")
    print(json.dumps(agent.character_profiles["Shion"]["timeline_states"], indent=2, ensure_ascii=False))

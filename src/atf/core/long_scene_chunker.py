import json

class LongSceneChunkerPrototype:
    def __init__(self):
        # 1. Mock Global RAG Context (What the character experienced so far)
        self.global_rag_lore = (
            "[UNIVERSAL TIMELINE - PHASE 5]\n"
            "Summary: Dan and Shion successfully escaped the burning slums. They are now hiding in the old church. "
            "They have resolved their past misunderstandings and agreed to work together."
        )
        
        # 2. Mock TLAS Profile (The current state of their relationship)
        self.tlas_profile = (
            "[TLAS CHARACTER PROFILE]\n"
            "Shion -> Dan: REL_FRIEND, REG_POLITE_INFORMAL, EMO_RELIEVED\n"
            "Dan -> Shion: REL_FRIEND, REG_CASUAL, EMO_PROTECTIVE"
        )
        
        # 3. Mock a long dialogue scene (Representing 50,000 words, but shortened here for terminal output)
        self.full_scene = []
        for i in range(1, 41):
            if i <= 20:
                self.full_scene.append(f"Line {i}: [Shion/Dan discussing escape plan and resting]")
            elif i <= 30:
                self.full_scene.append(f"Line {i}: [Shion/Dan reflecting on the past]")
            else:
                self.full_scene.append(f"Line {i}: [Suddenly, enemies break down the church door!]")
                
    def chunk_scene(self, lines, chunk_size=15):
        """Simulates Semantic Split: Chunks the scene into manageable blocks."""
        chunks = []
        for i in range(0, len(lines), chunk_size):
            chunks.append(lines[i:i+chunk_size])
        return chunks

    def assemble_prompt(self, chunk_id, current_chunk, previous_chunk):
        """Assembles the actual Prompt the Translator Agent receives."""
        prompt = f"========== PROMPT FOR CHUNK {chunk_id} ==========\n\n"
        
        # Part 1: Global Context (Never lost)
        prompt += "=== 1. GLOBAL LORE (From RAG) ===\n"
        prompt += self.global_rag_lore + "\n\n"
        
        # Part 2: TLAS State (Never lost)
        prompt += "=== 2. CURRENT RELATIONSHIP (From TLAS) ===\n"
        prompt += self.tlas_profile + "\n\n"
        
        # Part 3: Rolling Context (To maintain translation consistency)
        prompt += "=== 3. ROLLING CONTEXT (Last 5 lines of previous chunk) ===\n"
        if previous_chunk:
            rolling_context = "\n".join(previous_chunk[-5:])
            prompt += rolling_context + "\n\n"
        else:
            prompt += "(None - This is the start of the scene)\n\n"
            
        # Part 4: The Actual Content to Translate
        prompt += "=== 4. TEXT TO TRANSLATE (Current Chunk) ===\n"
        prompt += "\n".join(current_chunk) + "\n"
        
        prompt += "\n============================================\n"
        return prompt

    def run_simulation(self):
        print("Starting Long Scene Chunker Simulation...\n")
        
        # Split into chunks of 15 lines (Simulating 8,000 word limits)
        chunks = self.chunk_scene(self.full_scene, chunk_size=15)
        
        previous_chunk = None
        for idx, chunk in enumerate(chunks, 1):
            # Assemble the prompt
            prompt = self.assemble_prompt(idx, chunk, previous_chunk)
            print(prompt)
            
            # The current chunk becomes the previous chunk for the next iteration
            previous_chunk = chunk

if __name__ == "__main__":
    prototype = LongSceneChunkerPrototype()
    prototype.run_simulation()

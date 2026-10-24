# TLAS Annotation Guideline

**Version:** 1.0
**Target Audience:** Human Annotators, Data Engineers, and AI Analyzer Agents

## 1. Introduction
The Translation Linguistic Annotation System (TLAS) relies on strict, deterministic metadata (Tags) to guide the AI Translator. This guideline defines how to annotate and assign tags to Character Profiles and Dialogue Metadata.

## 2. The Golden Rule of Tagging
> **"Does this piece of information affect linguistic choices?"**

Before assigning a tag, ask yourself if it impacts:
1. Pronoun Selection (ผม/คุณ vs ฉัน/แก)
2. Honorifics (ครับ/ค่ะ, สิ/นะ)
3. Register/Formality (ทางการ/เป็นกันเอง)
4. Sentence Style & Vocabulary

If the answer is **NO**, do not create or assign the tag. (e.g., Do not tag a character as "Loves Pizza" unless they use pizza-specific slang in all their sentences).

## 3. Annotating Character Knowledge (Base & Delta)

When creating a `character_profile_template.json`:
- **Personality (PER):** Assign base traits that dictate their default way of speaking. E.g., `PER_SOC_POLITE`.
- **Relationships (REL):** Map how this character views others. The relationship is *directional*. If A views B as a boss, A has `REL_WORK_BOSS` targeting B. 
- **Timeline Deltas:** Characters evolve. Do not overwrite the base state if the change is temporary. Use `timeline_states` linked to a `trigger_event`. For example, after an argument, add a delta to change `REL_FRIEND` to `REL_ENEMY` and override the pronoun from `เรา` to `ฉัน`.

## 4. Annotating Dialogue Metadata (For Analyzer Agent)

When the Analyzer Agent receives a sentence, it must assign situational tags based on the current context provided by the Summarizer Agent.

### 4.1 Emotion (EMO)
Tag the emotion of the speaker *at the exact moment of speaking*. Emotion overrides default personality. 
- Example: A usually polite character (`PER_SOC_POLITE`) shouting in anger (`EMO_NEG_ANGER`) might drop their polite ending particles ("ครับ/ค่ะ").

### 4.2 Intent (INT)
What is the speaker trying to achieve?
- `INT_PERSUADE`: Will soften the tone.
- `INT_THREATEN`: Will harden the tone and may change pronouns.
- `INT_INFORM`: Neutral.

### 4.3 Situation (SIT)
Where are they, and who is listening?
- `SIT_PUBLIC`: Forces `REG_FORMAL` even if the characters are close friends.
- `SIT_PRIVATE`: Allows `REG_CASUAL`.

## 5. Conflict Resolution (How the Engine Decides)
If tags conflict, the TLAS Decision Engine applies priority rules:
**Situation (SIT) > Emotion (EMO) > Relationship (REL) > Personality (PER)**

*Example:* 
Base Personality is `PER_SOC_RUDE`.
But they are talking to the King (`REL_ROYAL`) in a Public Ceremony (`SIT_PUBLIC`).
*Result:* The Situation and Relationship override Personality. The Engine maps to Royal Register (`REG_ROYAL`) and uses "ฝ่าบาท / กระหม่อม".

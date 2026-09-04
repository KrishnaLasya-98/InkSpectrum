# 📘 End-to-End K-10 Textbook Video Generation Pipeline: Complete Architectural Plan

This plan outlines the complete, end-to-end execution strategy for converting K-10 textbooks into exhaustive, chapter-by-chapter video lectures (covering both theoretical and exercise sections) using our sibling repositories as a "Standard Library" via an Orchestration Architecture.

---

## 1. Core Philosophy: Complete End-to-End (Zero-Summary) Lectures

Standard video generators typically summarize input documents into a brief 2-minute overview. For academic textbooks (grades 1–10), this approach fails. A student needs to learn **every concept, every key term, and solve every question** in the chapter.

### Structural Partitioning Strategy
Instead of compressing a 15-page chapter into one short video, we treat a chapter as a **Lecture Playlist** consisting of multiple cohesive video parts:
1. **Part 1: Concept Deep-Dive (Theory)**
   - Walkthrough of all explanations, examples, and diagrams.
   - Verbatim reading of critical definitions (e.g., "The crown is seen above the gum...").
   - Detailed visual breakdown of complex topics (e.g., stages of digestion, vowel sounds).
2. **Part 2: Active Recall & Glossary**
   - Vocabulary cards, pronunciation guides, and interactive questions embedded in the textbook (e.g., "Warm Up" or "Read and Enjoy" reflections).
3. **Part 3: Comprehensive Exercise Walkthrough (Hands-on)**
   - Every single exercise, question, matching activity, or fill-in-the-blank is displayed, analyzed, and solved step-by-step on screen.
   - Explanations of *why* an answer is correct (e.g., explaining why Aristotle said outdoor environment is essential).

---

## 2. In-Depth Analysis of Actual Textbook Inputs

Based on our initial PyMuPDF inspection of the four primary RPS textbooks, here is how the physical pages map to our structural pipeline and where the specific risks lie:

### A. English Reader (Class 1 & Class 5)
*   **Structure Detected**: 
    - **Class 1**: Begins with Phonics Worksheets (Pages 7-16) covering letters (A to Z), vowels, and rhyming words, before moving into "Lesson 1 - At the Beach" (Page 17+).
    - **Class 5**: Structured around units like "Lesson 1 - Outdoor life" (Page 7-18). It starts with conversational pair-work ("Do you know your neighbours?"), moves to a Wordsworth literary passage ("Read and Enjoy", Page 8), provides a structured "Glossary" (Page 11), and ends with grammar and writing grids ("Think and Answer", Page 12; "Countable and Uncountable nouns word grid", Page 14).
*   **Technical Risks & Solutions**:
    - *Word Grids / Puzzles (Class 5, Page 14)*: Direct text parsers will spit out a garbled line of letters. 
        - **Solution**: Docling will detect the grid coordinates. We map these to an HTML/SVG `WordGrid` component in our scene vocabulary, allowing the renderer to dynamically highlight the found words on screen.
    - *Phonics Sounds (Class 1, Pages 7-16)*: Representation of phonetic slash-notations (e.g., `says /a/ as in Apple`).
        - **Solution**: Custom script templates to instruct the TTS to speak phonetically (e.g., using SSML `<phoneme>` tags if available, or spelling out pronunciation in narration scripts) while showing standard phonetic markers on screen.

### B. Mathematics Pioneers (Class 1)
*   **Structure Detected**:
    - Pages 7-13: Deep instructional math detailing how numbers are formed (e.g., "50 (5 Tens) + 1 (1 ones) = 51").
    - Page 14: "Let's Do" (Exercises on number compilation).
    - Page 15: "Number names 1-100".
*   **Technical Risks & Solutions**:
    - *Spatial Math Representation (Block groupings)*: "5 Tens" is represented in books by 5 bundles of sticks or blocks. Pure text parses this as `50 (5 Tens) +`.
        - **Solution**: We detect math patterns in Docling (which returns formulas and bounding boxes for diagrams). Our wrapper maps block groups into dynamic, programmatic SVG renders (`NumberBlocks` scene step) where bundles are animated sliding together.
    - *Math Exercises*: Rows of empty circles/boxes for kids to fill in.
        - **Solution**: The parser extracts the math equation. The script generator generates a "Step-by-Step Solve" scene step, where the question is displayed, a hand-drawn circle or highlight encircles the numbers, and the solution appears in a "handwritten" style font.

### C. Environmental Studies: EVS (Class 4)
*   **Structure Detected**:
    - Highly dense, structured, factual textbook. "Lesson 1: Digestion" (Page 6+) covers teeth types (Incisors, Canines, Premolars, Molars), tooth structure (Crown, Neck, Root), healthy dental habits, and the stages of digestion (Stomach, digestive juices, hydrochloric acid).
*   **Technical Risks & Solutions**:
    - *Anatomical Diagrams (Tooth Structure, Digestive System)*: Text refers heavily to "crown above the gum", "root inside the jaw", which is incomprehensible without seeing the diagram.
        - **Solution**: Use Docling's high-fidelity layout parser to extract the image coordinates. The crop is passed to the ModelsLab Image API for clean visual asset synthesis or is dynamically labeled on screen using SVG overlays with animated pointers pointing to the "crown" and "root" in sync with the audio.

---

## 3. High-Fidelity Ingestion Plan (Docling + Layout Engine)

```
[Textbook PDF] ──> [Docling Parser] ──> [Layout Analyzer & Cropper] ──> [Chapter Grouper] ──> [ChapterNode JSON]
                                                    │ (Extract figures, formulas)
                                                    └──> [ModelsLab Asset Pipeline] ──> [Local Media Assets]
```

To extract every piece of content without omitting paragraphs, we use a hybrid parsing process:
1.  **Logical Chapter Detection**: 
    - The system reads the Table of Contents page (found via regex matching like `CONTENT`, `INDEX`, `page`) and maps Chapter Titles to Page Ranges.
    - **Self-Healing Backup**: If no programmatic TOC page is found, the system scans the entire document for primary headers (e.g., `Lesson \d+`, `Chapter \d+`) to map the boundaries.
2.  **Paragraph and Layout Preservation**:
    - Docling processes the chapter pages, preserving tables, sidebar panels (like "Key Features" or "Do you know?"), and lists.
    - Formulas are extracted as LaTeX string objects.
    - Bounding boxes for diagram blocks are cropped and saved to disk.
3.  **Logical Grouping**:
    - Content is split into hierarchical blocks: `ChapterNode` -> `SectionNode` (with `SectionType` like `Theory`, `Glossary`, `Activity`, `Grammar`, `Exercise`).
    - Every exercise is explicitly mapped to an `ExerciseNode` to guarantee no questions are left behind.

---

## 4. The Scripting Strategy: Pedagogical "Two-Track" Exhaustive Narration

Our script generator translates the raw `ChapterNode` into a multi-scene, conversational, word-perfect script. It operates on two distinct tracks based on section type:

### Track A: Theoretical Chapter Lectures (Concept Deep-Dive)
*   **Role**: An expert teacher explaining the subject with high rigor.
*   **Visual Strategy**: High-contrast, structured layout. Direct diagrams, bold key terms, and visual lists. No bullet-points. Text appears dynamically in sync with the spoken word.
*   **Narration Style**: Verbatim integration of textbook text, spoken with natural transitions. (e.g., *"Let's understand the structure of a tooth. Every tooth in our mouth has two main parts: the crown and the root. The crown is the top part that you can see above the gum, while the root..."*).

### Track B: Exercise Section Walkthroughs (The Problem Solver)
*   **Role**: A patient tutor guiding the student through exercises.
*   **Visual Strategy**: "Split Screen" or "Focus Card" representation. Left: The question as written in the textbook. Right: Step-by-step resolution steps appearing one-by-one.
*   **Narration Style**: Walkthrough of each option, highlighting common mistakes, and presenting the final answer. (e.g., *"Now let's look at Exercise A, Question 1. It asks: 'Do you know your neighbours and do you spend time with them?' This is a personal question! Let's think about how you can write a perfect answer. You could say: 'Yes, I know my neighbours. We often play together in the park in the evening.' Let's write that down."*)

---

## 5. Script-to-Storyboard & Scene Vocabulary Mapping

The script is mapped to a highly restricted, predictable **Scene Primitive Vocabulary**. This makes rendering completely deterministic and robust, avoiding visual glitches.

### Core Visual Primitives (The Renderer Interface)
*   `TitleScreen`: Clean, thematic title with chapter number and subject colors.
*   `ConceptFocus`: Centered main concept with surrounding supporting details that slide in as mentioned.
*   `VocabularyCard`: Shows a key term on the left, with its phonetic pronunciation and meaning appearing on the right in sync with TTS.
*   `FormulaBuilder` (Math only): Programs LaTeX steps to animate one line at a time (e.g., $50 + 1 \to 51$).
*   `DiagramLabeler` (EVS/Science): Renders a diagram on the left (e.g., Digestive tract) with pointers highlight-pulsing on the right as parts are named.
*   `QuestionAnswerCard`: Splits the screen. Question on top, interactive checkboxes or blanks getting filled dynamically with an ink-drawing animation.

---

## 6. End-to-End Execution Roadmap

Here is our step-by-step roadmap for developing this system, keeping us focused on verifiable milestones:

```
[Phase 1: Ingestion & Analysis] ──> [Phase 2: Pedagogical Scripting] ──> [Phase 3: TTS & Visual Assembly] ──> [Phase 4: Composition & Composition Tests]
           │                                      │                                    │                                      │
    (WE ARE HERE:                          (LLM Multi-Scene                      (Edge TTS +                          (Remotion CLI / Manim
   Validating actual                      Script generation for                 ModelsLab Assets)                      render & CPU validation)
    RPS textbook files)                    whole chapter nodes)
```

### Phase 1: High-Fidelity PDF Ingestion (Active Step)
*   **Task 1.1**: Run our `docling_client` and `chapter_grouper` on the Class 5 English book (specifically Lesson 1: Outdoor Life, Pages 7-18) to verify how it extracts:
    - The textual narration of Wordsworth.
    - The glossary table on Page 11.
    - The exercises on Page 12.
*   **Task 1.2**: Save the resulting structured `ChapterNode` JSON file to `projects/english_class5_outdoor/chapter_1.json` and perform a structural audit (What was correctly mapped? What was missed?).
*   **Task 1.3**: Do the same for Class 1 Math (Pages 7-15) and save to `projects/math_class1_numbers/chapter_1.json`. Focus specifically on equation layout structures.

### Phase 2: Pedagogical Script Synthesis
*   **Task 2.1**: Build `lib/script_writer/generator.py` using Groq / LLM chain.
*   **Task 2.2**: Write prompt templates specifically optimized for English, Math, and EVS textbooks (ensuring zero summary, verbatim definitions, and comprehensive exercise coverage).
*   **Task 2.3**: Generate full length scripts for Class 5 English Chapter 1 and Class 1 Math Chapter 1, validating against `schemas/script.py` (ScriptScene structure).

### Phase 3: Sibling Repo Integration (The "Standard Library" Bridge)
*   **Task 3.1**: Build `wrappers/remix_exporter.py` to bridge to `video_explainer`’s audio-first timing engine. This will generate the TTS files and output the word-level alignment JSON.
*   **Task 3.2**: Build the ModelsLab Asset Generator in `lib/compositor/assets.py` to auto-generate graphics/diagrams or background slides if any are missing from PDF crops.

### Phase 4: Video Synthesis & Composition (CPU Native)
*   **Task 4.1**: Create the React template components in `lib/renderers/remotion/` matching our Scene Primitives.
*   **Task 4.2**: Trigger the Remotion command-line renderer using Node.js to render the video frame-by-frame on CPU and compile the final MP4.
*   **Task 4.3**: Integrate a validation loop (using Gemini Vision or simple programmatic video checks) to ensure word synchronization, subtitle alignment, and overlay coordinates are flawless.

---

## 7. Immediate Actionable Plan

To get started right away and see real, physical results:

1.  **Verify Docling is active**: We will write a lightweight check script to run a real docling extraction on the first 12 pages of `RPS - ENGLISH - CLASS 5 - VOLUME - 1 (2026) PRINTFILE.pdf` (which contains a complete lesson, glossary, and exercise).
2.  **Generate Structured JSON**: We will run the `docling_client` and `chapter_grouper` to output a real `ChapterNode` JSON to disk.
3.  **Inspect the Extraction**: We will print out the exact list of theoretical sections, glossary items, and exercise nodes detected by the pipeline. This lets us verify "what is recognized and what not" before we write any script-generation prompts.

Shall we execute this plan for the English Class 5 Lesson 1 now?

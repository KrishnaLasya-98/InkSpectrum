# Stage Director: input_ingestion

## Overview
Execute the input ingestion stage for EduStream Pilot content.

## Tool Selection
- Primary: `hybrid_pdf_extractor` tool (or OpenDataLoader/Marker directly)

## Decision Tree
```
if math_density > 5:
    route -> Marker
elif math_density > 0 and layout_complexity > 0.7:
    route -> hybrid
else:
    route -> OpenDataLoader local
```

## Execution Steps
1. **Pre-scan** with OpenDataLoader first (0.015s/page, no GPU)
2. **If Marker needed**: `marker_single <path> --mode balanced --use_llm --redo_inline_math`
3. **Count LaTeX equations**: regex for `\$\$`, `\$`, `\begin{equation}`, `\begin{align}`, `\frac`, `\int`, `\sum`, `\sqrt`

## Output Schema
- `extracted_content` with markdown, structured JSON, formula blocks, confidence score

## Self-Healing
- If extraction confidence < 0.85, try alternate engine

## End Condition
- Confidence >= 0.85 on all pages OR all engines exhausted

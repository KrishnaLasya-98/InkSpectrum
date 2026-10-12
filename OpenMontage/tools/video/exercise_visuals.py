"""Source-linked exercise visuals for the locked educational panel."""
from copy import deepcopy
import hashlib
import html
import math
from pathlib import Path
import shutil


def prepare_visual(question, words, start_seconds, earliest_seconds, latest_seconds, base_dir, asset_dir):
    raw = question.get("exercise_visual")
    if raw is None:
        if question.get("qa_format") in {"matching", "diagram_label", "grammar_sentence", "table_fill", "math_worked"}:
            raise ValueError("Specialized exercise requires exercise_visual data")
        return None
    if not isinstance(raw, dict):
        raise ValueError("exercise_visual must be an object")
    visual = deepcopy(raw)
    kind = visual.get("kind")
    def short(text):
        if not isinstance(text, str) or not text.strip() or len(text) > 32:
            raise ValueError("Exercise labels must be nonempty and at most 32 characters; split dense screens")
    if kind == "matching":
        for column in ("left", "right"):
            items = visual.get(column)
            if not isinstance(items, list) or not 1 <= len(items) <= 4:
                raise ValueError("Matching requires one to four items per column")
            for item in items:
                if not isinstance(item, dict): raise ValueError("Matching items must be objects")
                short(item.get("id")); short(item.get("text"))
            if len({i["id"] for i in items}) != len(items):
                raise ValueError("Matching item IDs must be unique")
        reveals = visual.get("matches", [])
        if not isinstance(reveals, list) or len(reveals) != len(visual["left"]) or len(reveals) != len(visual["right"]):
            raise ValueError("Matching must include every item exactly once")
        if any(not isinstance(m, dict) for m in reveals):
            raise ValueError("Matching pairs must be objects")
        for key, column in (("left_id", "left"), ("right_id", "right")):
            if {m.get(key) for m in reveals} != {i["id"] for i in visual[column]}:
                raise ValueError("Invalid or incomplete matching references")
    elif kind == "diagram_label":
        if visual.get("source_block_id") not in question.get("visual_source_block_ids", []):
            raise ValueError("Diagram must reference a reviewed visual source block")
        reveals = visual.get("labels", [])
        if not isinstance(reveals, list) or not 1 <= len(reveals) <= 4:
            raise ValueError("Diagram requires one to four labels")
        for label in reveals:
            if not isinstance(label, dict): raise ValueError("Diagram labels must be objects")
            short(label.get("text"))
            for field in ("x", "y", "target_x", "target_y"):
                value = label.get(field)
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError("Diagram coordinates must be finite normalized values")
            if not .1 <= label["x"] <= .9 or not .1 <= label["y"] <= .9:
                raise ValueError("Diagram label text must stay inside the safe area")
        path = Path(str(visual.get("image_path", "")))
        if not path.is_absolute(): path = Path(base_dir) / path
        path = path.resolve()
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("Diagram requires an existing local raster PDF crop")
        from PIL import Image
        with Image.open(path) as img:
            visual["width"], visual["height"] = img.size
            img.verify()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if visual.get("image_sha256") != digest:
            raise ValueError("Diagram image hash missing or changed; review the source crop")
        asset_dir.mkdir(parents=True, exist_ok=True)
        destination = asset_dir / (digest + path.suffix.lower())
        if destination != path: shutil.copyfile(path, destination)
        visual["image_path"] = "assets/exercises/" + destination.name
    elif kind == "grammar_sentence":
        sentence = visual.get("sentence")
        if not isinstance(sentence, str) or not sentence.strip() or len(sentence) > 180:
            raise ValueError("Grammar sentence must contain 1 to 180 characters")
        tokens = sentence.split()
        if not 1 <= len(tokens) <= 18:
            raise ValueError("Grammar sentence must contain one to eighteen tokens; split dense screens")
        reveals = visual.get("corrections", [])
        if not isinstance(reveals, list) or not 1 <= len(reveals) <= 6:
            raise ValueError("Grammar exercise requires one to six corrections")
        seen = set()
        for correction in reveals:
            if not isinstance(correction, dict):
                raise ValueError("Grammar corrections must be objects")
            index = correction.get("token_index")
            if type(index) is not int or not 0 <= index < len(tokens) or index in seen:
                raise ValueError("Grammar correction token indices must be unique and valid")
            seen.add(index)
            short(correction.get("text"))
        visual["tokens"] = tokens
    elif kind == "table_fill":
        source_id = visual.get("source_block_id")
        if source_id not in question.get("visual_source_block_ids", []):
            raise ValueError("Table must reference a reviewed visual source block")
        headers, rows = visual.get("headers"), visual.get("rows")
        if not isinstance(headers, list) or not 1 <= len(headers) <= 5:
            raise ValueError("Table requires one to five headers")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 6:
            raise ValueError("Table requires one to six rows; paginate dense tables")
        for value in headers:
            short(value)
        for row in rows:
            if not isinstance(row, list) or len(row) != len(headers):
                raise ValueError("Every table row must match the header width")
            for value in row:
                if not isinstance(value, str) or len(value) > 48:
                    raise ValueError("Table cells must be strings up to 48 characters")
        reveals = visual.get("answers", [])
        if not isinstance(reveals, list) or not 1 <= len(reveals) <= 8:
            raise ValueError("Table exercise requires one to eight answer reveals")
        positions = set()
        for answer in reveals:
            if not isinstance(answer, dict):
                raise ValueError("Table answers must be objects")
            row, column = answer.get("row"), answer.get("column")
            if (type(row) is not int or type(column) is not int or
                    not 0 <= row < len(rows) or not 0 <= column < len(headers) or
                    (row, column) in positions):
                raise ValueError("Table answer coordinates must be unique and valid")
            positions.add((row, column))
            short(answer.get("text"))
    elif kind == "math_worked":
        expression = visual.get("expression")
        if not isinstance(expression, str) or not expression.strip() or len(expression) > 96:
            raise ValueError("Math expression must contain 1 to 96 characters")
        reveals = visual.get("steps", [])
        if not isinstance(reveals, list) or not 1 <= len(reveals) <= 6:
            raise ValueError("Worked mathematics requires one to six narrated steps")
        for step in reveals:
            if not isinstance(step, dict) or not isinstance(step.get("text"), str):
                raise ValueError("Math steps must be objects with text")
            if not step["text"].strip() or len(step["text"]) > 120:
                raise ValueError("Math steps must be 1 to 120 characters; split dense solutions")
    else:
        raise ValueError("Unsupported exercise visual kind")

    def token(text): return text.casefold().strip('.,!?;:\"\u201c\u201d')
    spoken = [token(w["word"]) for w in words]
    cursor = 0
    for item in reveals:
        cue = item.get("cue_text")
        if not isinstance(cue, str) or not cue.strip():
            raise ValueError("Every exercise reveal needs spoken cue_text")
        target = [token(t) for t in cue.split()]
        found = None
        for index in range(cursor, len(words) - len(target) + 1):
            at = words[index]["start_ms"] / 1000 - start_seconds
            if earliest_seconds <= at < latest_seconds and spoken[index:index+len(target)] == target:
                if words[index+len(target)-1]["end_ms"] / 1000 - start_seconds <= latest_seconds:
                    found = index
                    break
        if found is None:
            raise ValueError("Exercise visual cue missing or outside its question interval: " + cue)
        item["reveal_seconds"] = words[found]["start_ms"] / 1000 - start_seconds
        cursor = found + len(target)
    visual["reveals"] = reveals
    return visual


def visual_html(visual, card_id):
    if not visual: return ""
    esc = html.escape
    if visual["kind"] == "matching":
        left, right = visual["left"], visual["right"]
        row_y = lambda index: 35 + index * 65
        parts = ['<svg class="exercise-visual" viewBox="0 0 1000 260" role="img" aria-label="Matching exercise">']
        for column, x in ((left, 20), (right, 620)):
            for index, item in enumerate(column):
                parts.append(f'<text x="{x}" y="{row_y(index)}" font-size="28" fill="currentColor">{esc(item["text"])}</text>')
        for index, match in enumerate(visual["reveals"]):
            a = next(i for i, item in enumerate(left) if item["id"] == match["left_id"])
            b = next(i for i, item in enumerate(right) if item["id"] == match["right_id"])
            parts.append(f'<line id="{card_id}-visual-{index}" class="exercise-reveal" x1="380" y1="{row_y(a)-8}" x2="590" y2="{row_y(b)-8}" stroke="currentColor" stroke-width="4"/>')
        return ''.join(parts) + '</svg>'
    elif visual["kind"] == "diagram_label":
        # Fixed SVG coordinate space keeps the source image and annotation
        # positions aligned even when the panel is scaled by the renderer.
        parts = ['<svg class="exercise-visual" viewBox="0 0 1000 500" role="img" aria-label="Diagram labelling exercise">',
                 f'<image href="{esc(visual["image_path"], quote=True)}" width="1000" height="500" preserveAspectRatio="none"/>']
        # Preserve the crop aspect ratio instead of stretching it.
        width, height = visual["width"], visual["height"]
        parts[0] = f'<svg class="exercise-visual" viewBox="0 0 {width} {height}" role="img" aria-label="Diagram labelling exercise">'
        parts[1] = f'<image href="{esc(visual["image_path"], quote=True)}" width="{width}" height="{height}"/>'
        for index, label in enumerate(visual["reveals"]):
            x, y, tx, ty = label["x"]*width, label["y"]*height, label["target_x"]*width, label["target_y"]*height
            font = max(width / 1000, height / 260) * 28
            parts.append(f'<g id="{card_id}-visual-{index}" class="exercise-reveal"><line x1="{x}" y1="{y}" x2="{tx}" y2="{ty}" stroke="currentColor" stroke-width="{height*.007}"/><circle cx="{tx}" cy="{ty}" r="{height*.013}" fill="currentColor"/><text x="{x}" y="{y}" text-anchor="middle" font-size="{font}" fill="currentColor" stroke="white" stroke-width="{font*.06}" paint-order="stroke">{esc(label["text"])}</text></g>')
        return ''.join(parts) + '</svg>'
    elif visual["kind"] == "grammar_sentence":
        corrections = {item["token_index"]: (index, item)
                       for index, item in enumerate(visual["reveals"])}
        tokens = []
        for index, token in enumerate(visual["tokens"]):
            if index in corrections:
                reveal_index, item = corrections[index]
                tokens.append(f'<span class="grammar-token grammar-target"><span class="grammar-original">{esc(token)}</span><span id="{card_id}-visual-{reveal_index}" class="exercise-reveal grammar-correction">{esc(item["text"])}</span></span>')
            else:
                tokens.append(f'<span class="grammar-token">{esc(token)}</span>')
        return '<div class="exercise-visual grammar-visual" role="group" aria-label="Grammar correction">' + ' '.join(tokens) + '</div>'
    elif visual["kind"] == "table_fill":
        answers = {(item["row"], item["column"]): (index, item)
                   for index, item in enumerate(visual["reveals"])}
        head = ''.join(f'<th>{esc(value)}</th>' for value in visual["headers"])
        body = []
        for row_index, row in enumerate(visual["rows"]):
            cells = []
            for column_index, value in enumerate(row):
                answer = answers.get((row_index, column_index))
                reveal = (f'<span id="{card_id}-visual-{answer[0]}" class="exercise-reveal table-answer">{esc(answer[1]["text"])}</span>' if answer else '')
                cells.append(f'<td><span class="table-given">{esc(value)}</span>{reveal}</td>')
            body.append('<tr>' + ''.join(cells) + '</tr>')
        return '<div class="exercise-visual table-visual"><table aria-label="Table exercise"><thead><tr>' + head + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'
    elif visual["kind"] == "math_worked":
        steps = ''.join(f'<div id="{card_id}-visual-{index}" class="exercise-reveal math-visual-step">{esc(step["text"])}</div>'
                        for index, step in enumerate(visual["reveals"]))
        return f'<div class="exercise-visual math-visual" role="group" aria-label="Worked mathematics"><div class="math-expression">{esc(visual["expression"])}</div><div class="math-steps">{steps}</div></div>'
    raise ValueError("Unsupported prepared exercise visual kind")

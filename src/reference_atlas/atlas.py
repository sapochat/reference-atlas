from collections.abc import Mapping


REQUIRED_ITEM = ["target", "reference", "borrow", "do_not_copy", "build_implication", "mobile", "attribution"]
REQUIRED_ROOT = ["project", "design_read", "invariants", "hierarchy", "items"]

def validate_atlas(data: object) -> list[str]:
    if not isinstance(data, Mapping):
        return ["atlas must be an object"]

    errors: list[str] = []

    for key in ("project", "design_read"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"root field must be non-empty text: {key}")

    invariants = data.get("invariants")
    if not isinstance(invariants, list) or len(invariants) < 3:
        errors.append("invariants must contain at least three items")
    elif any(not isinstance(value, str) or not value.strip() for value in invariants):
        errors.append("invariants must contain only non-empty text")

    hierarchy = data.get("hierarchy")
    if not isinstance(hierarchy, Mapping) or not hierarchy:
        errors.append("hierarchy must be a non-empty object")
    elif any(
        not isinstance(key, str)
        or not key.strip()
        or not isinstance(value, str)
        or not value.strip()
        for key, value in hierarchy.items()
    ):
        errors.append("hierarchy keys and values must be non-empty text")

    items = data.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty list")
        return errors

    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            errors.append(f"item {index} must be an object")
            continue
        for key in REQUIRED_ITEM:
            value = item.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"item {index} field must be non-empty text: {key}")

    return errors

def render_markdown(data: object) -> str:
    errors=validate_atlas(data)
    if errors: raise ValueError("; ".join(errors))
    assert isinstance(data, Mapping)
    lines=[f"# Reference Atlas: {data['project']}","",f"**Design read:** {data['design_read']}","","## Invariants",""]
    lines += [f"- {x}" for x in data["invariants"]]
    lines += ["","## Reference hierarchy",""] + [f"- **{k}:** {v}" for k,v in data["hierarchy"].items()]
    lines += ["","## Section map","","| Target | Reference | Borrow | Do not copy | Build implication | Mobile | Attribution |","|---|---|---|---|---|---|---|"]
    for x in data["items"]:
        vals=[x[k].replace("|", "\\|") for k in REQUIRED_ITEM]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)+"\n"

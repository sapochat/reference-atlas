from collections.abc import Mapping


REQUIRED_ITEM = ["target", "reference", "borrow", "do_not_copy", "build_implication", "mobile", "attribution"]
REQUIRED_ROOT = ["project", "design_read", "invariants", "hierarchy", "items"]

def validate_atlas(data: object) -> list[str]:
    if not isinstance(data, Mapping):
        return ["atlas must be an object"]

    errors=[]
    for key in REQUIRED_ROOT:
        if not data.get(key): errors.append(f"missing root field: {key}")
    if not isinstance(data.get("invariants",[]),list) or len(data.get("invariants",[]))<3: errors.append("invariants must contain at least three items")
    if data.get("hierarchy") and not isinstance(data["hierarchy"], Mapping): errors.append("hierarchy must be an object")
    if not isinstance(data.get("items"), list):
        errors.append("items must be a list")
        return errors
    for i,item in enumerate(data.get("items",[])):
        if not isinstance(item, Mapping):
            errors.append(f"item {i} must be an object")
            continue
        for key in REQUIRED_ITEM:
            if not item.get(key): errors.append(f"item {i} missing field: {key}")
            elif not isinstance(item[key], str): errors.append(f"item {i} field must be text: {key}")
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

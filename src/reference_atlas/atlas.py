REQUIRED_ITEM = ["target", "reference", "borrow", "do_not_copy", "build_implication", "mobile", "attribution"]
REQUIRED_ROOT = ["project", "design_read", "invariants", "hierarchy", "items"]

def validate_atlas(data: dict) -> list[str]:
    errors=[]
    for key in REQUIRED_ROOT:
        if not data.get(key): errors.append(f"missing root field: {key}")
    if not isinstance(data.get("invariants",[]),list) or len(data.get("invariants",[]))<3: errors.append("invariants must contain at least three items")
    for i,item in enumerate(data.get("items",[])):
        for key in REQUIRED_ITEM:
            if not item.get(key): errors.append(f"item {i} missing field: {key}")
    return errors

def render_markdown(data: dict) -> str:
    errors=validate_atlas(data)
    if errors: raise ValueError("; ".join(errors))
    lines=[f"# Reference Atlas: {data['project']}","",f"**Design read:** {data['design_read']}","","## Invariants",""]
    lines += [f"- {x}" for x in data["invariants"]]
    lines += ["","## Reference hierarchy",""] + [f"- **{k}:** {v}" for k,v in data["hierarchy"].items()]
    lines += ["","## Section map","","| Target | Reference | Borrow | Do not copy | Build implication | Mobile | Attribution |","|---|---|---|---|---|---|---|"]
    for x in data["items"]:
        vals=[x[k].replace("|", "\\|") for k in REQUIRED_ITEM]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)+"\n"

CHECKLISTS = {
    "Company Incorporation": [
        "Articles of Association",
        "Memorandum of Association",
        "Board Resolution",
        "UBO Declaration Form",
        "Register of Members and Directors"
    ]
}

def match_uploaded_to_required(uploaded_names):
    present = set()
    for name in uploaded_names:
        lname = name.lower()
        for req in CHECKLISTS['Company Incorporation']:
            if req.lower() in lname or all(token in lname for token in req.lower().split()[:2]):
                present.add(req)
    missing = [r for r in CHECKLISTS['Company Incorporation'] if r not in present]
    return list(present), missing

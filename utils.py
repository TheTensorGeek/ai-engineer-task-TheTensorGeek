import datetime, json, os

def timestamp():
    return datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')

def write_summary(summary: dict, out_dir='outputs'):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"summary_{timestamp()}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    return path

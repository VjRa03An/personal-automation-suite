import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = "token.json"
ARCHIVE_BEFORE = (datetime.now() - timedelta(days=30)).strftime("%Y/%m/%d")
KEEP_AFTER = (datetime.now() - timedelta(days=30)).strftime("%Y/%m/%d")

LABEL_RULES = {
    "Finance": ["from:citi.com","from:info6.citi.com","from:chase.com","from:no.reply.alerts@chase.com","from:ealerts.bankofamerica.com","from:morganstanley.com"],
    "Health": ["from:sutterhealth.org","from:care.sutterhealth.org","from:message.delta.org"],
    "Job Search": ["from:careeralerts.teksystems.com","from:hi.wellfound.com","subject:right to represent","from:gilead.com"],
    "GitHub": ["from:noreply@github.com"],
    "Home": ["subject:solar panels","subject:restoration","subject:home warranty"],
    "Utilities": ["from:pge.com","from:billpay.pge.com","from:att.com","from:sling.com","from:xfinity.com"],
    "Travel": ["from:iluv.southwest.com","from:americanairlines.com","from:airbnb.com","from:booking.com","from:email.clearme.com"],
    "India": ["from:axisbank.com","from:icicibank.com","from:kvbmail.com","from:cpc.incometax.gov.in"],
}

def authenticate():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, ["https://www.googleapis.com/auth/gmail.modify"])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)

def get_or_create_label(service, name, existing):
    if name in existing:
        return existing[name]
    result = service.users().labels().create(userId="me", body={"name": name}).execute()
    print(f"  + Created label: {name}")
    return result["id"]

def get_all_ids(service, query):
    ids = []
    page_token = None
    while True:
        params = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            params["pageToken"] = page_token
        results = service.users().messages().list(**params).execute()
        ids += [m["id"] for m in results.get("messages", [])]
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return ids

def batch_modify(service, ids, add=None, remove=None):
    if not ids:
        return 0
    total = 0
    for i in range(0, len(ids), 1000):
        chunk = ids[i:i+1000]
        body = {"ids": chunk}
        if add:
            body["addLabelIds"] = add
        if remove:
            body["removeLabelIds"] = remove
        service.users().messages().batchModify(userId="me", body=body).execute()
        total += len(chunk)
    return total

def run():
    print("\n🏷️  Gmail Auto-Labeler (Batch Mode)")
    print("=" * 40)
    service = authenticate()
    existing = {l["name"]: l["id"] for l in service.users().labels().list(userId="me").execute().get("labels", [])}

    for label_name, queries in LABEL_RULES.items():
        print(f"📁 {label_name}...")
        label_id = get_or_create_label(service, label_name, existing)
        old_ids, new_ids = [], []
        for q in queries:
            old_ids += get_all_ids(service, f"{q} before:{ARCHIVE_BEFORE}")
            new_ids += get_all_ids(service, f"{q} after:{KEEP_AFTER}")
        old_ids = list(set(old_ids))
        new_ids = list(set(new_ids))
        archived = batch_modify(service, old_ids, add=[label_id], remove=["INBOX"])
        labeled = batch_modify(service, new_ids, add=[label_id])
        print(f"  ✓ In inbox: {labeled} | Archived: {archived}")

    print("\n✅ Done!")

if __name__ == "__main__":
    run()

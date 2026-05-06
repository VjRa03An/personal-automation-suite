import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = os.path.expanduser("~/Downloads/gmail-cleanup/token.json")
ARCHIVE_BEFORE = (datetime.now() - timedelta(days=30)).strftime("%Y/%m/%d")
KEEP_AFTER = (datetime.now() - timedelta(days=30)).strftime("%Y/%m/%d")

LABEL_RULES = {
    "Finance": ["from:citi.com","from:citicards.com","from:info6.citi.com","from:chase.com","from:no.reply.alerts@chase.com","from:ealerts.bankofamerica.com","from:bankofamerica.com","from:morganstanley.com","from:fisherinvestments.com"],
    "Health": ["from:sutterhealth.org","from:care.sutterhealth.org","from:delta.org","from:message.delta.org","subject:appointment","subject:prescription"],
    "Job Search": ["from:csvenky@gmail.com subject:digest","from:careeralerts.teksystems.com","from:hi.wellfound.com","subject:right to represent","from:gilead.com"],
    "GitHub": ["from:noreply@github.com","from:notifications@github.com"],
    "Home": ["subject:solar panels","subject:restoration","subject:home warranty","subject:HOA","subject:property tax"],
    "Utilities": ["from:pge.com","from:billpay.pge.com","from:sanjoseca.gov","from:att.com","from:sling.com","from:roku.com","from:emails.roku.com","from:comcast.com","from:xfinity.com"],
    "Travel": ["from:iluv.southwest.com","from:southwest.com","from:aa.com","from:americanairlines.com","from:united.com","from:airbnb.com","from:hotels.com","from:booking.com","from:expedia.com","from:email.clearme.com","subject:itinerary","subject:boarding pass","subject:flight confirmation"],
    "India": ["from:axisbank.com","from:alerts@axisbank.com","from:icicibank.com","from:custcomm.icicibank.com","from:kvbmail.com","from:canarabank.in","from:incometax.gov.in","from:cpc.incometax.gov.in","from:intimations@cpc.incometax.gov.in"],
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

def apply_to_query(service, label_id, query, archive=False):
    count = 0
    page_token = None
    while True:
        params = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            params["pageToken"] = page_token
        results = service.users().messages().list(**params).execute()
        messages = results.get("messages", [])
        for msg in messages:
            try:
                body = {"addLabelIds": [label_id]}
                if archive:
                    body["removeLabelIds"] = ["INBOX"]
                service.users().messages().modify(userId="me", id=msg["id"], body=body).execute()
                count += 1
            except Exception as e:
                print(f"    ⚠️  {e}")
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return count

def run():
    print("\n🏷️  Gmail Auto-Labeler + Archiver")
    print("=" * 40)
    service = authenticate()
    existing = {l["name"]: l["labelId"] for l in service.users().labels().list(userId="me").execute().get("labels", [])}
    total_labeled = 0
    total_archived = 0
    for label_name, queries in LABEL_RULES.items():
        print(f"📁 {label_name}...")
        label_id = get_or_create_label(service, label_name, existing)
        labeled = archived = 0
        for q in queries:
            archived += apply_to_query(service, label_id, f"{q} before:{ARCHIVE_BEFORE}", archive=True)
            labeled += apply_to_query(service, label_id, f"{q} after:{KEEP_AFTER}", archive=False)
        print(f"  ✓ Kept in inbox: {labeled} | Archived: {archived}")
        total_labeled += labeled
        total_archived += archived
    print(f"\n✅ Done! Labeled: {total_labeled} | Archived: {total_archived}")

if __name__ == "__main__":
    run()

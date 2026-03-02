"""Check what sources/references data is available on Open Targets rows."""
import json, urllib.request

OT_API = "https://api.platform.opentargets.org/api/v4/graphql"

def gql(query):
    payload = json.dumps({"query": query}).encode()
    req = urllib.request.Request(OT_API, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# Fetch 10 rows and inspect references + urls in detail
Q = """
{
  disease(efoId: "EFO_0000389") {
    knownDrugs(size: 20) {
      count
      rows {
        drug { id name }
        phase
        status
        urls { url name }
        references { ids source urls }
        mechanismOfAction
        targetId
      }
    }
  }
}
"""

result = gql(Q)
rows = result["data"]["disease"]["knownDrugs"]["rows"]

print(f"Total rows sampled: {len(rows)}\n")
for row in rows:
    refs = row.get("references", [])
    urls = row.get("urls", [])
    if refs:
        print(f"DRUG: {row['drug']['name']} | phase={row['phase']} | status={row['status']}")
        print(f"  references: {json.dumps(refs)}")
        print(f"  urls: {json.dumps(urls)}")
        print()

print("\n--- Sample rows with non-empty urls ---")
for row in rows:
    if row.get("urls"):
        print(f"  {row['drug']['name']} | {row.get('urls')}")

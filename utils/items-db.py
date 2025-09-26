import requests
import json
import re
import time
import os
from datetime import datetime, timezone

# enter RSN name or email here if you want to be kind to the API maintainers
contact_info = "email@na.com"

def get_base_json(url):
    print("Fetching base JSON from GitHub in OSRSBox Master to create item baseline.")
    try:
        response = requests.get(url)
        response.raise_for_status()
        print("Successfully fetched base JSON.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching base JSON: {e}")
        return None

def get_session():
    session = requests.Session()
    headers = {
        'User-Agent': 'OSRS-Item-DB-Updater/2.1 (https://github.com/osrsbox/osrsbox-db; contact: {contact_info})'
    }
    session.headers.update(headers)
    return session

def get_wiki_itm_tls(session):
    print("Fetching all item titles from the OSRS Wiki.")
    all_titles = set()
    api_url = "https://oldschool.runescape.wiki/api.php"
    params = {
        "action": "query", "format": "json", "list": "categorymembers",
        "cmtitle": "Category:Items", "cmlimit": "500"
    }
    last_continue = {}
    while True:
        try:
            req_params = {**params, **last_continue}
            response = session.get(url=api_url, params=req_params)
            response.raise_for_status()
            data = response.json()
            for member in data.get("query", {}).get("categorymembers", []):
                all_titles.add(member["title"])
            if "continue" in data:
                last_continue = data["continue"]
                if len(all_titles) % 2000 == 0:
                    print(f"Paginating... Identified {len(all_titles)} items by title.")
            else:
                break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching wiki titles: {e}")
            return None
    print(f"Found a total of {len(all_titles)} item titles on the Wiki.")
    return all_titles

def batch_get_wiki_data(page_titles, session):
    results = {}
    params = {
        "action": "query", "prop": "revisions", "rvprop": "content|timestamp",
        "format": "json", "titles": "|".join(page_titles)
    }
    try:
        response = session.get("https://oldschool.runescape.wiki/api.php", params=params)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        for _, page_data in pages.items():
            title = page_data.get("title")
            if title and "revisions" in page_data and page_data["revisions"]:
                revision = page_data["revisions"][0]
                content = revision.get("*")
                timestamp = revision.get("timestamp")
                if content and timestamp:
                    results[title] = {"content": content, "timestamp": timestamp}
        return results
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Could not fetch a batch of wikitext: {e}")
        return {}

def _to_int(value, default=0):
    try:
        return int(re.sub(r'[^0-9-]', '', str(value)))
    except (ValueError, TypeError):
        return default

def _to_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def parse_infobox(wikitext, item_name, last_updated_iso):
    match = re.search(r'\{\{Infobox Item\s*\|([\s\S]+?)\}\}', wikitext, re.IGNORECASE)
    if not match: return None
    content = match.group(1)
    item_data = {}
    params = re.findall(r'\|\s*([^=]+?)\s*=\s*((?:.|\n)*?)(?=\n\s*\||\n\}\})', content)

    for key, value in params:
        key = key.strip().lower()
        value = value.strip()
        value = re.sub(r'\[\[(?:[^|]+\|)?([^\]]+)\]\]', r'\1', value)
        value = re.sub(r'<[^>]+>', '', value)
        value = re.sub(r'\{\{[^}]+\}\}', '', value)
        item_data[key] = value

    try:
        item_id = int(item_data.get('id', '0'))
        if item_id == 0: return None
    except ValueError:
        return None

    # preserve original 'equipment' or 'weapon' in merge, not needed here
    return {
        'id': item_id, 'name': item_name, 'last_updated': last_updated_iso,
        'incomplete': False, 'members': item_data.get('members', 'no').lower() == 'yes',
        'tradeable': 'yes' in item_data.get('tradeable', 'yes').lower(),
        'tradeable_on_ge': 'yes' in item_data.get('tradeable', 'yes').lower(),
        'stackable': item_data.get('stackable', 'no').lower() == 'yes',
        'stacked': None, 'noted': 'yes' in item_data.get('noteable', 'no').lower(),
        'noteable': 'yes' in item_data.get('noteable', 'no').lower(),
        'linked_id_item': None, 'linked_id_noted': None, 'linked_id_placeholder': None,
        'placeholder': False, 'equipable': item_data.get('equipable', 'no').lower() == 'yes',
        'equipable_by_player': item_data.get('equipable', 'no').lower() == 'yes',
        'equipable_weapon': 'weapon' in item_data.get('slayercat', ''),
        'cost': _to_int(item_data.get('value', '0')),
        'lowalch': _to_int(item_data.get('lowalch', '0')),
        'highalch': _to_int(item_data.get('highalch', '0')),
        'weight': _to_float(item_data.get('weight', 0.0)),
        'buy_limit': _to_int(item_data.get('gemw'), default=None) if item_data.get('gemw') else None,
        'quest_item': item_data.get('quest', 'no').lower() == 'yes',
        'release_date': item_data.get('release', None),
        'examine': item_data.get('examine', ''),
        'wiki_name': item_name.replace(' ', '_'),
        'wiki_url': f"https://oldschool.runescape.wiki/w/{item_name.replace(' ', '_')}"
    }

# osrsbox db for starting point
def main():
    api_url = 'https://raw.githubusercontent.com/osrsbox/osrsbox-db/master/docs/items-complete.json'
    
    output_dir = "database"
    output_filename = os.path.join(output_dir, "items.json")
    os.makedirs(output_dir, exist_ok=True)
    
    # cut off time for any new updates to items in osrs where we can merge
    osrsbox_cutoff = datetime.fromisoformat("2021-09-30T00:00:00").replace(tzinfo=timezone.utc)

    base_data = get_base_json(api_url)
    if base_data is None: return

    name_to_id_map = {item['name']: item_id for item_id, item in base_data.items()}
    existing_item_names = set(name_to_id_map.keys())
    print(f"Loaded {len(existing_item_names)} items from the base JSON.")

    wiki_session = get_session()
    wiki_titles = get_wiki_itm_tls(wiki_session)
    if wiki_titles is None: return

    new_item_titles = sorted([t for t in (wiki_titles - existing_item_names) if '/' not in t])
    items_to_check = sorted([t for t in (wiki_titles & existing_item_names) if '/' not in t])
    
    print(f"\nFound {len(new_item_titles)} new items to add.")
    print(f"Found {len(items_to_check)} existing items to check for updates.")
    
    all_titles_to_fetch = new_item_titles + items_to_check
    if not all_titles_to_fetch:
        print("No items to process. The database is up to date.")
        return

    print("\nFetching and parsing wiki data in batches.")
    new_items_added = 0
    items_updated = 0
    batch_size = 50

    for i in range(0, len(all_titles_to_fetch), batch_size):
        batch_titles = all_titles_to_fetch[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(all_titles_to_fetch) + batch_size - 1)//batch_size}...", end='\r')
        
        wiki_data_batch = batch_get_wiki_data(batch_titles, wiki_session)
        
        for title, data in wiki_data_batch.items():
            wiki_timestamp_iso = data['timestamp']
            wiki_timestamp_dt = datetime.fromisoformat(wiki_timestamp_iso).replace(tzinfo=timezone.utc)
            
            parsed_item = parse_infobox(data['content'], title, wiki_timestamp_iso)
            if not parsed_item: continue

            item_id_str = str(parsed_item['id'])
            
            if title in new_item_titles:
                if item_id_str not in base_data:
                    base_data[item_id_str] = parsed_item
                    new_items_added += 1
            elif title in items_to_check and wiki_timestamp_dt > osrsbox_cutoff:
                if item_id_str in base_data:
                    base_data[item_id_str].update(parsed_item)
                    items_updated += 1
                else: # This can happen if an item was renamed on the wiki
                    base_data[item_id_str] = parsed_item
                    new_items_added += 1

        time.sleep(0.1)

    print(f"\n\nProcessing complete.")
    print(f"Added: {new_items_added} new items.")
    print(f"Updated: {items_updated} existing items.")

    print(f"Saving combined data to '{output_filename}'...")
    with open(output_filename, 'w', encoding='utf-8') as f:
        sorted_data = {k: v for k, v in sorted(base_data.items(), key=lambda item: int(item[0]))}
        json.dump(sorted_data, f, indent=4)

    print("Done!")

if __name__ == "__main__":
    main()
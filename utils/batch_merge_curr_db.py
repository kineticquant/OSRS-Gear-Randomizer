import requests
import json
import re
import time
import os
from datetime import datetime, timezone, timedelta
import base64

# enter RSN name or email here if you want to be kind to the API maintainers
contact_info = "email@na.com"

def load_existing_items(filepath):
    print(f"Loading existing items from '{filepath}'.")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: The file '{filepath}' was not found. Please run the initial script first.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{filepath}'.")
        return None

def get_session():
    session = requests.Session()
    headers = {
        'User-Agent': f'OSRS-Item-Delta-Updater/1.0 (contact: {contact_info})'
    }
    session.headers.update(headers)
    return session

def get_wiki_item_titles(session):
    print("Fetching all item titles from the OSRS Wiki.")
    all_titles = set()
    api_url = "https://oldschool.runescape.wiki/api.php"
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": "Category:Items",
        "cmlimit": "500"
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
        "action": "query", "prop": "revisions|pageimages", "rvprop": "content|timestamp",
        "format": "json", "titles": "|".join(page_titles), "pithumbsize": 50
    }
    try:
        response = session.get("https://oldschool.runescape.wiki/api.php", params=params)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        for _, page_data in pages.items():
            title = page_data.get("title")
            icon_url = page_data.get("thumbnail", {}).get("source")
            if title and "revisions" in page_data and page_data["revisions"]:
                revision = page_data["revisions"][0]
                content = revision.get("*")
                timestamp = revision.get("timestamp")
                if content and timestamp:
                    results[title] = {"content": content, "timestamp": timestamp, "icon_url": icon_url}
        return results
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Could not fetch a batch of wikitext: {e}")
        return {}

def _get_icon_b64(url, session):
    if not url:
        return None
    try:
        response = session.get(url)
        response.raise_for_status()
        return base64.b64encode(response.content).decode('utf-8')
    except requests.exceptions.RequestException:
        return None

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

def _parse_equipment_and_weapon(wikitext):
    equipment = {}
    weapon = {}
    
    match = re.search(r'\{\{Infobox Bonuses\s*\|([\s\S]+?)\}\}', wikitext, re.IGNORECASE)
    if not match:
        return equipment, weapon

    content = match.group(1)
    bonus_data = {}
    lines = content.split('\n|')
    for line in lines:
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        bonus_data[key.strip().lower()] = value.strip()

    stat_map = {
        'astab': 'attack_stab', 'aslash': 'attack_slash', 'acrush': 'attack_crush',
        'amagic': 'attack_magic', 'arange': 'attack_ranged', 'dstab': 'defence_stab',
        'dslash': 'defence_slash', 'dcrush': 'defence_crush', 'dmagic': 'defence_magic',
        'drange': 'defence_ranged', 'str': 'melee_strength', 'rstr': 'ranged_strength',
        'mdmg': 'magic_damage', 'prayer': 'prayer'
    }
    for wiki_key, osrsbox_key in stat_map.items():
        equipment[osrsbox_key] = _to_int(bonus_data.get(wiki_key, 0))

    slot = bonus_data.get('slot', 'not equipable').lower()
    if '2h' in slot:
        equipment['slot'] = '2h'
    else:
        equipment['slot'] = slot

    weapon['attack_speed'] = _to_int(bonus_data.get('aspeed', 0))
    weapon['weapon_type'] = bonus_data.get('wtype', 'unarmed').lower()
    
    weapon['stances'] = [] 
    
    return equipment, weapon

def parse_infobox(wikitext, item_name, last_updated_iso, icon_b64):
    match = re.search(r'\{\{Infobox Item\s*\|([\s\S]+?)\}\}', wikitext, re.IGNORECASE)
    if not match: return None
    
    content = match.group(1)
    item_data = {}

    lines = content.split('\n|')
    for line in lines:
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip().lower()
        value = value.strip()
        value = re.sub(r'\[\[(?:[^|]+\|)?([^\]]+)\]\]', r'\1', value)
        value = re.sub(r'<[^>]+>', '', value)
        value = re.sub(r'\{\{[^}]*?\}\}', '', value)
        value = value.strip()
        item_data[key] = value

    try:
        item_id = _to_int(item_data.get('id', '0'))
        if item_id == 0: return None
    except (ValueError, TypeError):
        return None

    equipment, weapon = _parse_equipment_and_weapon(wikitext)

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
        'icon': icon_b64,
        'wiki_name': item_name.replace(' ', '_'),
        'wiki_url': f"https://oldschool.runescape.wiki/w/{item_name.replace(' ', '_')}",
        'equipment': equipment,
        'weapon': weapon
    }

def main():
    input_filename = os.path.join("database", "items.json")
    
    item_database = load_existing_items(input_filename)
    if item_database is None:
        return

    session = get_session()
    
    all_wiki_titles = get_wiki_item_titles(session)
    if all_wiki_titles is None:
        return

    existing_items_map = {str(item['id']): item['name'] for item in item_database.values()}
    
    missing_item_titles = {
        title for title in all_wiki_titles 
        if title not in existing_items_map.values() and '/' not in title and '(unobtainable)' not in title.lower()
    }
    
    updates_cutoff_date = datetime.now(timezone.utc) - timedelta(days=10)
    items_to_update = set()
    for item_id, item in item_database.items():
        try:
            last_updated_str = item.get('last_updated')
            if not last_updated_str:
                items_to_update.add(item['name'])
                continue
            
            last_updated_dt = datetime.fromisoformat(last_updated_str)
            if last_updated_dt.tzinfo is None:
                last_updated_dt = last_updated_dt.replace(tzinfo=timezone.utc)

            if last_updated_dt < updates_cutoff_date:
                items_to_update.add(item['name'])
        except (ValueError, TypeError):
            items_to_update.add(item['name'])


    all_titles_to_fetch = sorted(list(missing_item_titles | items_to_update))
    
    print(f"\nFound {len(missing_item_titles)} new item titles to process for insertion.")
    print(f"Found {len(items_to_update)} existing items to check for updates.")
    
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
        
        wiki_data_batch = batch_get_wiki_data(batch_titles, session)
        
        for title, data in wiki_data_batch.items():
            wiki_timestamp_iso = data['timestamp']
            wiki_timestamp_dt = datetime.fromisoformat(wiki_timestamp_iso).replace(tzinfo=timezone.utc)
            
            icon_b64 = _get_icon_b64(data.get('icon_url'), session)
            parsed_item = parse_infobox(data['content'], title, wiki_timestamp_iso, icon_b64)
            if not parsed_item:
                continue

            item_id_str = str(parsed_item['id'])
            
            if title in missing_item_titles:
                if item_id_str not in item_database:
                    item_database[item_id_str] = parsed_item
                    new_items_added += 1
            elif title in items_to_update:
                if item_id_str in item_database:
                    should_update = False
                    local_timestamp_str = item_database[item_id_str].get('last_updated')
                    if not local_timestamp_str:
                        should_update = True
                    else:
                        try:
                            local_timestamp_dt = datetime.fromisoformat(local_timestamp_str)
                            if local_timestamp_dt.tzinfo is None:
                                local_timestamp_dt = local_timestamp_dt.replace(tzinfo=timezone.utc)
                            
                            if wiki_timestamp_dt > local_timestamp_dt:
                                should_update = True
                        except ValueError:
                            should_update = True

                    if should_update:
                        item_database[item_id_str].update(parsed_item)
                        items_updated += 1
        
        time.sleep(0.1)

    print(f"\n\nProcessing complete.")
    print(f"Added: {new_items_added} new items.")
    print(f"Updated: {items_updated} existing items.")

    print(f"Saving combined data to '{input_filename}'...")
    with open(input_filename, 'w', encoding='utf-8') as f:
        sorted_data = {k: v for k, v in sorted(item_database.items(), key=lambda item: int(item[0]))}
        json.dump(sorted_data, f, indent=4)

    print("Done!")

if __name__ == "__main__":
    main()
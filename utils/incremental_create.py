import requests
import json
import re
import time

def get_base_json(url):
    print("Fetching base JSON from GitHub.")
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
        'User-Agent': 'OSRS-Item-DB-Updater/1.0 (https://github.com/osrsbox/osrsbox-db; contact: your_username_or_email)'
    }
    session.headers.update(headers)
    return session

def get_wiki_itm_tls(session):
    print("Fetching all item titles from the OSRS Wiki...")
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
            req_params = params.copy()
            req_params.update(last_continue)
            response = session.get(url=api_url, params=req_params)
            response.raise_for_status()
            data = response.json()

            if "query" not in data or "categorymembers" not in data["query"]:
                print(f"Unexpected API response: {data}")
                break

            for member in data["query"]["categorymembers"]:
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

def get_wikitext(page_title, session):
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
        "titles": page_title
    }
    try:
        response = session.get("https://oldschool.runescape.wiki/api.php", params=params)
        response.raise_for_status()
        data = response.json()
        pages = data["query"]["pages"]
        page_id = next(iter(pages))
        if 'revisions' not in pages[page_id]:
            return None
        content = pages[page_id]["revisions"][0]["*"]
        return content
    except (KeyError, IndexError, requests.exceptions.RequestException) as e:
        print(f"Could not fetch wikitext for '{page_title}': {e}")
        return None

def _to_int(value, default=0):
    try:
        return int(re.sub(r'[^0-9]', '', str(value)))
    except (ValueError, TypeError):
        return default

def _to_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def parse_infobox(wikitext, item_name):
    match = re.search(r'\{\{Infobox Item\s*\|([\s\S]+?)\}\}', wikitext, re.IGNORECASE)
    if not match:
        return None

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
        if item_id == 0:
            return None
    except ValueError:
        print(f"Warning: Could not parse integer ID for '{item_name}'. Value was '{item_data.get('id')}'. Skipping item.")
        return None

    formatted_item = {
        'id': item_id,
        'name': item_name,
        'last_updated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'incomplete': False,
        'members': item_data.get('members', 'no').lower() == 'yes',
        'tradeable': 'yes' in item_data.get('tradeable', 'yes').lower(),
        'tradeable_on_ge': 'yes' in item_data.get('tradeable', 'yes').lower(),
        'stackable': item_data.get('stackable', 'no').lower() == 'yes',
        'stacked': None,
        'noted': 'yes' in item_data.get('noteable', 'no').lower(),
        'noteable': 'yes' in item_data.get('noteable', 'no').lower(),
        'linked_id_item': None,
        'linked_id_noted': None,
        'linked_id_placeholder': None,
        'placeholder': False,
        'equipable': item_data.get('equipable', 'no').lower() == 'yes',
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
        'wiki_url': f"https://oldschool.runescape.wiki/w/{item_name.replace(' ', '_')}",
        'equipment': {},
        'weapon': {}
    }

    return formatted_item


def main():
    api_url = 'https://raw.githubusercontent.com/osrsbox/osrsbox-db/master/docs/items-complete.json'

    base_data = get_base_json(api_url)
    if base_data is None:
        return

    existing_item_names = {item['name'] for item in base_data.values()}
    print(f"Loaded {len(existing_item_names)} items from the base JSON.")

    wiki_session = get_session()
    wiki_titles = get_wiki_itm_tls(wiki_session)
    if wiki_titles is None:
        return

    new_item_titles = sorted(list(wiki_titles - existing_item_names))
    print(f"Found {len(new_item_titles)} new items to add.")

    if not new_item_titles:
        print("Database is up to date.")
        return

    print("\nFetching and parsing new items...")
    new_items_added = 0
    for i, title in enumerate(new_item_titles):
        if '/' in title: # don't process subpages
            continue

        print(f"Processing ({i+1}/{len(new_item_titles)}): {title}", end='\r')
        wikitext = get_wikitext(title, wiki_session)
        if wikitext:
            parsed_item = parse_infobox(wikitext, title)
            if parsed_item:
                item_id = str(parsed_item['id'])
                if item_id not in base_data:
                    base_data[item_id] = parsed_item
                    new_items_added += 1
        time.sleep(0.05) # negating abusing osrs wiki

    print(f"\nSuccessfully parsed and added {new_items_added} new items.")

    output_filename = 'items-delta.json'
    print(f"Saving combined data to '{output_filename}'...")
    with open(output_filename, 'w', encoding='utf-8') as f:
        sorted_data = {k: v for k, v in sorted(base_data.items(), key=lambda item: int(item[0]))}
        json.dump(sorted_data, f, indent=4)

    print("Process complete!")

if __name__ == "__main__":
    main()
# About Project
This is just a fun web app which generates random builds by rolls/slots. It was just a quick, fun side project for me inspired by others using their own roll utilities. With theirs not being open source, I decided to make and share my own.

In developing this, I found the OSRSBox API has been offline for quite some time, likely abandoned. As such, the items list is outdated by a few years, so I've created utilities to cross-compare off their items list to get all missing items into new finalized lists (see Utils section).

Built in:

[![Python IDLE](https://img.shields.io/badge/Python%20IDLE-3776AB?logo=python&logoColor=fff)](#)
[![HTML](https://img.shields.io/badge/HTML-%23E34F26.svg?logo=html5&logoColor=white)](#)
[![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=000)](#)
	[![CSS](https://img.shields.io/badge/CSS-639?logo=css&logoColor=fff)](#)


Feel free to reference the full OSRS items list directly here:
https://raw.githubusercontent.com/kineticquant/OSRS-Gear-Randomizer/main/database/items.json


### Utils
- items-db script: Runs a batch process to get all items from the OSRS wiki and their metadata. Cross-compares the OSRSBox items JSON with the OSRS wiki, and does a full insert on any new items missing, and updates all existing items with the latest stats/metadata. Use this to build a full new list to start off of. 
- fetch_delta_singular script: Runs a large cross-compare against the OSRSBox items JSON against the OSRS wiki, and then processes item by item to add any new items directly into a JSON. Use this for quick one-off's if you have a newly-updated list already.


### To Do:
| Task                                           | Status                          | Notes                          |
|------------------------------------------------|---------------------------------|---------------------------------|
| Create utils to establish a newly-updated Items list database                     | COMPLETED ✅          
| Redirect database in source to current repo                     | COMPLETED ✅          
| Mobile Responsiveness                     | In Progress       
| Host the items list JSON as an available REST API                     | In Progress     

### How it works:
Simply set the defined number of total rolls allowed, then start clicking each individual slot to roll a random item in that slot. Get all current item stats, the most recent roll's stats, or hover over an item to see its specific stats.
<img width="600" height="550" alt="image" src="https://github.com/user-attachments/assets/5d4a4511-ce0f-4eeb-84d1-83163539cd2c" />
<img width="600" height="550" alt="image" src="https://github.com/user-attachments/assets/4b9c1fe6-0cb7-4547-b711-5ec0caaaecc2" />

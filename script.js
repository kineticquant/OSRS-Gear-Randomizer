document.addEventListener('DOMContentLoaded', () => {
    const API_URL = 'https://raw.githubusercontent.com/kineticquant/OSRS-Gear-Randomizer/main/database/items.json';
    const categorizedItems = {};
    const rollCounters = {};
    const equippedItems = {};
    let totalRolls = 0;

    const loadingMessage = document.getElementById('loading-message');
    const itemNameDisplay = document.getElementById('item-name');
    const totalRollsDisplay = document.getElementById('total-rolls-counter');
    const tooltip = document.getElementById('item-tooltip');
    
    const rollLimitInput = document.getElementById('roll-limit');
    const totalRollsLimitDisplay = document.getElementById('total-rolls-limit');

    rollLimitInput.addEventListener('input', () => {
        const limit = parseInt(rollLimitInput.value, 10) || 0;
        totalRollsLimitDisplay.textContent = limit;
    });

    const statKeys = [
        'attack_stab', 'attack_slash', 'attack_crush', 'attack_magic', 'attack_ranged',
        'defence_stab', 'defence_slash', 'defence_crush', 'defence_magic', 'defence_ranged',
        'melee_strength', 'ranged_strength', 'magic_damage', 'prayer'
    ];

    async function initialize() {
        loadingMessage.classList.remove('hidden');
        try {
            const response = await fetch(API_URL);
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            const allItems = await response.json();
            
            for (const id in allItems) {
                const item = allItems[id];
                if (item.equipable_by_player && item.equipment) {
                    const slot = item.equipment.slot;
                    if (slot && slot !== 'null') {
                        if (!categorizedItems[slot]) categorizedItems[slot] = [];
                        categorizedItems[slot].push(item);
                    }
                }
            }
            
            setupSlotListeners();
            itemNameDisplay.textContent = 'Ready! Click a slot to start.';

        } catch (error) {
            console.error("Failed to load item database:", error);
            itemNameDisplay.textContent = 'Error: Could not load item data.';
        } finally {
            loadingMessage.classList.add('hidden');
        }
    }

    function setupSlotListeners() {
        const equipmentGrid = document.querySelector('.equipment-grid');
        const slots = document.querySelectorAll('.slot');
        slots.forEach(slot => {
            const slotName = slot.dataset.slot;
            rollCounters[slotName] = 0;
            equippedItems[slotName] = null;
            
            slot.addEventListener('click', () => {
                if (categorizedItems[slotName]?.length) {
                    randomizeItem(slotName);
                } else {
                    alert(`No equippable items found for the ${slotName} slot.`);
                }
            });

            slot.addEventListener('mouseover', () => showTooltip(slot));
        });

        equipmentGrid.addEventListener('mouseleave', () => hideTooltip());
    }

    function randomizeItem(slotName) {
        const rollLimit = parseInt(rollLimitInput.value, 10);
        if (totalRolls >= rollLimit) {
            alert(`You have reached the total roll limit of ${rollLimit}.`);
            return;
        }

        const itemsForSlot = categorizedItems[slotName];
        const randomIndex = Math.floor(Math.random() * itemsForSlot.length);
        const selectedItem = itemsForSlot[randomIndex];

        if (selectedItem) {
            hideTooltip();
            
            equippedItems[slotName] = selectedItem;
            updateDisplay(selectedItem, slotName);
            
            rollCounters[slotName]++;
            document.getElementById(`${slotName}-counter`).textContent = rollCounters[slotName];

            totalRolls++;
            totalRollsDisplay.textContent = totalRolls;
            updateTotalStats();
        }
    }

    function updateDisplay(item, slotName) {
        itemNameDisplay.textContent = item.name;

        const slotElement = document.getElementById(slotName);
        const img = slotElement.querySelector('img');
        if (img) {
            img.src = `data:image/png;base64,${item.icon}`;
            img.alt = item.name;
        }

        const stats = item.equipment;
        const statMapping = {
            'astab': 'attack_stab', 'aslash': 'attack_slash', 'acrush': 'attack_crush', 'amagic': 'attack_magic', 'arange': 'attack_ranged',
            'dstab': 'defence_stab', 'dslash': 'defence_slash', 'dcrush': 'defence_crush', 'dmagic': 'defence_magic', 'drange': 'defence_ranged',
            'str': 'melee_strength', 'rstr': 'ranged_strength', 'mdmg': 'magic_damage', 'prayer': 'prayer'
        };

        for (const key in statMapping) {
            const statValue = stats[statMapping[key]] || 0;
            const element = document.getElementById(key);
            element.textContent = key === 'mdmg' ? `${statValue}%` : (statValue > 0 ? `+${statValue}` : statValue);
        }
    }

    function showTooltip(slotElement) {
        const slotName = slotElement.dataset.slot;
        const item = equippedItems[slotName];

        if (!item) {
            hideTooltip();
            return;
        }

        let tooltipContent = `<div class="tooltip-name">${item.name}</div>`;
        const stats = item.equipment;
        const statDisplayMapping = {
            'Stab Atk': 'attack_stab', 'Slash Atk': 'attack_slash', 'Crush Atk': 'attack_crush', 'Magic Atk': 'attack_magic', 'Range Atk': 'attack_ranged',
            'Stab Def': 'defence_stab', 'Slash Def': 'defence_slash', 'Crush Def': 'defence_crush', 'Magic Def': 'defence_magic', 'Range Def': 'defence_ranged',
            'Melee Str': 'melee_strength', 'Range Str': 'ranged_strength', 'Magic Dmg': 'magic_damage', 'Prayer': 'prayer'
        };
        for (const name in statDisplayMapping) {
            const key = statDisplayMapping[name];
            const value = stats[key] || 0;
            if (value !== 0) {
                const displayValue = name === 'Magic Dmg' ? `${value}%` : (value > 0 ? `+${value}` : value);
                tooltipContent += `<div class="tooltip-stat">${name}: ${displayValue}</div>`;
            }
        }
        tooltip.innerHTML = tooltipContent;
        tooltip.style.visibility = 'visible';
    }

    function hideTooltip() {
        tooltip.style.visibility = 'hidden';
    }

    function updateTotalStats() {
        const totalStats = {};
        statKeys.forEach(key => totalStats[key] = 0);

        for (const slot in equippedItems) {
            const item = equippedItems[slot];
            if (item?.equipment) {
                statKeys.forEach(key => {
                    totalStats[key] += item.equipment[key] || 0;
                });
            }
        }

        const statMapping = {
            'total-astab': 'attack_stab', 'total-aslash': 'attack_slash', 'total-acrush': 'attack_crush', 'total-amagic': 'attack_magic', 'total-arange': 'attack_ranged',
            'total-dstab': 'defence_stab', 'total-dslash': 'defence_slash', 'total-dcrush': 'defence_crush', 'total-dmagic': 'defence_magic', 'total-drange': 'defence_ranged',
            'total-str': 'melee_strength', 'total-rstr': 'ranged_strength', 'total-mdmg': 'magic_damage', 'total-prayer': 'prayer'
        };

        for (const id in statMapping) {
            const key = statMapping[id];
            const statValue = totalStats[key];
            const element = document.getElementById(id);
            element.textContent = key === 'magic_damage' ? `${statValue}%` : (statValue > 0 ? `+${statValue}` : statValue);
        }
    }

    initialize();
});
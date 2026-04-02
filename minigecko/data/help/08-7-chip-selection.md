[Back to Table of Contents](toc.md)

## 7. Chip Selection

### 7.1 Opening the Chip Selector

Before you can run most device operations, you must select the correct chip.

Ways to open the chip selector:

- Click the `Selected IC: —` control in the toolbar.
- Press `s` from the main application screen.

What happens when it opens:

- MiniGecko displays a modal selection dialog over the main interface.
- The dialog loads device names from the `minipro` database.
- Focus starts in the search input so you can type immediately.
- The status line shows how many devices are available or matched.

Why this step matters:

- The selected chip determines which operations are enabled.
- The IC information panel is populated from the selected part.
- The `IC Ops` control remains disabled until a chip is chosen.

### 7.2 Filtering and Search

The chip selector is designed to narrow a large device database quickly.

Category filters:

- `All`
- `ROM / EEPROM / Flash`
- `MCU`
- `PLD`
- `SRAM`
- `Logic`
- `NAND`
- `eMMC`
- `VGA`

Search behavior:

- Type directly into the search box to filter results live.
- Matching is case-insensitive.
- Matching is based on substring search against the device name.
- If no search text is entered, the list shows all devices in the active
	category.

Result display:

- The result list updates immediately as you type.
- The status line shows how many devices match the current filter.
- If there are many matches, MiniGecko shows only the first 200 results.
- When results are truncated, the status line indicates how many are shown
	versus how many total matches exist.

Recommended workflow:

1. Choose the broad device category first if you know it.
2. Type part of the chip name, such as a family or exact part number.
3. Review the remaining matches before confirming selection.

### 7.3 Selecting a Device

After narrowing the list, confirm the correct device from the visible results.

Ways to select a device:

- Highlight a device in the list and press `Enter`.
- Double-click the same device entry to select it immediately.

After selection:

- The chip selector closes.
- The toolbar updates from `Selected IC: —` to the chosen part name.
- The `IC Ops` control becomes active.
- The IC information panel refreshes with metadata for the selected device.
- The action log records the chip selection event.

If you cancel instead:

- The dialog closes without changing the current selection.
- `IC Ops` remains disabled if no device had been selected previously.

Best practice:

- Confirm the full part number, package variant, and relevant capabilities in
	the IC information panel before using write or erase operations.

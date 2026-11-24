[Back to Table of Contents](toc.md)

## 8. File Operations

### 8.1 Opening a File

Use the file picker to load an existing binary file into the hex panel.

Ways to open the file picker:

- Press `f` from the main screen.

File picker behavior:

- The picker opens as a modal dialog over the main interface.
- It starts in the last directory you used, or your home directory if no
	previous location has been saved.
- The current directory is shown as a navigable tree.
- Click `↑ Up a folder` at the top, or press `Backspace`, to move up to the
  parent folder. The line also shows the folder you are in.

How to choose a file:

- Select a file in the directory tree and press `Enter`.
- Double-click a file to open it immediately.
- Press `Escape` to cancel without loading anything.

After a file is opened:

- MiniGecko remembers that file's parent directory for next time.
- The application subtitle updates to include the file path.
- The action log records the opened filename and size.
- The hex panel refreshes to show the file contents.

### 8.2 Editing and Saving

A `.pld` source and any plain-text file open for editing, with line numbers.
A `.jed`, a `.chp` and data read from a chip are read-only.

While you type in the text, letter keys go into the text. Press `Escape` (or
`Tab`) to leave it, so that `f`, `s`, `d` and the other keys work again.

- `Ctrl+S` (**Save**) writes your edits back to the open file. With nothing
  changed it only says so. After a device read, which has no file yet, it
  works like Save as.
- `F12` (**Save as**) saves the loaded data, with any edits, under a name you
  pick. The new file becomes the open one; the old file stays as it was.
- `F9` (**Compile**) appears when a `.pld` is open. It saves your edits, then
  compiles the source into a `.jed` beside it and shows the new equations.
  Galette and WinCUPL both use the `.pld` suffix, so MiniGecko picks the tool
  from the file's text: a GALasm source starts with its chip alone (such as
  `GAL16V8`) and goes to Galette, which also writes a `.chp` pinout; a CUPL
  source declares `Device g22v10;` and goes to WinCUPL under Wine, which also
  writes a `.doc` with the equations, fuse plot and product-term use. If the
  compiler finds an error, the action log shows its message, and when it
  names a line the cursor moves there. The log also shows the compile
  command, which `y` copies and which runs unchanged in a terminal. CUPL
  reads ASCII only, so MiniGecko points at any other character before
  WinCUPL runs.
- `o` (**Options**) chooses which files each compiler writes besides the
  `.jed`, WinCUPL's minimisation and the Wine prefix that holds WinCUPL. By
  default WinCUPL writes the `.doc` (equations, product-term use and fuse
  plot) and Galette the `.chp` pinout. Galette's security fuse is off unless
  you turn it on: a GAL with that fuse set cannot be read or verified until
  it is erased.

Before an action would throw away unsaved edits (opening another file,
reading a chip, quitting), MiniGecko warns you. Do the same thing again to
discard the edits.

Save as workflow:

1. Press `F12`. The save dialog opens with a file name filled in: the
   chip's name after a device read (for example `AT28C64.bin`), otherwise the
   loaded file's name.
2. Pick the folder in the tree (`Enter` on a folder chooses it), and edit the
   name if you like.
3. Press `Enter` in the name box to save. If the file already exists,
   MiniGecko asks you to press `Enter` again to overwrite it.

After saving:

- The action log records the save event with the destination filename.
- The application subtitle updates to reflect the new file path.
- The saved file becomes the new active data source.

### 8.3 Data Display Limits

The hex panel renders binary data in memory and has a practical display cap.

- Files larger than 10 MB are truncated for display purposes only.
- When truncation occurs, MiniGecko shows the first 10 MB of the file in the
  hex panel and appends a notice at the end of the visible content.
- The full, unmodified file is still used as the write source for device
  operations and file save operations.
- The truncation only affects what is visible — it does not alter file contents
  or affect write accuracy.

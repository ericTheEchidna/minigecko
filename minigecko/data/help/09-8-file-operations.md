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

### 8.2 Saving to a File

`Ctrl+S` saves the loaded data to a file you name. The key appears in the
footer once data is loaded.

Preconditions:

- Data must be loaded, either from a file you opened or from a previous device
  read operation.

Workflow:

1. Press `Ctrl+S`. The save dialog opens with a file name filled in: the
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

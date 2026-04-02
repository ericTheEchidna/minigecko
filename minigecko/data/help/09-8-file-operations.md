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
- The `↑ ..` control moves up to the parent directory.

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

The write-to-file operation saves the current in-memory data to a file you
choose. It is available from the IC operations menu as `Write to file`.

Preconditions:

- Data must be loaded, either from a file you opened or from a previous device
  read operation.
- If no data is loaded, MiniGecko logs a warning and the operation does nothing.

Workflow:

1. Open the IC operations menu with `d` or by clicking `IC Ops`.
2. Click `Write to file`.
3. The file picker opens. Navigate to the target directory and select a
   destination path.
4. Confirm with `Enter`.

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

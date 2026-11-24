[Back to Table of Contents](toc.md)

## Appendix B: minipro Options

MiniGecko runs the `minipro` command-line program for every chip operation.
The action log shows each command as a line that starts with `$`. Press `y`
to copy the last command, then paste it into a terminal. It does the same
thing there. Add any option from this page to do what MiniGecko does not offer.

Opening a `.jed` file also logs the MAME `jedutil` command that turns its
fuse map into the equations on the Data tab, such as
`jedutil -view counter.jed GAL16V8`. A `.jed` that minipro read from a chip
lacks the closing `*` on its last field, and jedutil refuses it as it stands.
MiniGecko gives jedutil a fixed copy, and the log says so under the command.

This page covers minipro 0.7.4, commit `fd6b56a` (2026-03-09). The source is
minipro's `src/main.c` and its manual page (`man minipro`). Every option takes
a short form, a long form, or both.

**MiniGecko** says which operation uses the option. A dash means MiniGecko
never sends it.

| Option | What it does | When to use it, and the risk | MiniGecko |
|---|---|---|---|
| **Choosing the chip and the programmer** | | | |
| `-p`, `--device <name>` | Names the chip, as listed by `-l` (for example `AT28C256` or `GAL16V8@DIP20`). | Every chip operation needs it. Quote a name that holds spaces or brackets. | Every chip operation |
| `-q`, `--programmer <model>` | Lists the chips of another programmer model: TL866A, TL866II, T48, T56 or T76. | To see what another programmer supports. It only changes listing. | — |
| `-i`, `--icsp_vcc` | Programs the chip in its circuit, through the ICSP header. The programmer supplies the chip's VCC. | For a microcontroller soldered on a board that is not powered. Not on the TL866CS. | — |
| `-I`, `--icsp_no_vcc` | Programs through the ICSP header, and the programmer does not supply VCC. | For a board that has its own power. Not on the TL866CS. | — |
| `-c`, `--page <type>` | Picks one memory area: `code`, `data`, `config`, `user` or `calibration`. | For microcontrollers with EEPROM or fuses. Without `-c`, a read saves code, data and config to separate files, and a write uses `code`. | — |
| **Reading and writing** | | | |
| `-r`, `--read <file>` | Reads the chip into the file. | To copy a chip. A GAL or PLD reads as a `.jed` fuse map. | Read, Compare, and Erase with "read after" |
| `-w`, `--write <file>` | Erases the chip, writes the file to it, then reads it back to check it. | To program a chip. Everything already on the chip is lost. | Write |
| `-m`, `--verify <file>` | Compares the chip with the file, without changing the chip. | To check a chip you programmed before. | — |
| `-f`, `--format <type>` | Reads or writes Intel HEX (`ihex`) or Motorola S-record (`srec`) files instead of raw binary. | For files from an assembler or compiler. A GAL always uses JEDEC (`.jed`), so it needs no `-f`. | — |
| `-e`, `--skip_erase` | Writes without erasing first. | Only on a chip you know is blank. Writing can change a bit from 1 to 0 but not back, so on a used chip the result is wrong. | — |
| `-v`, `--skip_verify` | Writes without reading the chip back to check it. | Only to save time. A bad write goes unnoticed. | Write, when you turn verify off |
| `-s`, `--no_size_error` | Writes a file whose size does not match the chip, with a warning only. | For a file smaller than the chip, such as a 16 KB image on a 32 KB EEPROM. | — |
| `-S`, `--no_size_warning` | Same as `-s`, without the warning. | As `-s`. Do not use it with `-s`. | — |
| **Checking and erasing** | | | |
| `-b`, `--blank_check` | Checks that the chip is erased: every byte reads 0xFF, or every GAL fuse reads 1. | Before writing a chip you are not sure about. It does not check pin contact: an empty socket reads blank. | Blank check (after `-z`) |
| `-E`, `--erase` | Erases the chip and does nothing else. | To clear a chip. Everything on it is lost. minipro refuses a chip it cannot erase ("This chip can't be erased!"), such as a UV EPROM. | Erase |
| `-z`, `--pin_check` | Checks that every pin touches the socket, and names any pin that does not. | When a chip gives odd results. Supply pins are not tested. | Pin check, and the first step of Blank check |
| `-T`, `--logic_test` | Tests a logic chip (such as a 74LS00) or a static RAM against its truth table. A wrong pin shows a minus sign. | To find a dead logic chip or RAM. | RAM/logic test |
| `-D`, `--read_id` | Reads only the chip's ID, nothing else. | To check which chip is in the socket, or that a chip is there at all. | — |
| `-x`, `--skip_id` | Does not read the chip ID at all. Read mode only. | For a chip whose ID read fails, or a clone with no ID. | — |
| `-y`, `--no_id_error` | Goes on when the chip ID does not match the chip named in `-p`. minipro still prints a warning. | For clones and second sources that report another maker's ID. With the wrong `-p`, a write can use the wrong voltages. | Read, Write, Erase, Blank check |
| **Lock and protection** | | | |
| `-u`, `--unprotect` | Turns the chip's write protection off before writing. | When minipro says "This chip may be write-protected. Use -u and try again." | — |
| `-P`, `--protect` | Turns write protection on after writing. On a GAL it writes the security fuse: the GAL datasheets say the fuse map then cannot be read or verified until the chip is erased. On other chips it works only where minipro supports it; those print "Use -P if you want to write-protect this chip." when you write without it. A protected chip may need `-u` before the next write. | Only when the chip must not be copied or changed. It is **not** "skip verify"; that is `-v`. | — |
| `--fuses` | With `-c config`, reads or writes only the fuse bytes. Setting it also sets `-c config`. | For microcontroller fuses alone. Not in the manual page. | — |
| `--uid` | With `-c config`, reads or writes only the user ID bytes. Setting it also sets `-c config`. | For the user ID alone. Not in the manual page. | — |
| `--lock` | With `-c config`, reads or writes only the lock bits. Setting it also sets `-c config`. | For the lock bits alone. Lock bits can stop the chip being read. Not in the manual page. | — |
| **Voltages and timing (`-o`)** | | | |
| `-o <name>=<value>` | Sets one of the values below. Give `-o` once per value, for example `-o vpp=12 -o vcc=5`. | Each value also has its own long form, such as `--vpp=12`. | — |
| `--vpp <volts>` | Sets the programming voltage. TL866II+: 9 to 18 V in steps; T48, T56, T76 also 21 and 25 V. | Only when the datasheet asks for a voltage the database does not use. Too high a voltage destroys the chip. | — |
| `--vdd <volts>` | Sets the supply voltage while writing: 3.3, 4, 4.5, 5, 5.5 or 6.5 V. | As the datasheet says. Above the chip's maximum damages it. | — |
| `--vcc <volts>` | Sets the supply voltage while verifying (3.3 to 6.5 V), or for a logic test (1.8, 2.5, 3.3 or 5 V). | To test a 3.3 V chip at 3.3 V. Above the chip's maximum damages it. | — |
| `--pulse <µs>` | Sets the programming pulse length, 0 to 65535 microseconds. | For an old EPROM whose datasheet asks for another pulse. Too long can overheat the chip. | — |
| `--spi_clock <MHz>` | Sets the SPI clock for serial flash. T48: 4, 8, 15, 30. T56: 8, 16, 25, 50. T76: more steps. | Slow it down for long wires or an unreliable read. | — |
| `--address <hex>` | Sets the I2C address of a 24Cxx EEPROM, such as 0xA0. T76 only. | For a 24Cxx chip whose address pins are not all tied low. | — |
| **Finding chips** | | | |
| `-l`, `--list` | Lists every chip the programmer supports. | To find the exact name for `-p`. | — |
| `-L`, `--search <text>` | Lists the chips whose name holds the text, such as `-L 28C64`. | Faster than `-l` when you know part of the name. | — |
| `-d`, `--get_info <name>` | Shows one chip's details: package, memory size, ID, voltages. | To check a chip before programming it. | — |
| `-a`, `--auto_detect <pins>` | Finds a 25xx SPI flash chip by its ID. The value is 8 or 16, its pin count. | For an SPI flash with a worn marking. | — |
| **The programmer itself** | | | |
| `-k`, `--presence_check` | Says which programmer is connected. | To check the USB connection. | — |
| `-Q`, `--query_supported` | Lists the programmer models minipro supports. | — | — |
| `-V`, `--version` | Shows minipro's version, and the programmer and firmware when one is connected. | To report a bug. | Start-up: finds the programmer |
| `-t`, `--hardware_check` | Tests the programmer itself: its VPP, VCC and GND pin drivers and its overcurrent protection. It drives voltages onto socket pins, so keep the socket empty. | When the programmer itself seems faulty. | — |
| `-F`, `--update <file>` | Writes new firmware to the programmer. | Only with firmware made for your model. See "UPDATING FIRMWARE" in `man minipro` first. | — |
| **Custom data files** | | | |
| `--infoic <file>` | Uses another chip database instead of the installed `infoic.xml`. | To try a chip definition you edited. | — |
| `--logicic <file>` | Uses another logic test database instead of `logicic.xml`. | To add a test for a logic chip. | — |
| `--logicic_out <file>` | Saves the result of a logic test (`-T`) to a file. | To keep a record of the test. | — |
| `--algorithms <file>` | Uses another programming algorithm file (T56 and T76). | Only for testing algorithms. | — |
| `-h`, `--help` | Prints a short usage line and stops. In 0.7.4 it points to `man minipro`. | — | — |

[Back to Table of Contents](toc.md)

## 13. Glossary

**Blank check**
A test that reads every byte of a device and confirms each one is `0xFF`,
the erased state for most Flash and EEPROM devices. A device that passes
blank check is ready to program.

**DIP (Dual Inline Package)**
A common IC package format with two parallel rows of through-hole pins.
Most EPROMs and EEPROMs targeted by `minipro` use DIP packages.

**EEPROM (Electrically Erasable Programmable Read-Only Memory)**
A non-volatile memory type that can be erased and rewritten electrically,
typically byte by byte or page by page without a separate erase step.

**EPROM (Erasable Programmable Read-Only Memory)**
An older non-volatile memory type programmed electrically but erased by
exposure to ultraviolet light (UV EPROM). Erase requires a UV lamp; the
programmer hardware cannot erase these devices.

**Flash**
A type of EEPROM that is erased and written in blocks or sectors rather
than byte by byte. Common in embedded systems and modern storage devices.

**ISP (In-System Programming)**
The ability to program a device while it remains installed in a circuit,
using a programming header rather than removing and socketing the chip.
The IC information panel indicates ISP support for applicable devices.

**OTP (One-Time Programmable)**
A device that can be programmed once and cannot be erased. Treat OTP
writes as permanent and verify carefully before committing data.

**PLD (Programmable Logic Device)**
A category of configurable logic ICs, including PALs, GALs, and CPLDs.
`minipro` supports programming and reading a range of PLD families.

**SRAM (Static Random-Access Memory)**
A volatile memory device that retains data only while powered. `minipro`
can run functional test vectors against SRAM to verify correct operation.

**VCC**
The positive supply voltage pin of a device. The IC information panel may
report the default VCC voltage for the selected chip.

**VPP (Programming Voltage)**
An elevated supply voltage applied to certain devices during programming
or erase operations. The programmer hardware manages VPP automatically;
MiniGecko and `minipro` handle the sequencing transparently.

**Verify**
A post-write step that reads the device back and compares it byte-by-byte
against the source file. MiniGecko enables `Verify after write` by
default. A failed verify indicates that the write did not complete
correctly.

**ZIF (Zero Insertion Force) socket**
The lever-operated socket on the programmer that holds the target IC
during operations. Opening the lever releases the chip with minimal
force. A fully closed lever is required for reliable contact.

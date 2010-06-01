mid2cnc - a MIDI to CNC G-code converter

This script reads in a standard or General MIDI file and calculates the feedrates and vectors that will yield the correct note frequencies (up to 3-note polyphony) on a CNC mill's axis motors.

Usage:
Set desired input/output file name, machine limits, and steps per inch (steps per rotation * leadscrew threads per inch) in mid2cnc.py. 200 steps per rotation and 6 or 10 threads per inch are probably the most common configurations. If in doubt, check the manual and/or your build logs.

Choose which MIDI channels to import

Ensure your machine is configured to the same steps per inch as the script.

If your machine controller performs smooth acceleration for linear moves, turn this off (set acceleration to infinity or other suitably large number)

* * * * * * * * *
WARNING: Limits are checked only between notes. Typical songs have at least one MIDI event regularly enough that this is not a problem, however it is possible for a single, uninterrupted note/chord to exceed the limits/safety and crash your machine. Doublecheck the ACTUAL output (X,Y,Z) and that your limit switches are in good working order.

WARNING: You use this program at your own risk. There may be bugs, errors, poor documentation leading to user error, and any other factors that could cause undesirable operation of your machine or damage to your machine. You should inspect the input and output files carefully to ensure the resulting file does not exceed the limits of your mill. Remember, your mill is designed for milling and not playing music, and the motions necessary to produce wicked tunes with it (e.g. infinite acceleration / rapid changes of direction) are probably not good for your machine in the long run.
* * * * * * * * *

Now that that is out of the way...

This is written for 3 axis, XYZ machines. If the input MIDI specifies more than 3 notes played simultaneously, three will be chosen arbitrarily. The results may not sound good. For best results, pick off unwanted notes in a MIDI editor before exporting. In a pinch, you can ignore entire tracks/instruments by removing them from the list at the start of the script.

Remember, MIDI stores music as a sequence of events, in the form of the event codes themselves and the delta time since the last event. This script computes chords/vectors as they exist at each unique delta time. Such events include minor or useless (to you) stuff such as changes to key pressure, lyrics display, tempo shifts, and drums / other events on ignored channels. Thus, any time ANY new channel event occurs (splitting up the event deltas), the motion vector gets split up too, resulting in a new line of gcode, an unpleasant pause of the machine between these lines, and possible frequency inaccuracies for short moves. Even if none of the notes being played have actually changed. So it is in your best interest to remove the drum tracks and any other unwanted/unplayable notes in a MIDI editor before converting. Ignoring the channel is not the same as removing the drums outright, since they will still be in the file and splitting up the deltas for notes you want.

If you have a fancy machine with pneumatic tool change or clickable relays for functions which can be controlled via gcode, you *could* implement the percussion as well. This is left as an exercise to the reader, but look at the first loop at the top of the file, which builds the table of 'interesting' events from the MIDI parser, and the second loop which goes through this list chronologically and determines which notes are active at each new delta.

Some notes / things I have discovered:
About half of all MIDIs pulled off the internets (published 1997, or whenever) are broken (bytes identifying the length of structures in the file don't match the actual structure lengths), causing the parser to crash with an error about a subscript out of range. Try opening in a good MIDI editor and re-saving. (While you're in there, delete those drum tracks as well...)

MIDIs for popular songs pulled from the Internet very often set or clear the same note multiple times in a row - possibly due to mistrust of the controller, or more likely (for multiple note-on) changes to key pressure. mid2cnc will warn about this, since it seems like an error (e.g. "tried to turn off note that wasn't on!"), but if the results sound OK you can safely ignore them.

This script currently only supports regular MIDI timing, not absolute / SMPTE / etc. These are indicated with a negative(!) tempo. I haven't found any files that use these yet, so I don't know what happens if one is encountered. Expect bad things to happen.

In addition to turning off notes using the appropriately-named Note Off command, some MIDI controllers turn off by sending a duplicate Note On command with the volume set to 0. Both methods are valid according to the MIDI specs(?), and will have the desired effect in mid2cnc.py.

G-Code is not universally standardized; different controllers support slightly different dialects. It should work on most well-known controller software such as EMC2 and TurboCNC. This program assumes:
* Machine pauses (G04 Pxxxx) are in seconds or fractions thereof (some controllers might use milliseconds)
* Comments are specified between ( and )
* Ten decimal places' precision for numeric values
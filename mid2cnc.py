# mid2cnc.py, a MIDI to CNC g-code converter
# by T. R. Gipson <drmn4ea at google mail>
# http://tim.cexx.org/?p=633
# Hacked by Miles Lightwood of TeamTeamUSA to support the MakerBot Cupcake CNC - m@teamteamusa.com
# Released under the GNU General Public License

# Includes midiparser.py module by Sean D. Spencer
# http://seandon4.tripod.com/
# This module is public domain.

# Usage:
# python ./mid2cnc.py midifile gcodefile ppi
# Example:
# python ./mid2cnc.py ../man_on_the_silver_mountain/man_on_the_silver_mountain.mid ../man_on_the_silver_mountain/man_on_the_silver_mountain.gcode 600

import sys
import midiparser
import math

imported_channels=[0,1,2,3,4,5,6,7,8,9,11,12,13,14,15]  # List of MIDI channels (instruments) to import.
                                                        # Channel 10 is percussion, so you probably want to omit it.

is_cupcake = 'yes' # if set to 'yes' you can ignore the rest of the variables

machine_ppi = 2000  # Set equal to your machine's Steps Per Inch (steps per rotation * threads per inch)

machine_limit_x = 12 # Working envelope of your machine, in inches. This script assumes your machine's origin at (0,0,0)
machine_limit_y = 6 
machine_limit_z = 1 
machine_safety = 0.2  # Safety margin between when moves reverse direction and your machine's limits. You do have limit switches, right? ;-)
num_axes = 3

suppress_comments = 0 # Set to 1 if your machine controller does not handle ( comments )

#tempo=None # should be set by your MIDI...
tempo=138 # should be set by your MIDI...

metric = 'yes' # set to 'no' for Imperial units

def main(argv):
	
    x=0.0
    y=0.0
    z=0.0

    x_dir=1.0;
    y_dir=1.0;
    z_dir=1.0;

    if is_cupcake == 'yes':
        num_axes = 1 # for Cupcakes it should be 1; all others should be 3
        machine_ppi = float(argv[3])  # Higher numbers make the pitch lower and the song slower; 600 is a good starting place for Cupcakes
        machine_limit_x = 3.93 # 
        machine_limit_y = 3.93 # 
        machine_limit_z = 1 # 
		
    midifile = argv[1]
    outfile = argv[2]

    FILE = open(outfile,"w")

    #midi = midiparser.File(argv[1])
    midi = midiparser.File(midifile)
    
    print midi.file, midi.format, midi.num_tracks, midi.division

    noteEventList=[]

    for track in midi.tracks:
        for event in track.events:
            if event.type == midiparser.meta.SetTempo:
                tempo=event.detail.tempo
                print "Tempo change: " + str(event.detail.tempo)
            if ((event.type == midiparser.voice.NoteOn) and (event.channel in imported_channels)): # filter undesired instruments
                #print event.absolute, 
                #print event.detail.note_no, event.detail.velocity
                # NB: looks like some use "note on (vel 0)" as equivalent to note off, so check for vel=0 here and treat it as a note-off.
                if event.detail.velocity > 0:
                    noteEventList.append([event.absolute, 1, event.detail.note_no, event.detail.velocity])
                else:
                    noteEventList.append([event.absolute, 0, event.detail.note_no, event.detail.velocity])
            if (event.type == midiparser.voice.NoteOff) and (event.channel in imported_channels):
                #print event.absolute, 
                #print event.detail.note_no, event.detail.velocity
                noteEventList.append([event.absolute, 0, event.detail.note_no, event.detail.velocity])
            if event.type == midiparser.meta.TrackName: 
                print event.detail.text.strip()
            if event.type == midiparser.meta.CuePoint: 
                print event.detail.text.strip()
            if event.type == midiparser.meta.Lyric: 
                print event.detail.text.strip()
                #if event.type == midiparser.meta.KeySignature: 
                # ...

    # We now have entire file's notes with abs time from all channels
    # We don't care which channel/voice is which, but we do care about having all the notes in order
    # so sort event list by abstime to dechannelify

    noteEventList.sort()
    #print noteEventList

    print len(noteEventList)
    last_time=-0
    active_notes={} # make this a dict so we can add and remove notes by name

    # Start the file...
    # It would be nice to add some metadata here, such as who/what generated the output, what the input file was,
    # and important playback parameters (such as steps/in assumed and machine envelope).
    # Unfortunately G-code comments are not 100% standardized...

    if suppress_comments == 0:
        FILE.write ("( File created with mid2cnc.py - http://tim.cexx.org/?p=633 )\n")
        FILE.write ("( Hacked by Miles Lightwood of TeamTeamUSA to support the MakerBot Cupcake CNC - m at teamteamusa dot com )\n")
        FILE.write ("( Input file was " + midifile + " )\n")

        FILE.write ("( Steps per inch: " + str(machine_ppi) + " )\n")    
        FILE.write ("( Machine envelope: )\n")
        FILE.write ("( x = " + str(machine_limit_x) + " )\n")
        FILE.write ("( y = " + str(machine_limit_y) + " )\n")
        FILE.write ("( z = " + str(machine_limit_z) + " )\n")

    if metric == 'yes':
        FILE.write ("G21\n")            # Set units to Metric
    else:
        FILE.write ("G20\n")            # Set units to Imperial

    if is_cupcake == 'yes':
        FILE.write ("G90\n")            # Set movements relative
	
    FILE.write("G00 X0 Y0 Z0\n")    # Home


    # General description of what follows: going through the chronologically-sorted list of note events, (in big outer loop) adding
    # or removing them from a running list of active notes (active_notes{}). Generally all the notes of a chord will turn on at the
    # same time, so nothing further needs to be done. If the delta time changes since the last note, though, we know how long the
    # last chord should play for, so dump out the running list as a linear move and continue collecting note events until the next
    # delta change...

    for note in noteEventList:
        #print note # [event.absolute, 0, event.detail.note_no, event.detail.velocity]
        if last_time < note[0]:
            # New time, so dump out current noteset for the time between last_time and the present, BEFORE processing new updates.
            # Whatever changes at this time (delta=0) will be handled when the next new time (nonzero delta) appears.
            
            freq_xyz=[0,0,0]
            feed_xyz=[0,0,0]
            distance_xyz=[0,0,0]

            for i in range(0, min(len(active_notes.values()), num_axes)): # number of axes for which to build notes
                # If there are more notes than axes, use the highest of the available notes, since they seem to sound the best
                # (lowest frequencies just tend to sound like growling and not musical at all)
                nownote=sorted(active_notes.values(), reverse=True)[i]
                freq_xyz[i] = pow(2.0, (nownote-69)/12.0)*440.0 # convert note numbers to frequency for each axis in Hz
                feed_xyz[i] = freq_xyz[i] * 60.0 / machine_ppi    # feedrate in IPM for each axis individually
                distance_xyz[i] =  feed_xyz[i] * (((note[0]-last_time)+0.0)/(midi.division+0.0)) * (tempo/60000000.0)   #distance in inches for each axis 
                # Also- what on earth were they smoking when they made precision of a math operation's output dependent on its undeclared-types value at any given moment?
                # (adding 0.0 to numbers above forces operations involving them to be computed with floating-point precision in case the number they contain happens to be an integer once in a while)

            print "Chord: [%.3f, %.3f, %.3f] for %d deltas" % (freq_xyz[0], freq_xyz[0], freq_xyz[0], (note[0] - last_time))

            # So, we now know the frequencies assigned to each axis and how long to play them, thus the distance.
            # So write it out as a linear move...

            # Feedrate from frequency: f*60/machine_ppi
            # Distance (move length): feedrate/60 (seconds); feedrate/60000 (ms)

            # And for the combined (multi-axis) feedrate... arbitrarily select one note as the reference, and the ratio of the
            # final (unknown) feedrate to the reference feedrate should equal the ratio of the 3D vector length (known) to the
            # reference length (known). That sounds too easy.

            # First, an ugly bit of logic to reverse directions if approaching the machine's limits

            x = x + (distance_xyz[0] * x_dir)
            if x > (machine_limit_x-machine_safety):
                x_dir = -1
            if x < machine_safety:
                x_dir = 1

            y = y + (distance_xyz[1] * y_dir)
            if y > (machine_limit_y-machine_safety):
                y_dir = -1
            if y < machine_safety:
                y_dir = 1
                
            z = z + (distance_xyz[2] * z_dir)
            if z > (machine_limit_z-machine_safety):
                z_dir = -1
            if z < machine_safety:
                z_dir = 1
                
            if distance_xyz[0] > 0: # handle 'rests' in addition to notes. How standard is this pause gcode, anyway?
                vector_length = math.sqrt(distance_xyz[0]**2 + distance_xyz[1]**2 + distance_xyz[2]**2)
                combined_feedrate = (vector_length / distance_xyz[0]) * feed_xyz[0]
                if is_cupcake == 'yes': # flip x and z so that all movement is in z
                    FILE.write("G01 X%.10f Y%.10f Z%.10f F%.10f\n" % (z, y, x, combined_feedrate))
                else:
                    FILE.write("G01 X%.10f Y%.10f Z%.10f F%.10f\n" % (x, y, z, combined_feedrate))
            else:
                temp = int((((note[0]-last_time)+0.0)/(midi.division+0.0)) * (tempo/1000.0))
                FILE.write("G04 P%0.4f\n" % (temp/1000.0))

            # finally, set this absolute time as the new starting time
            last_time = note[0]


        if note[1]==1: # Note on
            if active_notes.has_key(note[2]):
                print "Warning: tried to turn on note already on!"
            else:
                active_notes[note[2]]=note[2] # key and value are the same, but we don't really care.
        elif note[1]==0: # Note off
            if(active_notes.has_key(note[2])):
                active_notes.pop(note[2])
            else:
                print "Warning: tried to turn off note that wasn't on!"

    
if __name__ == "__main__":
    main(sys.argv)

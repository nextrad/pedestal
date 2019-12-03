NeXtRAD Antenna Mount/Pedestal Controller
---

Requires Python3 with pyserial


    usage: pedestal.py

    Monitor and control of a NeXtRAD antenna

    optional arguments:
      -h, --help   show this help message and exit
      -d, --debug  display debug messages to STDOUT
      -c, --cli    launch command-line interface
Command-Line Interface

    sudo python3 pedestal.py -c


    Pedestal Startup Sequence
    -------------------------
    1) Power on the pedestal
    2) After remote has initialised, enter A-Z mode.
    3) Use the remote to point antennas at reference point.
    4) Power off the pedestal.
    5) Repeat steps 1 and 2.


    NB: If the pedestal is switched off this process will need to be repeated


    press "y" if these operations have been performed (y/N)?
    y
    >>> Connection Established


    Pedestal Control System
    -----------------------
    1 - Check Connection
    2 - Get Position
    3 - Set Position
    q - Quit


    choose a selection

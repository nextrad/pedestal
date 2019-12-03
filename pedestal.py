# Name:         pedestal.property
# Description:  python program to control an antenna pedestal
# Author:       Brad Kahn based off the work of Stuart Hadfield and David Bussett

import argparse
import configparser
import serial
import sys
import os
import logging
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

class Pedestal(object):
    """
    Monitor and control of a NeXtRAD antenna.
    Supported hardware: mount - ORION Atlas Pro AZ/EQ-G GoTo.
                        hand controller - ORION SynScan V4.
    """
    def __init__(self, device='/dev/ttyUSB0', baud=9600, timeout=1, control_file=None):
        self.azimuth = float()
        self.elevation = float()
        self.DEVICE = device
        self.BAUD = baud
        self.TIMEOUT = timeout
        self.control_file = control_file

        # for future use
        self.AZIMUTH_DIFFERENCE = 0
        self.ELEVATION_DIFFERENCE = 0

    def connect(self):
        '''set up a serial connection to pedestal'''
        logger.debug("[DEBUG] Establishing serial connections using params: port={}, baudrate={}, timeout={}".format(self.DEVICE, self.BAUD, self.TIMEOUT))
        self.ser = serial.Serial(port=self.DEVICE, baudrate=self.BAUD, timeout=self.TIMEOUT)

    def check_connection(self):
        logger.debug("[DEBUG] Checking Connection...")
        strReadRemoteCommand = "Kx"
        self.ser.write(str.encode(strReadRemoteCommand))
        strRemoteControlText = self.ser.read_until(terminator='#')
        if not (strRemoteControlText):
            raise Exception("Error code 1: serial port timed out while doing initial config for pedestal.")

    def stop_slew(self):
        self.ser.write(str.encode('M'))

    def get_position(self):
        '''Returns a tuple containing (azimuth, elevation) of the current position'''
        self.ser.write(str.encode('Z'))
        azm_alt = self.ser.read_until(terminator='#')
        logger.debug("[DEBUG] Hex azm, elev: " + str(azm_alt[0:4]) + ', ' + str(azm_alt[5:9]))
        Azimuth_Deg = int(azm_alt[0:4],16)*360.0/65536.0
        Elevation_Deg = int(azm_alt[5:9],16)*360.0/65536.0
        logger.debug("[DEBUG] azm, elev: " + str(Azimuth_Deg) + ', ' + str(Elevation_Deg))
        self.azimuth, self.elevation = Azimuth_Deg, Elevation_Deg
        return self.azimuth, self.elevation

    def set_position(self, Azimuth_Deg, Elevation_Deg):
        Overshoot_Flag = 0

        #Azimuth
        if(abs(Azimuth_Deg) >= 360.0):
            raise Exception("Error: Specified azimuth not in range (-360, 360).")
        #Adjust for calibration offset
        Azimuth_Deg -= self.AZIMUTH_DIFFERENCE
        #Format to [0, 360) degrees
        if(Azimuth_Deg < 0.0):
            Azimuth_Deg += 360

        #Elevation
        if(abs(Elevation_Deg) > 90):
            raise Exception("Error: Specified elevation not in range[-90, 90].")
        #Adjust for calibration offset
        Elevation_Deg -= self.ELEVATION_DIFFERENCE
        #Format to [0, 360) degrees
        if(Elevation_Deg < 0.0):
            Elevation_Deg += 360 #abs(Elevation_Deg)

        # TODO: compensation flags for overshooting and undershooting
        # self.azimuth, self.elevation = self.get_position() # using this causes an offset of ~0.7deg when returning to (0,0)
        self.azimuth, self.elevation = 0, 0
        logger.debug("[DEBUG] Antenna current direction ({}, {})".format(self.azimuth, self.elevation))

        #Set flags to compensate for overshooting or undershooting
        #Azimuth
        logger.debug("[DEBUG] Difference between desired and actual azimuth: {}".format(self.azimuth - Azimuth_Deg))
        logger.debug("[DEBUG] Desired azimuth: {}".format(Azimuth_Deg))
        logger.debug("[DEBUG] Actual azimuth: {}".format(self.azimuth))
        if(self.azimuth - Azimuth_Deg <= 0):
            Azimuth_Hex = (int)(Azimuth_Deg*65536.0/360)
        elif(self.azimuth - Azimuth_Deg > 45.0/60.0):
            Azimuth_Hex = (int)((Azimuth_Deg + 45.0/60.0)*65536.0/360)
        else:
            Azimuth_Hex = (int)(Azimuth_Deg*65536.0/360)
            Overshoot_Flag += 1

        #Elevation
        logger.debug("[DEBUG] Difference between desired and actual elevation: {}".format(self.elevation - Elevation_Deg))
        logger.debug("[DEBUG] Desired elevation: {}".format(Elevation_Deg))
        logger.debug("[DEBUG] Actual elevation: {}".format(self.elevation))
        if(self.elevation - Elevation_Deg <= 0):
            Elevation_Hex = (int)(Elevation_Deg*65536.0/360)
        elif(self.elevation - Elevation_Deg > 45.0/60):
            Elevation_Hex = (int)((Elevation_Deg)*65536.0/360)
        else:
            Elevation_Hex = (int)(Elevation_Deg*65536.0/360)
            Overshoot_Flag += 1

        logger.debug(Azimuth_Hex)
        logger.debug(Elevation_Hex)

        #Send 'Goto' Command
        command = "B%04X,%04X"% (Azimuth_Hex, Elevation_Hex)
        logger.debug("[DEBUG] Command for Azimuth and Elevation: " + command)
        self.ser.write(str.encode(command))

        response = self.ser.read_until(terminator='#')
        logger.debug(response)

        if (response[0] == '0'):
            raise Exception("Error: Specified heading out of range.", Azimuth_Deg, " ", Elevation_Deg)
        if(Overshoot_Flag > 0):
            loadAzmAlt(Azimuth_Deg,Elevation_Deg)

    def init_file_watchdog_thread(self):
        if self.control_file is not None:
            watched_dir = os.path.split(self.control_file)[0]  # os.path.split() returns tuple (path, filename)
            print('watched_dir = {watched_dir}'.format(watched_dir=watched_dir))
            patterns = [self.control_file]
            print('patterns = {patterns}'.format(patterns=', '.join(patterns)))
            self.event_handler = FileEventHandler(patterns=patterns)
            self.observer = Observer()
            self.observer.schedule(self.event_handler, watched_dir, recursive=False)
            self.observer.start()
        else:
            logger.warn('no headerfile path given, cannot start headerfile monitor')

class FileEventHandler(PatternMatchingEventHandler):
    """Overriding PatternMatchingEventHandler to handle when headerfile changes."""
    def __init__(self, patterns):
        super(FileEventHandler, self).__init__(patterns=patterns)

    def on_modified(self, event):
        super(FileEventHandler, self).on_modified(event)
        logger.info('[INFO] control file changed')
        file_parser.read(pedestal.control_file)
        new_azimuth = self._extract_param('AZIMUTH')
        new_elevation = self._extract_param('ELEVATION')
        logger.debug('New direction from control file: {}, {}'.format(new_azimuth, new_elevation))
        pedestal.set_position(float(new_azimuth), float(new_elevation))

    def _extract_param(self, param):
        """ returns the value of given param name
        """
        result = ""
        try:
            result = file_parser['Direction'][param]
        except Exception as e:
            logger.error('Could not find required parameter "{}" in {}'
                              .format(param, pedestal.control_file))
        return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage='pedestal.py',
                                     description='Monitor and control of a NeXtRAD antenna')
    parser.add_argument('-d', '--debug', help='display debug messages to STDOUT',
                        action='store_true', default=False)
    parser.add_argument('-c', '--cli', help='launch command-line interface',
                        action='store_true', default=False)
    parser.add_argument('-f', '--file', help="control file containing direction parameters")
    parser.add_argument('-p', '--port', help="serial port to connect to [/dev/ttyUSB0]", default='/dev/ttyUSB0')
    args = parser.parse_args()

    logger = logging.getLogger('pedestal_logger')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    if args.debug:
        ch.setLevel(logging.DEBUG)
    else:
        ch.setLevel(logging.WARNING)
    logger.addHandler(ch)

    pedestal = Pedestal(device=args.port)

    if args.cli:
        user_input = ''
        while user_input != 'y':
            print('\n')
            print('Pedestal Startup Sequence')
            print('-------------------------')
            print('1) Power on the pedestal')
            print('2) After remote has initialised, enter A-Z mode.')
            print('3) Use the remote to point antennas at reference point.')
            print('4) Power off the pedestal.')
            print('5) Repeat steps 1 and 2.')
            print('\n')
            print('NB: If the pedestal is switched off this process will need to be repeated')
            print('\n')
            user_input = input('press "y" if these operations have been performed (y/N)?\n')

        try:
            pedestal.connect()
            print('>>> Connection Established')
            pedestal.control_file = args.file
            file_parser = configparser.ConfigParser(comment_prefixes='/', allow_no_value=True)
            file_parser.optionxform = str  # retain upper case for keys
            pedestal.init_file_watchdog_thread()
        except Exception as e:
            logger.error('[ERROR] Error with establishing connection')

        while user_input != 'q':
            print('\n')
            print('Pedestal Control System')
            print('-----------------------')
            print('1 - Check Connection')
            print('2 - Get Position')
            print('3 - Set Position')
            print('q - Quit')
            print('\n')
            user_input = input('choose a selection\n\n')
            if user_input == '1':
                try:
                    pedestal.check_connection()
                    print('>>> Connected')
                except Exception as e:
                    logger.error('Error with connection')
            elif user_input == '2':
                try:
                    azimuth, elevation = pedestal.get_position()
                    print('>>> Azimuth: {}'.format(azimuth))
                    print('>>> Elevation: {}'.format(elevation))
                except Exception as e:
                    logger.error('Error with getting position')
            elif user_input == '3':
                try:
                    user_input = input('enter new position: [azimuth, elevation]\n')
                    user_input = user_input.split(',')
                    azi = float(user_input[0])
                    alt = float(user_input[1])
                    print('>>> Attempting to move...')
                    pedestal.set_position(azi, alt)
                except Exception as e:
                    logger.error('Error with setting position')
            elif user_input == 'q':
                sys.exit()
            else:
                pass

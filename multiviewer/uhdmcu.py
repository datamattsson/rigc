import os
import socket
import serial
import logging
import time

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S +0000')

class FourXOneUHD:
    def __init__(self, config):

        self.config = config
        
        self.logger = logging.getLogger('{name}'.format(name=__name__))
        self.logger.setLevel(logging.DEBUG if self.config.get(
            'local').get('debug') else logging.INFO)
        
        if os.path.exists(config['local']['serial_port']):
            self.connect = 'serial'
        else:
            self.connect = 'remote'
        self.logger.debug('Connection to MV with "{connect}" interface'.format(connect=self.connect))

        self.inputs = {
                'HDMI-1': 1,
                'HDMI-2': 2,
                'HDMI-3': 3,
                'HDMI-4': 4
                }

        self.remote_timeout = self.config['mv'].get('remote_timeout', 2.0)
        self.command_delay = self.config['mv'].get('command_delay', .1)

        self.config['mv']['modes'] = {
          '3840x2160p60': 3,
          '3840x2160p30': 5,
          '1920x1080p60': 8,
        }

        self.config['mv']['scenes'] = {
          'single': 1,
          'pip': 2,
          'pbp': 3, # Not implemented
          'triple': 4,
          'quad': 5
        }

        self.config['mv']['backgrounds'] = {
          'black': 1,
          'blue': 2
        }

        self.config['mv']['borders'] = {
          'black': 1,
          'red': 2,
          'green': 3,
          'blue': 4,
          'yellow': 5,
          'magenta': 6,
          'cyan': 7,
          'white': 8,
          'gray': 9
        }

        self.vka = self.config['mv']['backgrounds'][self.config['mv'].get('vka', 'blue')]


    def __poweroff(self):
        self.send_command('power 0!')

    def __poweron(self):
        self.send_command('power 1!')
    
    def __output(self, **kwargs):
        res = kwargs.get('res')

        if res and self.config['mv']['modes'][res]:
            self.send_command(f's output res {self.config["mv"]["modes"][res]}!')
        else:
            raise Exception(f'Invalid resolution, check config stanzas.')
    
    def __audio(self, **kwargs):
        if kwargs.get('port'):
            self.send_command(f's output audio {kwargs["port"]}!')
        else:
            raise Exception(f'HDMI port number is not set')
    
    def __scene(self, **kwargs):
        viewports = kwargs.get('viewports')
        pip = kwargs.get('pip')

        if viewports and self.config['mv']['scenes'][viewports]:
            self.send_command(f's multiview {self.config["mv"]["scenes"][viewports]}!')
            if viewports == 'triple':
                self.send_command('s triple mode 2!')
                self.send_command('s triple aspect 2!')
            if viewports == 'pip':
                x = pip.get('pos-x', 2)
                y = pip.get('pos-y', 3)
                size = pip.get('size', 25)
                self.send_command(f's PIP {x} {y} {size} {size}!')
        else:
            raise Exception(f'Invalid scene, check config stanzas')

    def __layout(self, **kwargs):
        grid = kwargs.get('grid')

        if grid:
            for hdmi in grid:
                if len(grid) == 1:
                    if grid[hdmi] == 1:
                        self.send_command(f's multiview {self.config["mv"]["scenes"]["single"]}!')
                        self.send_command(f's window 1 in {self.inputs[hdmi]}!')
                    else:
                        self.logger.debug(f'{hdmi} value not legal for scene type')
                else:
                    self.send_command(f's window {grid[hdmi]} in {self.inputs[hdmi]}!')
        else:
            raise Exception(f'Layout not found in config file')

    def send_command(self, cmd):
        console = ''

        if self.connect == 'serial':

            ser = serial.Serial(self.config['local']['serial_port'], 115200)

            msg = "{command}\n".format(command=cmd)

            self.logger.debug(f'About to send "{cmd}" to {self.config["local"]["serial_port"]}')
            ser.write(bytes(msg, encoding="ascii"))

            if self.config['local']['debug']:
                console = ser.readline().decode().rstrip('\r\n')

            self.logger.debug('Received from MV: "{msg}"'. format(msg=console))

        if self.connect == 'remote':

            host = self.config['mv']['ip_addr']
            port = 23 
            msg = "{command}".format(command=cmd)
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.remote_timeout)
                s.connect((host, port))
                self.logger.debug(f'About to send "{cmd}" to {host}:{port} with a timeout of {self.remote_timeout}s')
                s.sendall(bytes(msg, encoding="ascii"))

                if self.config['local']['debug']:
                    console = s.recv(32).decode().rstrip('\r\n')

                self.logger.debug('Received from MV: "{msg}"'. format(msg=console))
                s.shutdown(socket.SHUT_RDWR)
                s.close()

        time.sleep(self.command_delay)
        return console

    def baseline(self):
        self.send_command(f's multiview 1!')
        self.send_command(f's auto switch 0!')
        self.send_command(f's output hdcp 3!')
        self.send_command(f's output vka {self.vka}!')
        self.send_command(f's window source osd 0!')
        self.send_command(f's multiview 5!')
        self.send_command(f's window 1 border 0!')
        self.send_command(f's window 2 border 0!')
        self.send_command(f's window 3 border 0!')
        self.send_command(f's window 4 border 0!')

    def apply(self, profile):
        # Output
        self.__output(res=profile.get('output'))
        # Scene
        self.__scene(viewports=profile.get('scene'), pip=profile.get('pip', {}))
        # Layout
        self.__layout(grid=profile.get('layout'))
        # Audio
        self.__audio(port=profile.get('audio'))

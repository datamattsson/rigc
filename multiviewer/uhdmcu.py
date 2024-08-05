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

        if viewports and self.config['mv']['scenes'][viewports]:
            self.send_command(f's multiview {self.config["mv"]["scenes"][viewports]}!')
            if viewports == 'triple':
                self.send_command('s triple mode 2!')
                self.send_command('s triple aspect 2!')
        else:
            raise Exception(f'Invalid scene, check config stanzas')

    def __layout(self, **kwargs):
        grid = kwargs.get('grid')

        if grid:
            for hdmi in grid:
                if len(grid) == 1:
                    if grid[hdmi] == 1:
                        self.send_command(f's in source {self.inputs[hdmi]}!')
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
                console = s.recv(32).decode().rstrip('\r\n')
                self.logger.debug('Received from MV: "{msg}"'. format(msg=console))
                s.shutdown(socket.SHUT_RDWR)
                s.close()

        time.sleep(self.command_delay)
        return console

    def apply(self, profile):
        # Output
        self.__output(res=profile.get('output'))
        # Scene
        self.__scene(viewports=profile.get('scene'))
        # Layout
        self.__layout(grid=profile.get('layout'))
        # Audio
        self.__audio(port=profile.get('audio'))

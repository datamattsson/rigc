import os
import socket
import serial
import logging

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
                self.send_command('s triple aspect 2!')
        else:
            raise Exception(f'Invalid scene, check config stanzas')

    def __layout(self, **kwargs):
        grid = kwargs.get('grid')

        if grid:
            window = 1
            for viewport in grid:
                self.send_command(f's window {grid[viewport]} in {window}!')
                window += 1
        else:
            raise Exception(f'HDMI port number is not set')

    def send_command(self, cmd):
        if self.connect == 'serial':

            ser = serial.Serial(self.config['local']['serial_port'], 115200)

            msg = "{command}\n".format(command=cmd)

            self.logger.debug(f'About to send "{cmd}" to {self.config["local"]["serial_port"]}')
            ser.write(bytes(msg, encoding="ascii"))
            self.logger.debug('Received from MV: "{msg}"'. format(msg=ser.readline().decode().rstrip('\r\n')))

        if self.connect == 'remote':

            host = self.config['mv']['ip_addr']
            port = 23 
            msg = "{command}\n".format(command=cmd)
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(.3)
                s.connect((host, port))
                self.logger.debug(f'About to send "{cmd}" to {host}:{port}')
                s.sendall(bytes(msg, encoding="ascii"))
                self.logger.debug('Received from MV: "{msg}"'. format(msg=s.recv(64).decode().rstrip('\r\n')))

    def apply(self, profile):
        # Output
        self.__output(res=profile.get('output'))
        # Scene
        self.__scene(viewports=profile.get('scene'))
        # Layout
        self.__layout(grid=profile.get('layout'))
        # Audio
        self.__audio(port=profile.get('audio'))

import requests
import logging
import json
from time import sleep

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S +0000')

class ProConvert:
    def __init__(self, config, mbps):
        self.kbps = mbps * 1024
        self.config = config
        self.base_url = f'http://{self.config["encoder"]["ip_addr"]}/mwapi'
        self.user = self.config['encoder']['user']
        self.password = self.config['encoder']['pass']
        
        self.logger = logging.getLogger('{name}'.format(name=__name__))
        self.logger.setLevel(logging.DEBUG if self.config['local']['debug'] else logging.INFO)
        self.session = requests.Session()
        self.__authenticate()

        # Throttle params
        self.interval = 0.5
        self.iterations = 5
        self.increments = 15 # bitrate slider
        self.toleration = 5 # percentage
        # "slider"
        self.throttle_min = 50
        self.throttle_max = 200

        
    def send_command(self, **kwargs):
        payload = kwargs.get('payload')
        if not isinstance(payload, dict):
            self.logger.info(f'Invalid payload: "{payload}", sending a ping to Encoder.')
            payload = {'method': 'ping'}

        self.logger.debug(f'Sending payload to Encoder: "{payload}"')
        res = self.session.get(self.base_url, params=payload)
        self.logger.debug('Response from Encoder: "{response}"'.format(response=json.loads(res.text)))
        return json.loads(res.text)

    def __authenticate(self):
        payload = {}
        payload['method'] = 'login'
        payload['id'] = self.user
        payload['pass'] = self.password

        res = self.session.get(self.base_url, params=payload)
        self.logger.debug('Logged in: "{response}"'.format(response=json.loads(res.text)))

    def __set_bitrate(self, **kwargs):
        enc = kwargs.get('encoder')

        if enc:
            req = {'method': 'set-video-config'}
            req['bit-rate-ratio'] = str(enc['bitrate'])

            self.send_command(payload=req)
   
    def __set_framerate(self, **kwargs):
        enc = kwargs.get('encoder')

        if enc:
            req = {'method': 'set-video-config'}
            req['out-fr-convertion'] = enc['framerate']

            self.send_command(payload=req)
    
    def __set_output(self, **kwargs):
        enc = kwargs.get('encoder')

        if enc:
            req = {'method': 'set-video-config'}

            if enc['resolution'] == 'raw':
                req['out-raw-resolution'] = 'true'
            else:
                out_cx, out_cy = enc['resolution'].split('x')
                req['out-raw-resolution'] = 'false'
                req['out-cx'] = out_cx
                req['out-cy'] = out_cy

            self.send_command(payload=req)

    def __throttle(self):
        for i in range(self.iterations):

            # Current NDI bitrate
            req = {'method': 'get-summary-info'}
            res = self.send_command(payload=req)
            bitrate = int(res['ndi']['video-bit-rate'])

            # Current throttle
            req = {'method': 'get-video-config'}
            res = self.send_command(payload=req)
            throttle = int(res['bit-rate-ratio']) 

            diff = bitrate / self.kbps * 100 - 100

            self.logger.debug(f'bitrate={bitrate} throttle={throttle} diff={diff} kbps={self.kbps} toleration={self.toleration}')

            if diff < -abs(self.toleration) and diff < 0:
                if throttle < self.throttle_max:
                    set_rate = throttle + self.increments
                    if set_rate > self.throttle_max:
                        set_rate = self.throttle_max
                    enc = {'bitrate': set_rate}
                    self.__set_bitrate(encoder=enc)
                    self.logger.debug(f'Bump up to {set_rate}')
                    sleep(self.interval) 
                    continue

            if diff > self.toleration and diff > 0:
                if throttle > self.throttle_min:
                    set_rate = throttle - self.increments
                    if set_rate < self.throttle_min:
                        set_rate = self.throttle_min
                    enc = {'bitrate': set_rate}
                    self.__set_bitrate(encoder=enc)
                    self.logger.debug(f'Bump down to {set_rate}')
                    sleep(self.interval) 
                    continue
            
            self.logger.debug(f'Nothing to throttle. Currently at {throttle}.')
            break

    def apply(self, profile):
        self.__set_framerate(encoder=profile)
        self.__set_output(encoder=profile)
        if self.kbps:
            self.__throttle()
        else:
            self.__set_bitrate(encoder=profile)

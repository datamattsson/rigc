#!/usr/bin/env python3

import sys
import logging
import os

import yaml
import click

from multiviewer import *
from encoder import *

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S +0000')

class PinballRig:
    def __init__(self, config, mbps, baseline):
        self.config = config
        self.mbps = mbps
        self.baseline = baseline
        self.logger = logging.getLogger(f'{__name__}')
        self.logger.setLevel(logging.DEBUG if self.config.get(
            'local').get('debug') else logging.INFO)

    def configure(self, config, profile):
        try:
            mv = uhdmcu.FourXOneUHD(config)
            if profile:
                mv.apply(profile.get('mv'))
            else:
                mv.baseline()
                return
        except Exception as exc:
            self.logger.error(f'Unable to apply MV config: "{exc}"')
            raise RigBroke from exc
        if not self.config.get('local').get('ignore_encoder') and profile.get('encoder'):
            try:
                enc = magewell.ProConvert(config, self.mbps)
                enc.apply(profile.get('encoder'))
            except Exception as exc:
                self.logger.error(f'Unable to apply Encoder config: {exc}')
                raise RigBroke from exc

class RigBroke(Exception):
    pass

@click.command()
@click.option('--config', type=click.Path(exists=True),
              default='config.yaml', help='config.yaml formatted file')
@click.option('--profile', default='default', help='Profile name in --config')
@click.option('--mbps', default=0, help='Throttle encoder bitrate to Mbit/s, overrides bitrate in `encoder` sections in --config. Use with caution.')
@click.option('--baseline', default=False, help='Apply multiviewer baseline configuration suitable for streaming.', is_flag=True)
@click.option('--debug', default=False, help='Turn on very verbose logging and override --config flag.', is_flag=True)

def apply(config, profile, mbps, debug, baseline):

    logger = logging.getLogger(f'{__name__}')
    if debug:
        logger.setLevel(logging.DEBUG)

    with open(config, encoding="utf-8") as stream:
        try:
            cf = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logger.error(f'Unable to read config file "{config}" with exception: "{exc}"')
            sys.exit(1)

    config = cf.get('config')
    profiles = cf.get('profiles')

    if debug:
        config['local']['debug'] = True

    if config and profiles.get(profile) and not baseline:
        rig = PinballRig(config, mbps, baseline)
        try:
            rig.configure(config, profiles.get(profile))
            logger.debug(f'Rig configured with profile: "{profile}"')
        except RigBroke:
            logger.error('Failed configuring the rig, check logs.')
            sys.exit(1)
    elif config and baseline:
        rig = PinballRig(config, mbps, baseline)
        try:
            rig.configure(config, False)
            logger.debug(f'Rig baseline configured.')
        except RigBroke:
            logger.error('Failed applying baseline, check logs.')
            sys.exit(1)
    else:
        logger.error(f'The `config` stanza or profile "{profile}" in the `profiles` \
stanza invalid in --config file')
        sys.exit(1)

if __name__ == '__main__':
    apply(None, None, None, None, None)

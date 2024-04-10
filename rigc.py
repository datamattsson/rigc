import obspython as obs
import cli
import yaml
import logging

settings = {}
RIGC_PROFILE_DISABLED = 'disabled'

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S +0000')
logger = logging.getLogger(f'{__name__}')
logger.setLevel(logging.ERROR)

def script_description():
    return '''<h2>RigC</h2>
              <p>Original <code>scene_command_execute</code> script by <a href="https://github.com/marklagendijk">Mark Lagendijk</a>. Rewritten in Python by <a href="https://github.com/JosephSamela">Joe Samela</a>. Adopted to Mac and optimized for <a href="https://github.com/datamattsson/rigc">RigC</a> by <a href="https://github.com/datamattsson">Michael Mattsson</a>.
              <h3>Instructions:</h3>
              <ul>
               <li>Configure profiles in <code>config.yaml</code>
               <li>Select <code>config.yaml</code> in the file dialog
               <li>Reload the script (the cirular arrow below the script list)
               <li>Enable RigC
               <li>Select profiles to activate after transition->scene activation
               <li>Optionally, configure the desired encoder bitrate to override. 0 means use bitrate in <code>config.yaml<code>
              </ul>
              Visit the docs on <a href="https://github.com/datamattsson/rigc">GitHub</a> for more info.
            '''

def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_path(props, "rigc_config", "RigC configuration file", obs.OBS_PATH_FILE, '*.yaml', None)
    rigc_config = obs.obs_data_get_string(settings, "rigc_config")
    if rigc_config:
        obs.obs_properties_add_bool(props, "rigc_enabled", "Enable RigC")
        obs.obs_properties_add_bool(props, "rigc_debug", "Debug RigC (verbose Script Log)")
        obs.obs_properties_add_int(props, "rigc_bitrate", "Bitrate override (Mbit's)", 0, 100000, 1)
        scenes = obs.obs_frontend_get_scenes()
        profile_list = {}

        with open(rigc_config, encoding="utf-8") as stream:
            try:
                rigc_config_file = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                logger.error(f'Unable to read config file "{config}" with exception: "{exc}"')

        if scenes != None:
            for scene in scenes:
                scene_name = obs.obs_source_get_name(scene)
                profile_list[scene_name] = obs.obs_properties_add_list(props, f"rigc_profile_{scene_name}", f"{scene_name} profile", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
                obs.obs_property_list_add_string(profile_list[scene_name], '-', RIGC_PROFILE_DISABLED)
                for config_profile in rigc_config_file.get('profiles'):
                    obs.obs_property_list_add_string(profile_list[scene_name], config_profile, config_profile)

        obs.source_list_release(scenes)
    return props

def script_update(_settings):
    global settings
    settings = _settings

def script_load(settings):
    obs.obs_frontend_add_event_callback(handle_event)

def handle_event(event):
    if event == obs.OBS_FRONTEND_EVENT_SCENE_CHANGED:
        handle_scene_change()

def handle_scene_change():
    scene = obs.obs_frontend_get_current_scene()
    rigc_enabled = obs.obs_data_get_bool(settings, "rigc_enabled")
    rigc_debug = obs.obs_data_get_bool(settings, "rigc_debug")

    if rigc_debug:
        logger.setLevel(logging.DEBUG)

    if rigc_enabled:
        scene_name = obs.obs_source_get_name(scene)
        rigc_profile = obs.obs_data_get_string(settings, f"rigc_profile_{scene_name}")
        rigc_config = obs.obs_data_get_string(settings, "rigc_config")
        rigc_bitrate = obs.obs_data_get_int(settings, "rigc_bitrate")

        if rigc_profile != RIGC_PROFILE_DISABLED:
            rigc_args = [
                    f'--config={rigc_config}',
                    f'--profile={rigc_profile}',
                    f'--mbps={rigc_bitrate}'
                    ]
            if rigc_debug:
                rigc_args.append('--debug')
            logger.debug(f'Running RigC on {scene_name} with these args: {rigc_args}')
            try:
                result = rigcli.apply(rigc_args)
            except SystemExit:
                pass
        else:
            logger.debug(f"Activating {scene_name}. RigC is disabled for this scene.")
    else:
        logger.debug("RigC is disabled.")
    
    obs.obs_source_release(scene)

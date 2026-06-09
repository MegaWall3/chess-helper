import os
import platform
import subprocess
import config


class PikafishFileError(Exception):
    pass

def resolve_command():
    for path in command_candidates():
        if os.path.isfile(path):
            return os.path.abspath(path)
    raise PikafishFileError(f"未找到 Pikafish 可执行文件，请将解压后的引擎放到 {config.PIKAFISH_HOME}")

def resolve_nnue_file():
    for path in (
        os.path.join(config.PIKAFISH_HOME, 'pikafish.nnue'),
        os.path.join(config.PIKAFISH_HOME, 'src', 'pikafish.nnue'),
    ):
        if os.path.isfile(path):
            return os.path.abspath(path)
    raise PikafishFileError(f"未找到 pikafish.nnue，请将解压后的引擎文件放到 {config.PIKAFISH_HOME}")

def command_candidates():
    system = platform.system()
    machine = platform.machine().lower()
    cpu_flags = get_cpu_flags()

    if system == 'Darwin':
        names = ['pikafish-apple-silicon'] if 'arm' in machine else preferred_x86_names(cpu_flags)
        return candidate_paths('MacOS', names) + legacy_candidate_paths()
    if system == 'Linux':
        if 'arm' in machine or 'aarch' in machine:
            return candidate_paths('Android', ['pikafish-armv8-dotprod', 'pikafish-armv8']) + legacy_candidate_paths()
        return candidate_paths('Linux', preferred_x86_names(cpu_flags)) + legacy_candidate_paths()
    if system == 'Windows':
        names = [f'{name}.exe' for name in preferred_x86_names(cpu_flags)]
        return candidate_paths('Windows', names) + legacy_candidate_paths()
    if 'android' in system.lower():
        return candidate_paths('Android', ['pikafish-armv8-dotprod', 'pikafish-armv8']) + legacy_candidate_paths()

    return legacy_candidate_paths()

def candidate_paths(folder, names):
    return [os.path.join(config.PIKAFISH_HOME, folder, name) for name in names]

def legacy_candidate_paths():
    return [
        os.path.join(config.PIKAFISH_HOME, 'src', 'pikafish'),
        os.path.join(config.PIKAFISH_HOME, 'src', 'pikafish.exe'),
    ]

def preferred_x86_names(cpu_flags):
    if 'avx512vnni' in cpu_flags or 'avxvnni' in cpu_flags:
        return ['pikafish-avxvnni', 'pikafish-avx2', 'pikafish-bmi2', 'pikafish-sse41-popcnt']
    if 'avx512f' in cpu_flags:
        return ['pikafish-avx512', 'pikafish-avx2', 'pikafish-bmi2', 'pikafish-sse41-popcnt']
    return ['pikafish-avx2', 'pikafish-bmi2', 'pikafish-sse41-popcnt']

def get_cpu_flags():
    if platform.system() == 'Darwin':
        return run_command_for_flags(['sysctl', '-n', 'machdep.cpu.features']) | run_command_for_flags(['sysctl', '-n', 'machdep.cpu.leaf7_features'])
    if platform.system() == 'Linux':
        try:
            with open('/proc/cpuinfo', 'r') as file:
                return set(file.read().lower().replace('\n', ' ').split())
        except OSError:
            return set()
    return set()

def run_command_for_flags(command):
    try:
        output = subprocess.check_output(command, stderr=subprocess.DEVNULL, text=True)
        return set(output.lower().split())
    except (OSError, subprocess.CalledProcessError):
        return set()

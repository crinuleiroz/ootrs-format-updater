# Set to True to use spinner, false to show full file logs
USE_SPINNER = True

# Begin script
import os, sys, time
import tempfile
import shutil
import zipfile
import yaml
import unicodedata
from collections import defaultdict
from typing import Final

FILES = sys.argv[1:]

# ANSI Terminal Color Codes
RED        : Final = '\x1b[31m'
PINK_218   : Final = '\x1b[38;5;218m'
PINK_204   : Final = '\x1b[38;5;204m'
YELLOW     : Final = '\x1b[33m'
YELLOW_229 : Final = '\x1b[38;5;229m'
CYAN       : Final = '\x1b[36m'
BLUE_39    : Final = '\x1b[38;5;39m'
GRAY_245   : Final = '\x1b[38;5;245m'
GRAY_248   : Final = '\x1b[38;5;248m'
GREEN_79   : Final = '\x1b[38;5;79m'

BOLD      : Final = '\x1b[1m'
ITALIC    : Final = '\x1b[3m'
UNDERLINE : Final = '\x1b[4m'
STRIKE    : Final = '\x1b[9m'
RESET     : Final = '\x1b[0m'

PL  : Final = '\x1b[F'
CL  : Final = '\x1b[K'

SPINNER_FRAMES : Final[list[str]] = [
  "⢀⠀", "⡀⠀", "⠄⠀", "⢂⠀", "⡂⠀", "⠅⠀", "⢃⠀", "⡃⠀",
  "⠍⠀", "⢋⠀", "⡋⠀", "⠍⠁", "⢋⠁", "⡋⠁", "⠍⠉", "⠋⠉",
  "⠋⠉", "⠉⠙", "⠉⠙", "⠉⠩", "⠈⢙", "⠈⡙", "⢈⠩", "⡀⢙",
  "⠄⡙", "⢂⠩", "⡂⢘", "⠅⡘", "⢃⠨", "⡃⢐", "⠍⡐", "⢋⠠",
  "⡋⢀", "⠍⡁", "⢋⠁", "⡋⠁", "⠍⠉", "⠋⠉", "⠋⠉", "⠉⠙",
  "⠉⠙", "⠉⠩", "⠈⢙", "⠈⡙", "⠈⠩", "⠀⢙", "⠀⡙", "⠀⠩",
  "⠀⢘", "⠀⡘", "⠀⠨", "⠀⢐", "⠀⡐", "⠀⠠", "⠀⢀", "⠀⡀",
]

# HANDLE THREADING
import threading, itertools
from concurrent.futures import ThreadPoolExecutor

done_flag = threading.Event()
spinner_thread = threading.Thread()

def spinner_task(message: str, done_flag: threading.Event) -> None:
    for frame in itertools.cycle(SPINNER_FRAMES):
        if done_flag.is_set():
            break
        sys.stderr.write(f"{PL}{CL}{PINK_204}{frame}{RESET} {GRAY_245}{message}{RESET}\n")
        sys.stderr.flush()
        time.sleep(0.07)
    if USE_SPINNER:
      sys.stderr.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}{message}{RESET}\n")
    else:
      sys.stderr.write(f"{GREEN_79}✓{RESET} {GRAY_245}{message}{RESET}\n")
    sys.stderr.flush()

def start_spinner(message: str):
    if not USE_SPINNER:
        print(f"{GRAY_245}{message}{RESET}")

        class DummyThread:
          def join(self): pass
        return DummyThread()

    done_flag.clear()
    thread = threading.Thread(target=spinner_task, args=(message, done_flag))
    thread.start()
    return thread

# HANDLE ERROR LOGGING
import logging

logger = logging.getLogger('mmr_music_updater')
logger.setLevel(logging.ERROR)
logger.propagate = False
_log_handler = None

def log_error(message: str, exc_info = True):
  global _log_handler
  if _log_handler is None:
    _log_handler = logging.FileHandler('mmr-music-updater_errors.log', mode='a', encoding='utf-8')
    _log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(_log_handler)

  logger.error(message, exc_info=exc_info)

def remove_diacritics(text: str) -> str:
  '''Normalizes filenames to prevent errors caused by diacritics'''
  normalized = unicodedata.normalize('NFD', text)
  without_diacritics = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

  return without_diacritics

# HANDLE MUSIC FILE CLASSES
class SkipFileException(Exception):
  pass

class MusicArchive:
  def __init__(self, tempfolder):
    self.sequence: str = None
    self.meta: str = None
    self.bank: str = None
    self.bankmeta: str = None
    self.zsounds: list[int] = []
    self.tempfolder = tempfolder

  def unpack(self, filepath: str) -> None:
    if os.path.exists(self.tempfolder):
      os.rmdir(self.tempfolder)

    with zipfile.ZipFile(filepath, 'r') as zip_archive:
      for f in zip_archive.namelist():
        if f.endswith(".metadata"):
          raise SkipFileException("Archive contains .metadata, skipping.")
      zip_archive.extractall(self.tempfolder)

    for f in os.listdir(self.tempfolder):
      # filename = os.path.basename(f)
      # base_name = os.path.splitext(f)[0]
      extension = os.path.splitext(f)[1].lower()

      if extension == ".seq":
        self.sequence = f
        continue

      if extension == ".bankmeta":
        self.bankmeta = f
        continue

      if extension == ".zbank":
        self.bank = f
        continue

      if extension == ".zsound":
        self.zsounds.append(f)

      if extension == ".meta":
        self.meta = f

    if not self.sequence:
      raise FileNotFoundError(f'MusicArchive Error: No sequence file found!')
    if not self.meta:
      raise FileNotFoundError(f'MusicArchive Error: No meta file found!')

    if self.bank and not self.bankmeta:
      raise FileNotFoundError(f'MusicArchive Error: No bankmeta file found!')
    if not self.bank and self.bankmeta:
      raise FileNotFoundError(f'MusicArchive Error: No bank file found!')

# Write metadata file
class FlowStyleList(list):
  pass

class HexInt(int):
    pass

def represent_flow_style_list(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

def represent_hexint(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:int', f"0x{data:X}")

yaml.add_representer(FlowStyleList, represent_flow_style_list)
yaml.add_representer(HexInt, represent_hexint)

def write_metadata(folder: str, base_name: str, cosmetic_name: str, instrument_set: str | int, song_type: str, music_groups, zsounds: dict[str, dict[str, int]] = None):
  metadata_file_path = f"{folder}/{base_name}.metadata"

  yaml_dict : dict = {
    "game": "oot",
    "metadata": {
      "display name": cosmetic_name,
      "instrument set": HexInt(instrument_set) if isinstance(instrument_set, int) else instrument_set,
      "song type": song_type,
      "music groups": FlowStyleList([cat for cat in music_groups]),
    }
  }

  if zsounds:
    yaml_dict["metadata"]["audio samples"] = zsounds

  with open(metadata_file_path, "w", encoding="utf-8") as f:
    yaml.dump(yaml_dict, f, sort_keys=False, allow_unicode=True)

def copy_archive_files(source_dir: str, destination_dir: str) -> None:
  skip_extensions: list[str] = ['.meta'] # Skip the old metadata file

  for file in os.listdir(source_dir):
    name: str = os.path.basename(file)
    extension: str = os.path.splitext(file)[1]

    if extension.lower() in skip_extensions:
      continue

    shutil.copyfile(os.path.join(source_dir, file), os.path.join(destination_dir, file))

# def copy_unprocessed_files(source_dir: str, destination_dir: str) -> None:
#   skip_extensions: list[str] = ['.seq', '.meta', '.zbank', '.bankmeta', '.zsound']

#   for file in os.listdir(source_dir):
#     name: str = os.path.basename(file)
#     extension: str = os.path.splitext(file)[1]

#     if extension.lower() in skip_extensions:
#       continue

#     shutil.copyfile(os.path.join(source_dir, file), os.path.join(destination_dir, file))

def pack(filename: str, tempfolder: str, destination_dir: str) -> None:
    '''Packs the temp folder into a new ootrs file'''
    archive_base = os.path.join(destination_dir, filename)
    zip_path = f"{archive_base}.zip"
    mmrs_path = f"{archive_base}.ootrs"

    shutil.make_archive(archive_base, 'zip', tempfolder)

    if os.path.exists(mmrs_path):
      os.remove(mmrs_path)

    os.rename(zip_path, mmrs_path)

def process_meta_file(meta_filepath: str) -> tuple[str, str | int, str, list[str], dict]:
  with open(meta_filepath, 'r') as f:
    lines = f.readlines()
    lines = [line.rstrip() for line in lines]

    cosmetic_name = f"{lines[0]}"
    instrument_set = "custom" if lines[1] == '-' else int(lines[1], 16)

    if len(lines) < 3:
      song_type = "bgm"
    elif len(lines) >= 3:
      song_type = lines[2].lower()

    if len(lines) >= 4:
      music_groups = [category for category in lines[3].split(',')]

    zsounds = {}
    if len(lines) >= 5:
      for line in lines[4:]:
        tokens = line.split(':')

        # Try to parse new style, else fallback to old style
        try:
          if tokens[0] == 'ZSOUND':
            zsounds[tokens[4]] = {
              "instrument type": tokens[1],
              "list index": int(tokens[2]),
              "key region": tokens[3] if tokens[3] in ("LOW", "PRIM", "HIGH") else "PRIM"
            }
        except:
          if tokens[0] == 'ZSOUND':
            zsounds[tokens[1]] = {
              "temp address": int(tokens[2], 16)
            }

  return cosmetic_name, instrument_set, song_type, music_groups, zsounds

def convert_archive(input_file: str, destination_dir: str) -> None:
  filename = os.path.splitext(os.path.basename(input_file))[0]
  filepath = os.path.abspath(input_file)

  with tempfile.TemporaryDirectory(prefix='ootrs_convert_') as tempfolder:
    archive = MusicArchive(tempfolder)
    original_temp = archive.tempfolder

    try:
      archive.unpack(filepath)

      meta_name: str = os.path.splitext(os.path.basename(archive.meta))[0]
      meta_filepath: str = os.path.join(original_temp, archive.meta)
      cosmetic_name, instrument_set, song_type, music_groups, zsounds = process_meta_file(meta_filepath)

      with tempfile.TemporaryDirectory(prefix='ootrs_convert_2_') as song_folder:
        copy_archive_files(original_temp, song_folder)
        # copy_unprocessed_files(original_temp, song_folder)

        write_metadata(song_folder, meta_name, cosmetic_name, instrument_set, song_type, music_groups, zsounds)
        pack(f'{filename}', song_folder, destination_dir)

    except SkipFileException:
      return
    except Exception as e:
      raise Exception(e)

# Process single file
def processing_file(input_file: str, base_folder: str, conversion_folder: str) -> None:
  try:
    extension = os.path.splitext(input_file)[1]
    relative_path = os.path.relpath(input_file, base_folder)
    destination_dir = os.path.dirname(os.path.join(conversion_folder, relative_path))

    # Create the destination and copy the file to the destination
    os.makedirs(destination_dir, exist_ok=True)

    if extension == ".ootrs":
      convert_archive(input_file, destination_dir)

  except Exception as e:
    raise Exception(f"processing_file Error: {e}")

# Begin processing files
def process_with_spinner(input_file: str, base_folder: str, conversion_folder: str, show_file_log: bool = False) -> None:
  global spinner_thread
  try:
    processing_file(input_file, base_folder, conversion_folder)
  except Exception as e:
    done_flag.set()
    spinner_thread.join()
    print(f"{RED}Error processing {input_file}:{RESET}")
    print(f"{YELLOW}{str(e)}{RESET}")
    print()
    log_error(f"Error processing {input_file}", exc_info=True)
    spinner_thread = start_spinner("Processing file...")

def process_files(base_folder: str, conversion_folder: str, files: list[str], show_file_log: bool = False):
  os.makedirs(conversion_folder, exist_ok=True)

  files_by_dir = defaultdict(list)
  for input_file in files:
    rel_path = os.path.relpath(input_file, base_folder)
    dir_path = os.path.dirname(rel_path)
    files_by_dir[dir_path].append((input_file, os.path.basename(rel_path)))

  with ThreadPoolExecutor() as executor:
    for dir_path, file_entries in sorted(files_by_dir.items()):
      if not USE_SPINNER and show_file_log:
        print(f"{CYAN}Processing Directory:{RESET} {os.path.join(os.path.basename(base_folder), dir_path)}")
        for _, filename in sorted(file_entries, key=lambda x: x[1]):
          print(f"{GRAY_248}  └─ Processing file:{RESET} {filename}")

      for input_file, _, in file_entries:
        executor.submit(process_with_spinner, input_file, base_folder, conversion_folder, show_file_log)

def convert_music_files() -> None:
  global spinner_thread

  spinner_thread = start_spinner("Processing files...")

  try:
    for file in FILES:
      filepath = os.path.abspath(file)

      if os.path.isdir(file):
        base_folder = filepath
        parent_folder = os.path.dirname(base_folder)
        conversion_folder: str = os.path.join(parent_folder, f'{os.path.basename(base_folder)}_converted')

        files_to_process = [
          os.path.join(root, name)
          for root, _, files in os.walk(base_folder)
          for name in files
        ]

        if not USE_SPINNER:
          print(f"{CYAN}Processing directory:{RESET} {os.path.basename(base_folder)}")

        process_files(base_folder, conversion_folder, files_to_process, True)

      elif os.path.isfile(file):
        base_folder = os.path.dirname(filepath)
        conversion_folder: str = os.path.join(base_folder, 'converted_files')

        if not USE_SPINNER:
          print(f"{CYAN}Processing File:{RESET} {os.path.basename(file)}")

        process_files(base_folder, conversion_folder, [file])

  finally:
    done_flag.set()
    spinner_thread.join()
    if USE_SPINNER:
      sys.stdout.write(f"{PL}{CL}{GREEN_79}✓{RESET} {GRAY_245}All files processed.{RESET}\n")
    else:
      sys.stderr.write(f"{GREEN_79}✓{RESET} {GRAY_245}All files processed.{RESET}\n")
    sys.stdout.flush()

if __name__ == '__main__':
  convert_music_files()
  os.system('pause')
